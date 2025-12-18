import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import time
import random
import os
import re
import pandas as pd

# Import configuration
import config

def get_new_job_urls(sitemap_url, cutoff_date_str=None):
    """
    Fetches URLs from a sitemap (XML or HTML style) that were modified after the cutoff_date.
    Returns a list of dicts: [{'url': '...', 'date': 'YYYY-MM-DD'}, ...]
    """
    if not cutoff_date_str:
        yesterday = datetime.now() - timedelta(days=1)
        cutoff_date = yesterday 
    else:
        cutoff_date = datetime.strptime(cutoff_date_str, "%Y-%m-%d")

    print(f"Fetching sitemap: {sitemap_url}")
    print(f"Looking for posts after: {cutoff_date.strftime('%Y-%m-%d')}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(sitemap_url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f" [ERROR] Failed to fetch sitemap: {e}")
        return []

    # Helper to parse and valid date
    def parse_date(date_text):
        if not date_text: return None
        try:
            # Try ISO format with T
            dt_str = date_text.split("T")[0]
            # Try space format (RankMath HTML style: 2025-08-18 16:52 +00:00)
            dt_str = dt_str.split(" ")[0]
            
            dt_obj = datetime.strptime(dt_str, "%Y-%m-%d")
            if dt_obj >= cutoff_date:
                return dt_str
            return None
        except ValueError:
            return None

    target_items = []
    content = response.content
    
    # Attempt 1: Standard XML sitemap (using ElementTree)
    try:
        root = ET.fromstring(content)
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        xml_urls = root.findall('ns:url', namespace)
        if xml_urls:
            print("   -> Detected Standard XML Sitemap.")
            for url_tag in xml_urls:
                loc = url_tag.find('ns:loc', namespace)
                lastmod = url_tag.find('ns:lastmod', namespace)
                
                if loc is not None and loc.text and lastmod is not None:
                    valid_dt = parse_date(lastmod.text)
                    if valid_dt:
                        target_items.append({'url': loc.text, 'date': valid_dt})
            
            return target_items
            
    except ET.ParseError:
        pass 

    # Attempt 2: HTML Sitemap (RankMath/Yoast style)
    print("   -> Standard XML parsing failed/empty. Trying HTML Parse...")
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
                if valid_dt:
                     target_items.append({'url': link_tag.get('href'), 'date': valid_dt})
    
    return target_items

def extract_official_link(post_url):
    """
    Scrapes a specific post URL to find the 'Apply Link' and the Page Title.
    """
    search_keywords = [
        "Apply Link", 
        "Click Here", 
        "Official Notification", 
        "Apply Online", 
        "Original Post",
        "Registration Link"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        from urllib.parse import urlparse
        
        # Determine the base domain of the current post to filter out internal links
        parsed_post = urlparse(post_url)
        post_domain = parsed_post.netloc.replace('www.', '')

        response = requests.get(post_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract Page Title (usually in h1)
        page_title = "Unknown Title"
        h1_tag = soup.find('h1')
        if h1_tag:
            page_title = h1_tag.get_text(strip=True)
        
        for keyword in search_keywords:
            target_labels = soup.find_all(string=lambda text: text and keyword.lower() in text.lower())

            for label in target_labels:
                if len(label) > 100: 
                    continue

                # Helper to validate and return link data
                def validate_and_return(link_element):
                    href = link_element.get('href')
                    if not href:
                        return None
                    
                    # IGNORE INTERNAL LINKS / RELATIVE LINKS
                    if not href.startswith('http'):
                        # It is relative, so it's internal
                        return None
                    
                    if post_domain in href:
                        # It points back to the same site
                        return None

                    return {
                        'link': href,
                        'text': link_element.get_text(strip=True),
                        'title': page_title,
                        'match': label.strip()
                    }

                # STRATEGY 1: Parent Link
                parent_link = label.find_parent('a')
                if parent_link:
                    result = validate_and_return(parent_link)
                    if result: return result

                # STRATEGY 2: Sibling/Next Link
                element = label.parent
                next_link = element.find_next('a')
                if next_link:
                    result = validate_and_return(next_link)
                    if result: return result

        return None

    except Exception as e:
        print(f"Error scraping {post_url}: {e}")
        return None

def main():
    # Calculate date
    end_date_obj = datetime.now()
    start_date_obj = end_date_obj - timedelta(days=config.DAYS_BACK)
    
    start_date_str = start_date_obj.strftime("%Y-%m-%d")
    end_date_str = end_date_obj.strftime("%Y-%m-%d")
    
    print("--- STARTING SCRAPER ---")
    items = get_new_job_urls(config.SITEMAP_URL, start_date_str)
    
    if not items:
        print("No new URLs found matching the criteria.")
        return

    print(f"\nFound {len(items)} URLs to process.\n")

    results = []

    for i, item in enumerate(items):
        url = item['url']
        post_date = item['date']
        
        print(f"[{i+1}/{len(items)}] [{post_date}] Checking: {url}")
        
        data = extract_official_link(url)
        
        if data:
            match_info = f"'{data['text']}' (near '{data['match']}')"
            # Using simple text replacement for printing to avoid encoding issues
            title_print = data['title'][:50].encode('ascii', 'ignore').decode('ascii')
            print(f"   [FOUND] {title_print}... -> {match_info}")
            
            results.append({
                'Date Posted': post_date,
                'Job Title': data['title'],
                'Apply Link': data['link'],
                'Link Text': data['text'],
                'Context Found': data['match'],
                'Source Post': url
            })
        else:
            print("   [SKIP] No apply link found.")
        
        time.sleep(random.uniform(1.0, 2.0))

    # Summary
    print("\n--- SUMMARY ---")
    print(f"Processed {len(items)} posts.")
    print(f"Found {len(results)} Apply Links.")
    
    # Save to Excel with Dynamic Name
    if results:
        try:
            # 1. Ensure Output Directory Exists
            output_dir = os.path.join(os.getcwd(), config.OUTPUT_FOLDER)
            os.makedirs(output_dir, exist_ok=True)

            # 2. Generate Dynamic Filename
            # Extract domain name for slug (e.g., 'freshershunt' from 'freshershunt.in')
            domain_slug = "site"
            match = re.search(r'https?://([^/]+)/?', config.SITEMAP_URL)
            if match:
                domain = match.group(1)
                domain_parts = domain.split('.')
                # usually domain.com or sub.domain.com. Take the main part.
                if len(domain_parts) >= 2:
                   domain_slug = domain_parts[-2] # take 'freshershunt' from 'freshershunt.in'
                else: 
                   domain_slug = domain_parts[0]

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Format: SITE_TIMESTAMP_FROM_TO.xlsx
            filename = f"{domain_slug}_{timestamp}_from_{start_date_str}_to_{end_date_str}.xlsx"
            
            full_path = os.path.join(output_dir, filename)

            df = pd.DataFrame(results)
            df.to_excel(full_path, index=False)
            print(f"\n[SUCCESS] Results saved to: {full_path}")
            
        except Exception as e:
            print(f"[ERROR] Error saving file: {e}")

if __name__ == "__main__":
    main()
