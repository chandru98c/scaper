from flask import Flask, render_template, request, Response, send_file
import random
import time
import pandas as pd
import os
from datetime import datetime, timedelta
import scraper as job_scraper

OUTPUT_FOLDER = 'scraped_data'

app = Flask(__name__)

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

        items = job_scraper.get_new_job_urls(sitemap_url, start_date_str, end_date_str)
        
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
                data = job_scraper.extract_official_link(url)
                
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

            # Polite Wait: Random 4-8s (Simulating human reading time)
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
    path = os.path.join(OUTPUT_FOLDER, filename)
    return send_file(path, as_attachment=True)

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
