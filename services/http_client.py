import requests
import random
import time

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
