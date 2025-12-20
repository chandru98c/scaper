from flask import Flask, render_template, request, Response, send_file, send_from_directory
import random
import time
import pandas as pd
import os
from datetime import datetime, timedelta

# Import Services
from services.http_client import PoliteScraper
from services.sitemap_parser import get_new_job_urls
from services.extractor import extract_official_link
# Feature 2 Import
from services.auto_discovery.runner import AutoDiscoveryRunner
from services.config import OUTPUT_FOLDER

app = Flask(__name__)

# Initialize Global Scraper to reuse session
global_scraper = PoliteScraper()

# Route for the Home Page
@app.route('/')
def index():
    return render_template('index.html')

# Route to Stream Logs
@app.route('/stream')
def stream():
    sitemap_url = request.args.get('sitemap_url')
    # Receive precise dates from Frontend
    start_date_param = request.args.get('start_date') 
    end_date_param = request.args.get('end_date')

    def generate():
        yield "data: [START] Initializing Scraper...\n\n"
        
        # Date Logic
        if not start_date_param:
            # Fallback (Should typically be provided by UI)
            start_date = datetime.now() - timedelta(days=2)
            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = datetime.now().strftime("%Y-%m-%d")
        else:
            start_date_str = start_date_param
            # If no end date provided, default to today
            end_date_str = end_date_param if end_date_param else datetime.now().strftime("%Y-%m-%d")
        
        yield f"data: [INFO] Fetching sitemap: {sitemap_url}\n\n"
        yield f"data: [INFO] Searching Range: {start_date_str} to {end_date_str}\n\n"

        # Call Service with scraper instance
        items = get_new_job_urls(global_scraper, sitemap_url, start_date_str, end_date_str)
        
        if not items:
            yield "data: [ERROR] No new URLs found or Sitemap unreachable.\n\n"
            yield "event: close\ndata: close\n\n"
            return

        yield f"data: [INFO] Found {len(items)} URLs. Starting processing...\n\n"
        
        results = []
        total = len(items)

        for i, item in enumerate(items):
            url = item['url']
            post_date = item['date']
            
            yield f"data: [{i+1}/{total}] Checking: {url}\n\n"
            
            try:
                # Call Service
                data = extract_official_link(global_scraper, url)
                
                if data:
                    title_sh = data['title'][:40]
                    yield f"data: [FOUND] {title_sh}... ({data['match']})\n\n"
                    results.append({
                        'Date Posted': post_date,
                        'Job Title': data['title'],
                        'Apply Link': data['link'],
                        'Link Text': data['text'],
                        'Context': data['match'],
                        'Source Post': url
                    })
                else:
                    yield "data: [SKIP] No confident link found.\n\n"
            except Exception as e:
                yield f"data: [WARN] Error checking URL: {e}\n\n"

            # Polite Wait: Random 4-8s
            wait = random.randint(4, 8)
            for s in range(wait):
               time.sleep(1)
            
        # Save File
        if results:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"jobs_scraped_{timestamp}.xlsx"
            filepath = os.path.join(OUTPUT_FOLDER, filename)
            
            if not os.path.exists(OUTPUT_FOLDER):
                os.makedirs(OUTPUT_FOLDER)
                
            pd.DataFrame(results).to_excel(filepath, index=False)
            
            yield f"data: [SUCCESS] Saved {len(results)} jobs.\n\n"
            yield f"data: [DOWNLOAD] {filename}\n\n" # Front end will catch this to trigger download
        else:
            yield "data: [DONE] Checked all, but found no valid links.\n\n"

        yield "event: close\ndata: close\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

# --- FEATURE 2 ENDPOINT ---
@app.route('/stream_auto')
def stream_auto():
    homepage_url = request.args.get('homepage_url')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not homepage_url:
        def generate_error():
            yield "data: [ERROR] No URL provided\n\n"
            yield "data: close\n\n"
        return Response(generate_error(), mimetype='text/event-stream')

    def generate():
        runner = AutoDiscoveryRunner(global_scraper)
        for log in runner.run(homepage_url, start_date, end_date, OUTPUT_FOLDER):
            yield f"data: {log}\n\n"
        yield "data: close\n\n"

    return Response(generate(), mimetype='text/event-stream')

# --- HISTORY API ---
@app.route('/api/files')
def list_files():
    if not os.path.exists(OUTPUT_FOLDER):
        return {"files": []}
    
    files = []
    for f in os.listdir(OUTPUT_FOLDER):
        if f.endswith('.xlsx') or f.endswith('.csv'):
            path = os.path.join(OUTPUT_FOLDER, f)
            stat = os.stat(path)
            # Create a nice object
            files.append({
                "name": f,
                "size": f"{stat.st_size / 1024:.1f} KB",
                "date": datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                "timestamp": stat.st_mtime
            })
    
    # Sort by Newest First
    files.sort(key=lambda x: x['timestamp'], reverse=True)
    return {"files": files}

# --- OPEN API (Local Only) ---
@app.route('/api/open/<filename>')
def open_local_file(filename):
    if not filename: return {"status": "error"}
    path = os.path.join(OUTPUT_FOLDER, filename)
    if os.path.exists(path):
        import subprocess, sys
        try:
            if os.name == 'nt': # Windows
                os.startfile(path)
            elif sys.platform == 'darwin': # macOS
                subprocess.call(('open', path))
            else: # linux
                subprocess.call(('xdg-open', path))
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "msg": str(e)}
    return {"status": "not found"}

if __name__ == '__main__':
    import webbrowser
    from threading import Timer
    import os

    def open_browser():
        if not os.environ.get("WERKZEUG_RUN_MAIN"):
            webbrowser.open('http://127.0.0.1:5000')

    # Wait just 1 second to ensure server binds port, then open
    Timer(1, open_browser).start()
    app.run(debug=True, port=5000)
