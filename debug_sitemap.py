import requests
import xml.etree.ElementTree as ET

url = 'https://freshershunt.in/post-sitemap.xml'
print(f"Fetching {url}...")
headers = {'User-Agent': 'Mozilla/5.0'}
try:
    r = requests.get(url, headers=headers)
    print(f"Status: {r.status_code}")
    content = r.content
    root = ET.fromstring(content)
    namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    
    urls = root.findall('ns:url', namespace)
    print(f"Found {len(urls)} URLs.")
    
    for i, u in enumerate(urls[:5]):
        lastmod = u.find('ns:lastmod', namespace)
        loc = u.find('ns:loc', namespace)
        lm_text = lastmod.text if lastmod is not None else "None"
        print(f"[{i}] {loc.text[:50]}... -> LastMod: {lm_text}")
        
except Exception as e:
    print(f"Error: {e}")
