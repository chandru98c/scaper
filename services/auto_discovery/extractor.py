import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup

def extract_official_link(scraper, post_url):
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
