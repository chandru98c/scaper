import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

def get_new_job_urls(scraper, sitemap_url, cutoff_date_str=None, end_date_str=None):
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
    
    # Use the passed polite requester
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
