# Job Scraper Pro 🚀

A professional-grade, privacy-focused job extraction tool built with **Flask** and **Vanilla JS**. Designed for teams to scrape, analyze, and manage job applications locally while staying consistent.

![Status](https://img.shields.io/badge/Status-Stable-green) ![Security](https://img.shields.io/badge/Security-Local%20Only-blue) ![Sync](https://img.shields.io/badge/Sync-Google%20Drive-orange)

## ✨ Unique Features

### 🔄 1. Zero-Config Team Sync (New!)
Work with a partner without setting up a database server.
- **Shared Memory:** The app automatically checks your Google Drive (`G:\My Drive\sharded_scaper`) for a history file.
- **Duplicate Protection:** If your partner scraped a job 5 minutes ago, the app detects it instantly and marks it as a **Duplicate** in your report.
- **Privacy First:** No cloud API keys, no passwords shared. Uses your existing file system permissions.

### 🕸️ 2. Auto-Discovery Engine
- **Target:** Any career page URL (e.g., `company.com/careers`).
- **Smart Crawling:** Automatically detects "Next" buttons, handles pagination, and stops crawling when posts get too old based on your selected date range.

### 🗺️ 3. Sitemap Scraper
- **Target:** `/sitemap.xml` files.
- **Precision:** Filters aggressively by date to only process the newest posts.

### 🛡️ 4. Enterprise-Grade Extraction
- **Polite Scraping:** Random delays and User-Agent rotation to avoid getting blocked.
- **Smart Scoring:** Uses a heuristic algorithm to identify the *real* "Apply Now" link among dozens of other links on a page.

---

## 🛠️ Installation & Setup

### Prerequisites
1.  **Python 3.10+**
2.  **Google Drive for Desktop** (Specific for Sync Feature) installed and running.

### Quick Start
1.  **Clone the Repo**
    ```bash
    git clone <your-repo-url>
    cd scaper
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Setup Team Sync (One-Time)**
    - Ensure your Google Drive is mounted (usually `G:\`).
    - Create a folder named: `sharded_scaper` in `My Drive`.
    - That's it! The app will automatically create and sync the `seen_apply_link.txt` file there.

4.  **Run the Application**
    ```bash
    python app.py
    ```
    - The dashboard will open automatically at `http://127.0.0.1:5000`.

---

## 👥 How Team Sync Works

When you run a scan, the application follows this logic:

1.  **Read:** It pulls the latest `seen_apply_link.txt` from your Shared Drive.
2.  **Scrape:** It scans the target website.
3.  **Check:**
    - **Found New Job?** -> Writes to Excel (Green) + Appends to Shared Drive File.
    - **Found Old Job?** -> Writes to Excel (Red Highlight) + Skips adding to Drive.
4.  **Result:**
    - You get a clean Excel sheet with duplicates clearly highlighted in **RED**.
    - Your teammate instantly knows you've already "Seen" that job.

---

## 📂 Architecture

This project follows a modular **Service-Oriented Architecture**:

- **`app.py`**: The Orchestrator. Handles routes, SSE streaming, and the Drive file logic.
- **`services/http_client.py`**: The Network Layer. Handles retries, timeouts, and politeness.
- **`services/extractor.py`**: The Brain. Contains the logic to find the "Official" link.
- **`services/auto_discovery`**: The Engine. Handles pagination and infinite scrolling logic.

---

## 🔒 Security Note

- **No Cloud Database**: We intentionally avoid `.env` database connections to keep credentials off user machines.
- **Credential Safety**: Authentication relies entirely on your OS-level Google Drive login. The Python script never touches passwords.
- **Vulnerability Checks**:
    - *Dec 2025*: Patched `node-jws` vulnerability in the accompanying web dashboard.
    - All unnecessary local ports are closed; the app runs on `localhost` only.
