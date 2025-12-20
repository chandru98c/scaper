# Job Scraper Tool

This tool scrapes job postings from a specified sitemap URL, filtering for recent posts, and extracts the "Apply Link" and other details. The results are saved into an Excel file with a timestamped filename for easy tracking.

## Features

-   **Polite & Human-Like**: Uses rotating browser profiles (Chrome, Edge, Mac/Windows) and randomized delays to mimic real human behavior and avoid detection.
-   **Smart Probability Scoring**: Uses an advanced scoring algorithm to evaluate potential links based on context (tables, labels), URL content (company name, keywords), and visual cues to pick the *single best* "Apply" link.
-   **Intelligent Filtering**: Automatically blacklists social media (Telegram, WhatsApp), video sites, and redirect services to ensure only legitimate career links are captured.
-   **Configurable**: Easily change the target sitemap, search range (days), and output folder via `config.py`.
-   **Robust Output**: Automatically creates timestamped Excel files in `scraped_data`, handling file permission errors gracefully.
-   **Robust Parsing**: Handles both standard XML sitemaps and HTML table-based sitemaps.

## Prerequisites

-   Python 3.x installed on your system.
-   `pip` (Python package installer).

## Installation

1.  **Clone or Download** this repository to your local machine.
2.  **Open a terminal** and navigate to the project folder:
    ```bash
    cd "path/to/scaper"
    ```
3.  **Install Dependencies**:
    Run the following command to install the required Python libraries:
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

All settings are managed in the `config.py` file. Open this file in any text editor to change the settings.

```python
# config.py

# 1. The Sitemap URL you want to scrape
SITEMAP_URL = 'https://freshershunt.in/post-sitemap.xml'

# 2. The folder name where Excel files will be saved
OUTPUT_FOLDER = 'scraped_data'

# 3. How many days back to search for new posts
DAYS_BACK = 5
```

## Usage

### Run the Scraper

To start the scraping process, simply run the `scraper.py` script:

```bash
python scraper.py
```

### What Happens Next?

1.  The script reads the `SITEMAP_URL` from `config.py`.
2.  It looks for posts published within the last `DAYS_BACK` days.
3.  It visits each post and tries to find the official "Apply Link".
4.  **Success**: If found, it saves the data to a new Excel file in the `scraped_data` folder.
    *   **Filename Format**: `[SiteName]_[Timestamp]_from_[StartDate]_to_[EndDate].xlsx`

## Troubleshooting

-   **`ModuleNotFoundError`**: If you see this, make sure you ran `pip install -r requirements.txt`.
-   **No results found**: increase `DAYS_BACK` in `config.py` or check if the website structure has changed.

---
**Note**: This tool deals with web scraping. Ensure you comply with the target website's `robots.txt` and Terms of Service.
