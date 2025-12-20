from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

class PaginationScanner:
    def __init__(self, scraper):
        self.scraper = scraper

    def get_page_content(self, url):
        response = self.scraper.safe_request(url)
        if response and response.status_code == 200:
            return response.text, response.url
        return None, None

    def find_article_links(self, html, base_url):
        """
        Heuristic to find 'Post' links on a listing page.
        """
        soup = BeautifulSoup(html, 'html.parser')
        links = set()
        base_domain = urlparse(base_url).netloc
        
        # Strategy 1: Look for links inside common article containers
        candidate_containers = soup.find_all(['article', 'div'], class_=lambda x: x and ('post' in x or 'entry' in x or 'blog' in x or 'job' in x))
        
        candidates = []
        if candidate_containers:
            for c in candidate_containers:
                candidates.extend(c.find_all('a', href=True))
        else:
            # Fallback: Look for all links, will filter later
            candidates = soup.find_all('a', href=True)

        for a in candidates:
            href = a['href']
            full_url = urljoin(base_url, href)
            
            # Filter: Internal links only
            if urlparse(full_url).netloc != base_domain:
                continue
            
            # Filter: Navigation junk
            if any(x in full_url.lower() for x in ['/tag/', '/category/', '/author/', '#', 'wp-content', 'wp-includes']):
                continue
            
            # Filter: Main pages
            if full_url.rstrip('/') == base_url.rstrip('/'):
                continue
            
            # Additional Heuristic: Link text length (Posts usually have titles)
            text = a.get_text(strip=True)
            if len(text) < 10: 
                continue

            links.add(full_url)
            
        return list(links)

    def find_next_page(self, html, current_url):
        soup = BeautifulSoup(html, 'html.parser')
        
        # Strategy 1: <link rel="next"> (Best Standard)
        link_next = soup.find('link', rel='next')
        if link_next and link_next.get('href'):
            return urljoin(current_url, link_next['href'])

        # Strategy 2: <a> with rel="next"
        a_next = soup.find('a', rel='next')
        if a_next and a_next.get('href'):
            return urljoin(current_url, a_next['href'])
            
        # Strategy 3: Common Text "Next", "Next Page"
        # Be careful not to pick "Next Post" inside a single page.
        for a in soup.find_all('a', href=True):
            txt = a.get_text(strip=True).lower()
            if txt in ['next', 'next page', 'older posts', '>'] or 'next page' in txt:
                # Check if it looks like pagination
                href = a['href']
                if '/page/' in href or 'paged=' in href:
                    return urljoin(current_url, href)
                    
        return None
