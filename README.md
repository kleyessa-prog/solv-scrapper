# Solvhealth Scraper (Python)

A Python-based Playwright web scraper for extracting data from [Solvhealth Management Portal](https://manage.solvhealth.com/).

## Features

- Extracts comprehensive page data including:
  - Page title and metadata
  - All links and their destinations
  - Headings (h1-h6)
  - Form elements and inputs
  - Tables with headers and rows
  - Buttons and interactive elements
  - Images with alt text and sources
  - Full page text content
- Automatic login with credentials
- Takes full-page screenshots for reference
- Saves data in structured JSON format
- Supports both visible and headless browser modes

## Installation

1. **Install Python dependencies:**

```bash
pip install -r requirements.txt
```

2. **Install Playwright browsers:**

```bash
playwright install
```

Or install only Chromium:

```bash
playwright install chromium
```

## Usage

### Basic Usage

Run the scraper with visible browser (recommended for first run):

```bash
python scraper.py
```

### Headless Mode

Run in headless mode (faster, no browser window):

```bash
python scraper.py --headless
```

### Fast Mode (No Slow Motion)

By default, the scraper slows down operations for visibility. To run faster:

```bash
python scraper.py --headless --no-slow
```

### Command Line Options

- `--headless`: Run browser in headless mode
- `--no-slow`: Disable slow motion (faster execution)
- `-h, --help`: Show help message

## Output

The scraper creates two directories:

1. **`scraped-data/`** - Contains JSON files with all extracted data
   - Format: `solvhealth-{timestamp}.json`
   - Includes all page elements, links, forms, tables, etc.

2. **`screenshots/`** - Contains full-page screenshots
   - `solvhealth-homepage.png` - Main page screenshot
   - `error-{timestamp}.png` - Screenshot on errors (if any)

## Example Output Structure

```json
{
  "url": "https://manage.solvhealth.com/",
  "timestamp": "2024-11-04T...",
  "title": "Page Title",
  "links": [...],
  "headings": [...],
  "forms": [...],
  "tables": [...],
  "buttons": [...],
  "images": [...],
  "textContent": "...",
  "meta": {...}
}
```

## Requirements

- Python 3.8+
- Playwright for Python
- Playwright browsers (installed with `playwright install`)

## Configuration

Login credentials are hardcoded in `scraper.py`. To change them, edit the following lines:

```python
email = "cdavis@catalyzelabs.com"
password = "MT#r6nF!!Ez6iRz"
```

For better security, consider using environment variables:

```python
import os
email = os.getenv("SOLVHEALTH_EMAIL", "cdavis@catalyzelabs.com")
password = os.getenv("SOLVHEALTH_PASSWORD", "MT#r6nF!!Ez6iRz")
```

## Notes

- The scraper automatically detects and handles login
- It waits for pages to fully load before extracting data
- Some sites may have anti-scraping measures; adjust as needed
- Respect the site's `robots.txt` and terms of service
- The scraper uses Chromium by default

## Troubleshooting

If you encounter issues:

1. **Browsers not installed**: Run `playwright install`
2. **Timeout errors**: The scraper has generous timeouts, but slow networks may need adjustment
3. **Login failures**: Check credentials and network connectivity
4. **Import errors**: Ensure all dependencies are installed with `pip install -r requirements.txt`

## License

ISC

