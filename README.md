# Job Scraper Pro - Project Structure

This project follows a **Service-Oriented Architecture** to ensure maintainability and scalability.

## 📂 Folder Structure

### 1. `app.py` (The Controller)
- This is the entry point.
- It handles Web Routes (`/`, `/stream`, `/download`).
- **Rule:** It should contain NO business logic. It just connects the user request to the correct Service.

### 2. `/services` (The Business Logic)
This folder contains the "Brain" of the application.
- **`http_client.py`**: The `PoliteScraper` class. Handles User-Agents, Proxies (if added), and Rate Limiting.
- **`sitemap_parser.py`**: Reads XML/HTML sitemaps and finds new URLs.
- **`extractor.py`**: The sophisticated logic to find the "Apply Link" on a page. Contains the Scoring Strategy.
- **`config.py`**: Global settings (Output folders, etc).

### 3. `/static` (Frontend Assets)
- **`/js`**:
    - `ui.js`: Theme toggles, Modals, and Button states.
    - `calendar.js`: The complex Date Picker logic.
    - `stream.js`: Handles the SSE connection to the server (Start/Stop scraping).
- **`/css`**:
    - `style.css`: Custom overrides for Tailwind.

### 4. `/templates` (HTML)
- **`index.html`**: The main page skeleton.

---

## 🚀 How to Add New Features

- **"I want to Scrape a new site that has a weird layout"**:
    - Go to `services/extractor.py`. Add a new Strategy or adjust the Scoring.
- **"I want to add a 'Weekly' button"**:
    - Update `index.html` (button).
    - Update `static/js/ui.js` (button click).
    - Update `static/js/stream.js` (date calculation).
- **"I want to save results to a Database instead of Excel"**:
    - Create `services/database.py`.
    - Call it from `app.py` inside the `/stream` loop.
