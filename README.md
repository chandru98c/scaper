# Job Scraper Pro 🚀

A robust, service-oriented web scraper built with **Flask** and **Vanilla JS**. Designed to extract job postings from WordPress sites and other web pages with ease.

## ✨ Features

### 1. Sitemap Scraper (Core)
- **Target**: Sites with explicit `/sitemap.xml` or `/post-sitemap.xml`.
- **How it works**: Parses the sitemap for URLs within a specific date range, visits each page, and intelligently extracts the "Apply" link using a scoring algorithm.
- **Output**: Excel file download.

### 2. Auto Discovery (New!)
- **Target**: Sites *without* a sitemap (or unknown sitemap path).
- **How it works**:
    - Takes a **Homepage URL** (e.g., `https://example.com/careers`).
    - Scans the page for job articles.
    - Automatically handles **Pagination** ("Next Page", "Page 2", etc.).
    - Stops automatically when it encounters posts older than your selected range.
- **Smart Date Logic**: Select ranges like "Today", "Yesterday", or "Last 4 Days".

---

## 🛠️ Installation & Setup

1.  **Clone the Repository**
    ```bash
    git clone <your-repo-url>
    cd scaper
    ```

2.  **Install Dependencies**
    Ensure you have Python installed.
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the App**
    ```bash
    python app.py
    ```
    The application will open automatically in your browser at `http://127.0.0.1:5000`.

---

## 📂 Architecture (For Developers)

This project follows a **Service-Oriented Architecture** to ensure maintainability and scalability.

### 1. `app.py` (Controller)
- Entry point. Handles routes (`/`, `/stream`, `/stream_auto`) and SSE (Server-Sent Events) streaming.

### 2. `/services` (Business Logic)
- **`http_client.py`**: `PoliteScraper` class for handling requests with delays and User-Agent rotation.
- **`extractor.py`**: The sophisticated logic to find the "Apply Link" on a page (Scoring Strategy).
- **`sitemap_parser.py`**: Logic for Feature 1 (Sitemap Parsing).
- **`/auto_discovery`**: **Isolated Logic for Feature 2**.
    - `runner.py`: Orchestrates the pagination scraping.
    - `pagination.py`: Handles page traversal and article finding.
    - `extractor.py`: Dedicated copy of extraction logic for isolation.

### 3. `/static` (Frontend)
- **`/js`**:
    - `ui.js`: Theme, Modal, and Button logic.
    - `calendar.js`: Complex Global Date Picker logic.
    - `stream.js`: Logic for Feature 1 (SSE connection).
    - **`feature_auto.js`**: Logic for Feature 2 (Auto Discovery dates & stream).
- **`/css`**:
    - `style.css`: Tailwind overrides and custom themes.

### 4. `/templates` (HTML)
- **`index.html`**: The single-page application skeleton.
- **`/components`**: Reusable HTML chunks (e.g., `modals.html`).

---

## 🚀 Extending the Project

- **Add a new Scraper Strategy**:
    - Go to `services/extractor.py`. Add a new Scoring Rule (e.g., look for `data-apply-link` attributes).
- **Add a Database**:
    - Create `services/database.py`. Call it inside `app.py` or the runners to save data instead of creating Excel files.
