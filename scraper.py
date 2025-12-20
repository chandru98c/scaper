import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import time
import random
import os
import re
import pandas as pd
from urllib.parse import urlparse

# Import configuration
import config

class PoliteScraper:
    def __init__(self):
        self.session = requests.Session()
        # Common modern browser signatures
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
        ]
        
    def get_headers(self, referer=None):
        """Generates random human-like headers."""
        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate', # Removed br to avoid compression issues
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        if referer:
            headers['Referer'] = referer
            headers['Sec-Fetch-Site'] = 'same-origin'
            
        return headers

    def safe_request(self, url, referer=None):
        """
        Requests a URL with exponential backoff and error handling.
        """
        retries = 3
        backoff = 5 
        
        for i in range(retries):
            try:
                # Add a small random delay BEFORE requesting (mimics "thinking" time)
                time.sleep(random.uniform(2.0, 5.0))
                
                response = self.session.get(
                    url, 
                    headers=self.get_headers(referer), 
                    timeout=30 # Increased timeout
                )
                
                if response.status_code in [429, 500, 502, 503, 504]:
                    print(f"   [WAIT] Server said {response.status_code}. Sleeping {backoff}s...")
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                    
                response.raise_for_status()
                return response
                
            except requests.RequestException as e:
                print(f"   [WARN] Attempt {i+1} failed: {e}")
                time.sleep(backoff)
                
        return None

# Initialize the polite scraper
scraper = PoliteScraper()

def get_new_job_urls(sitemap_url, cutoff_date_str=None, end_date_str=None):
    if not cutoff_date_str:
        yesterday = datetime.now() - timedelta(days=1)
        cutoff_date = yesterday 
    else:
        cutoff_date = datetime.strptime(cutoff_date_str, "%Y-%m-%d")

    # Parse End Date
    end_date = datetime.now()
    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        end_date = end_date.replace(hour=23, minute=59, second=59)

    print(f"Fetching sitemap: {sitemap_url}")
    print(f"Looking for posts between: {cutoff_date.strftime('%Y-%m-%d')} and {end_date.strftime('%Y-%m-%d')}")
    
    # Use the polite requester
    response = scraper.safe_request(sitemap_url)
    if not response:
        return []

    target_items = []
    content = response.content
    
    def parse_date(date_text):
        if not date_text: return None
        try:
            dt_str = date_text.split("T")[0].split(" ")[0]
            dt_obj = datetime.strptime(dt_str, "%Y-%m-%d")
            # Check Range (Inclusive)
            if cutoff_date <= dt_obj <= end_date: 
                return dt_str
        except: return None
        return None

    # Attempt 1: Standard XML
    try:
        if content.strip().startswith(b'<'):
            root = ET.fromstring(content)
            namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            xml_urls = root.findall('ns:url', namespace)
            
            if xml_urls:
                print("   -> Detected Standard XML Sitemap.")
                for url_tag in xml_urls:
                    loc = url_tag.find('ns:loc', namespace)
                    lastmod = url_tag.find('ns:lastmod', namespace)
                    if loc is not None and lastmod is not None:
                        valid_dt = parse_date(lastmod.text)
                        if valid_dt: target_items.append({'url': loc.text, 'date': valid_dt})
                return target_items
    except: pass 

    # Attempt 2: HTML Sitemap
    print("   -> Trying HTML Parse...")
    soup = BeautifulSoup(content, 'html.parser')
    rows = soup.select('table#sitemap tbody tr')
    if rows:
        print(f"   -> Detected HTML Sitemap Table with {len(rows)} rows.")
        for row in rows:
            cols = row.find_all('td')
            if not cols: continue
            link_tag = cols[0].find('a')
            date_text = cols[-1].text if cols else None
            
            if link_tag and link_tag.get('href'):
                valid_dt = parse_date(date_text)
                if valid_dt: target_items.append({'url': link_tag.get('href'), 'date': valid_dt})
    
    return target_items

