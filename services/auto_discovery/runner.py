from services.http_client import PoliteScraper
from services.auto_discovery.pagination import PaginationScanner
from services.auto_discovery.extractor import extract_official_link
import pandas as pd
import os
import datetime
from dateutil import parser
from bs4 import BeautifulSoup
import re

class AutoDiscoveryRunner:
    def __init__(self, scraper: PoliteScraper):
        self.scraper = scraper
        self.scanner = PaginationScanner(scraper)
        
    def extract_date_from_page(self, html, url):
        """
        Attempts to find the publish date of a page.
        """
        try:
            # 1. Check URL for date pattern (YYYY/MM/DD)
            match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
            if match:
                return datetime.datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).date()

            soup = BeautifulSoup(html, 'html.parser')
            
            # 2. Meta Tags (JSON-LD is best but complex, try standard meta first)
            meta_date = soup.find('meta', property='article:published_time') or \
                        soup.find('meta', itemprop='datePublished') or \
                        soup.find('meta', name='pubdate')
            
            if meta_date and meta_date.get('content'):
                dt = parser.parse(meta_date['content'])
                return dt.date()
                
            # 3. Time tag
            time_tag = soup.find('time')
            if time_tag and time_tag.get('datetime'):
                dt = parser.parse(time_tag['datetime'])
                return dt.date()
                
            return None
        except:
            return None

    def run(self, homepage_url, start_date_str, end_date_str, output_folder='scraped_data'):
        yield f"[START] Auto-Discovery (Pagination Mode) for: {homepage_url}"
        
        try:
            s_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
            e_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except:
            yield "[ERROR] Invalid date format."
            return

        current_url = homepage_url
        visited_urls = set()
        results = []
        page_num = 1
        keep_running = True
        
        while keep_running and current_url:
            yield f"[INFO] Scanning Page {page_num}: {current_url}"
            html, final_url = self.scanner.get_page_content(current_url)
            
            if not html:
                yield "[WARN] Failed into fetch page. Stopping."
                break
                
            # Find Articles
            article_links = self.scanner.find_article_links(html, final_url)
            yield f"[INFO] Found {len(article_links)} potential articles."
            
            if not article_links:
                yield "[WARN] No article links found on this page."
                # Don't stop immediately, try next page just in case? No, usually empty page means done.
                
            # Process Articles
            valid_articles_on_page = 0
            
            for link in article_links:
                if link in visited_urls: continue
                visited_urls.add(link)
                
                # Visit Article to check Date & Content
                # Note: This is request intensive (N requests per listing page). 
                # Optimization: If link has date in URL, check that FIRST.
                
                # Optimistic Date Check from URL
                url_date = self.extract_date_from_page(None, link)
                if url_date:
                    if url_date < s_date:
                        yield f"[STOP] Found old post ({url_date}) in URL. Stopping."
                        keep_running = False
                        break
                    
                # If we couldn't determine date from URL, or it looks valid/new, we MUST visit.
                # Delay provided by scraper.safe_request
                a_html, _ = self.scanner.get_page_content(link)
                if not a_html: continue
                
                pub_date = self.extract_date_from_page(a_html, link)
                
                if not pub_date:
                    # If No Date found, we assume it's RELEVANT? Or SKIP? 
                    # Safer to SKIP or Log. But for many modern sites date is hidden.
                    # Let's assume relevant if we are on Page 1.
                    # Actually, risking infinite scrape. Let's Log.
                    # yield f"[SKIP] No date found: {link}"
                    # continue
                    pass # Treat as valid candidate to try extracting job link

                if pub_date:
                    if pub_date < s_date:
                        # Found an article older than start date. 
                        # If this is Page 1, it might be mixed. If Page 2, likely we are done.
                        # We will assume reverse chronological order.
                        yield f"[STOP] Reached older content: {pub_date}"
                        keep_running = False
                        break
                    if pub_date > e_date:
                        continue # Too new? (Future post?)
                
                # Date Valid or Unknown -> Extract Job
                valid_articles_on_page += 1
                yield f"[CHECK] {link}"
                
                # Reuse the Global Extractor logic (Pure Function)
                data = extract_official_link(self.scraper, link)
                if data:
                    yield f"[FOUND] {data['title'][:30]}..."
                    results.append({
                        'Source_URL': link,
                        'Publish_Date': pub_date,
                        'Job_Title': data['title'],
                        'Apply_Link': data['link'],
                        'Link_Text': data['text'],
                        'Match_Type': data['match']
                    })
            
            if not keep_running: break
            
            # Next Page - Only go if we found valid stuff or we are exploring
            # If we found NOTHING on this page, maybe we should stop?
            
            next_url = self.scanner.find_next_page(html, final_url)
            if next_url and next_url not in visited_urls:
                current_url = next_url
                page_num += 1
                yield f"[NEXT] Moving to Page {page_num}..."
            else:
                yield "[DONE] No next page found."
                break

        # Save
        if results:
            df = pd.DataFrame(results)
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)
            
            domain = homepage_url.replace('http://', '').replace('https://', '').split('/')[0]
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"auto_{domain}_{timestamp}.xlsx"
            filepath = os.path.join(output_folder, filename)
            
            df.to_excel(filepath, index=False)
            yield f"[DOWNLOAD] {filename}"
        else:
            yield "[DONE] Finished. No jobs extracted."