def extract_official_link(post_url):
    # Use polite requester with Referer
    response = scraper.safe_request(post_url, referer="https://www.google.com/")
    if not response: return None
            
    try:
        parsed_post = urlparse(post_url)
        post_domain = parsed_post.netloc.replace('www.', '')
        soup = BeautifulSoup(response.content, 'html.parser')
        
        page_title = "Unknown Title"
        h1 = soup.find('h1')
        if h1: page_title = h1.get_text(strip=True)
        
        # --- PROBABILITY SCORING LOGIC ---
        
        # 1. Identify Company Keywords from Title
        ignore_words = ['off', 'campus', 'hiring', 'recruitment', 'job', 'vacancy', 'careers', '2024', '2025', '2026', 'freshers', 'apply', 'online', 'drive', 'engineer', 'developer', 'analyst', 'manager', 'specialist']
        title_clean = re.sub(r'[^a-zA-Z0-9\s]', '', page_title.lower()).split()
        company_keywords = [w for w in title_clean if len(w) > 3 and w not in ignore_words]

        # Candidate List
        candidates = []

        def add_candidate(link_el, context, base_score):
            href = link_el.get('href', '')
            if not href or not href.startswith('http'): return
            if post_domain in href: return # Ignore internal
            
            # Blacklist - Enhanced
            blacklist = [
                'telegram', 't.me', 'whatsapp', 'wa.me', 'facebook', 'fb.com', 
                'instagram', 'youtube', 'youtu.be', 'linkedin', 'twitter', 'x.com', 
                'discord', 'pinterest', 'reddit', 'tiktok', 'snapchat', 
                'openinapp', 'linktr.ee', 'bit.ly', 'goo.gl', 'tinyurl', 'cutt.ly'
            ]
            
            # Parse candidate URL to check domain specifically
            try:
                cand_parsed = urlparse(href)
                cand_domain = cand_parsed.netloc.lower()
                # Check if blacklist item is domain or suffix (e.g. sub.twitter.com or twitter.com)
                if any(b == cand_domain or cand_domain.endswith('.' + b) for b in blacklist): 
                    return
                # Also check if blacklist item is INSIDE the domain (for match like 'sub.bit.ly')
                if any(b in cand_domain for b in blacklist):
                     return
            except:
                pass
            
            # Old buggy check was: if any(b in href.lower() for b in blacklist): return
            # This matched 'x.com' inside 'netflix.com' query param.
            
            # Score Calculation
            score = base_score
            boosts = []
            
            # Boost 1: Company Name in URL (The strongest signal)
            if company_keywords and any(c in href.lower() for c in company_keywords):
                score += 50
                boosts.append("CompanyURL")
            
            # Boost 2: Career Keywords in URL
            if 'career' in href.lower() or 'jobs' in href.lower() or 'recruitment' in href.lower():
                score += 20
                boosts.append("CareerTerm")
            
            candidates.append({
                'link': href,
                'text': link_el.get_text(strip=True),
                'score': score,
                'match': f"{context} ({', '.join(boosts)})"
            })

        # STRATEGY 1: TABLE SCAN (High Context)
        # Often links are in <tr> alongside "Apply Link" text
        for row in soup.find_all('tr'):
            row_text = row.get_text(" ", strip=True).lower()
            if "apply" in row_text or "link" in row_text or "click here" in row_text:
                for link in row.find_all('a'):
                    add_candidate(link, "Table Context", 90) # Boosted to 90 to beat generic CompanyURLs

        # STRATEGY 2: KEYWORD NEIGHBORS (Medium Context)
        keywords = ["Apply Link", "Click Here", "Official Notification", "Apply Online", "Registration Link"]
        for kw in keywords:
            for label in soup.find_all(string=lambda t: t and kw.lower() in t.lower()):
                if len(label) > 100: continue
                
                # Check Parent <a>
                parent = label.find_parent('a')
                if parent: add_candidate(parent, f"Keyword ({kw})", 90) # Boosted to 90
                
                # Check Next <a>
                try:
                    nxt = label.find_next('a')
                    # Ensure the next link is reasonably close (not in footer)
                    if nxt: add_candidate(nxt, f"Next to ({kw})", 90)
                except: pass

        # STRATEGY 3: GLOBAL SMART SCAN
        # If we know the company name, check ALL links on page for it
        if company_keywords:
            for link in soup.find_all('a', href=True):
                add_candidate(link, "Global Smart Scan", 10) # Lowered base to 10 so it only wins if no context found

        # DECISION TIME
        if not candidates: return None

        # Sort by Score (Desc)
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Log top decision for debugging
        winner = candidates[0]
        # print(f"   [DECISION] Winner: {winner['link']} (Score: {winner['score']})")
        
        if winner['score'] >= 30: # Minimum confidence threshold
            return {
                'title': page_title,
                'link': winner['link'],
                'text': winner['text'],
                'match': winner['match']
            }
            
        return None

    except Exception as e:
        print(f"Error scraping {post_url}: {e}")
        return None

def main():
    end_date_obj = datetime.now()
    start_date_obj = end_date_obj - timedelta(days=config.DAYS_BACK)
    start_date_str = start_date_obj.strftime("%Y-%m-%d")
    
    print("--- STARTING POLITE SCRAPER ---")
    items = get_new_job_urls(config.SITEMAP_URL, start_date_str)
    
    if not items:
        print("No new URLs found.")
        return

    print(f"\nFound {len(items)} URLs to process.\n")
    results = []

    for i, item in enumerate(items):
        url = item['url']
        post_date = item['date']
        
        print(f"[{i+1}/{len(items)}] [{post_date}] Visiting: {url}")
        
        data = extract_official_link(url)
        
        if data:
            title_print = data['title'][:50].encode('ascii', 'ignore').decode('ascii')
            print(f"   [FOUND] {title_print}...")
            results.append({
                'Date Posted': post_date,
                'Job Title': data['title'],
                'Apply Link': data['link'],
                'Link Text': data['text'],
                'Context': data['match'],
                'Source Post': url
            })
        else:
            print("   [SKIP] No confident apply link found.")
        
        # POLITE WAIT: Wait 10 to 20 seconds between posts
        wait_time = random.uniform(5.0, 10.0) # Reduced slightly for testing, but still safe
        print(f"   -> Reading page... (Waiting {int(wait_time)}s)")
        time.sleep(wait_time)

    if results:
        # Robust Save Logic
        output_dir = os.path.join(os.getcwd(), config.OUTPUT_FOLDER)
        if not os.path.exists(output_dir): os.makedirs(output_dir)
        
        timestamp = datetime.now().strftime('%H%M%S')
        filename = f"{config.OUTPUT_FOLDER}/jobs_{start_date_str}_{timestamp}.xlsx"
        
        pd.DataFrame(results).to_excel(filename, index=False)
        print(f"\n[SUCCESS] Saved to: {filename}")

if __name__ == "__main__":
    main()
