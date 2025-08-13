# Daily PTR Checker System

An automated system for checking, processing, and syncing House of Representatives Periodic Transaction Reports (PTRs) to Supabase.

## Features

- **Automated Web Scraping**: Scrapes the House Financial Disclosures website for new PTR filings
- **PDF Processing**: Downloads and extracts transaction data from PTR PDFs using LLM (OpenRouter API)
- **Database Storage**: Stores data in local SQLite and syncs to Supabase PostgreSQL
- **Daily Scheduling**: Can run automatically on a daily schedule
- **Parallel Processing**: Processes multiple filings concurrently for efficiency
- **Error Handling**: Tracks failed extractions and retries

## System Components

1. **`house_scraper.py`** - Selenium-based web scraper for House disclosures website
2. **`pdf_processor.py`** - PDF download and LLM-based transaction extraction
3. **`supabase_integration.py`** - Syncs local data to Supabase cloud database
4. **`daily_ptr_checker.py`** - Main orchestrator script that coordinates everything

## Installation

### Prerequisites

- Python 3.8+
- Chrome browser installed
- ChromeDriver (for Selenium)
- Tesseract OCR (optional, for scanned PDFs)

### Setup

1. Install Python dependencies:
```bash
cd Scripts
pip install -r requirements.txt
```

2. Install ChromeDriver:
```bash
# On Ubuntu/Debian
sudo apt-get install chromium-chromedriver

# On macOS with Homebrew
brew install --cask chromedriver

# On Windows
# Download from https://chromedriver.chromium.org/
```

3. Configure environment variables in `.env`:
```env
# OpenRouter API Key (required for LLM processing)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Supabase Configuration (optional, for cloud sync)
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_anon_key_here
DATABASE_URL=your_database_url_here
```

## Usage

### Run Once (Manual Check)

Check for new PTRs and process them:
```bash
python daily_ptr_checker.py
```

### Run with Options

```bash
# Check specific year
python daily_ptr_checker.py --year 2025

# Limit pages to scrape (for testing)
python daily_ptr_checker.py --max-pages 5

# Limit number of filings to process
python daily_ptr_checker.py --max-filings 10

# Use more parallel workers
python daily_ptr_checker.py --workers 10

# Show browser window (not headless)
python daily_ptr_checker.py --no-headless

# Skip Supabase sync (local only)
python daily_ptr_checker.py --no-supabase
```

### Schedule Daily Runs

Run automatically every day at 9:00 AM:
```bash
python daily_ptr_checker.py --schedule
```

Run at a custom time:
```bash
python daily_ptr_checker.py --schedule --schedule-time 14:30
```

### Test Individual Components

Test the web scraper:
```bash
python house_scraper.py
```

Test PDF processing:
```bash
python pdf_processor.py
```

Test Supabase sync:
```bash
python supabase_integration.py
```

## Database Schema

### SQLite Tables (Local)

- **Members**: Congressional members information
- **Filings**: PTR filing metadata
- **Assets**: Companies and tickers
- **Transactions**: Individual stock transactions
- **API_Requests**: LLM API call logs
- **StockPrices**: Historical price data

### Supabase Tables (Cloud)

Same structure as SQLite, with PostgreSQL-specific optimizations and indexes.

## Data Flow

1. **Scraping**: The system navigates to the House disclosures website, searches for PTRs by year, and extracts filing metadata
2. **Filtering**: Compares scraped doc_ids against existing database to find new filings
3. **Processing**: 
   - Downloads PDF files
   - Extracts text using PyMuPDF (with OCR fallback)
   - Sends text to OpenRouter LLM API for transaction extraction
   - Parses LLM response into structured data
4. **Storage**: Saves to local SQLite database
5. **Sync**: Uploads new data to Supabase for web application access

## Monitoring

The system creates logs in `daily_ptr_checker.log` with detailed information about:
- Filings scraped
- Processing success/failures
- API calls
- Sync status

## Error Handling

- **Text Extraction Failures**: Tracked in `text_extraction_failures.json`
- **Generation IDs**: Stored in `generation_ids.json` for API tracking
- **Failed Filings**: Logged but not retried in same run
- **Timeout Protection**: 5-minute timeout per filing

## Performance

- Processes 5-10 filings per minute (depending on PDF size and complexity)
- Uses parallel processing (default 5 workers)
- Caches existing doc_ids to avoid reprocessing

## Troubleshooting

### ChromeDriver Issues
- Ensure ChromeDriver version matches your Chrome browser version
- Add ChromeDriver to PATH or specify path in code

### API Rate Limits
- OpenRouter has rate limits; adjust `--workers` if hitting limits
- The system includes automatic rate limiting

### PDF Extraction Failures
- Some PDFs may be scanned images requiring OCR
- Install Tesseract: `sudo apt-get install tesseract-ocr`

### Supabase Connection
- Verify credentials in `.env`
- Check firewall/network settings
- Ensure database tables are created (run `create_supabase_tables()`)

## Development

### Adding New Features

1. **New Filing Types**: Modify `extract_ptr_filings_from_page()` in `house_scraper.py`
2. **Different LLM Models**: Update model in `call_llm_api()` in `pdf_processor.py`
3. **Additional Data Fields**: Update database schema in `common/db_schema.py`

### Testing

Run tests with pytest:
```bash
pytest test_daily_ptr_checker.py -v
```

## Deployment

### Linux Server (Cron)

Add to crontab for daily runs:
```bash
# Run every day at 9 AM
0 9 * * * cd /path/to/Scripts && /usr/bin/python3 daily_ptr_checker.py >> cron.log 2>&1
```

### Docker Container

Build and run in Docker:
```bash
docker build -t ptr-checker .
docker run -d --name ptr-checker-daily ptr-checker
```

### Cloud Functions

Can be adapted for AWS Lambda, Google Cloud Functions, or Azure Functions with minimal modifications.

## License

This project is for educational and transparency purposes.

## Support

For issues or questions, please check the logs first:
- `daily_ptr_checker.log` - Main execution log
- `text_extraction_failures.json` - PDFs that failed text extraction
- `house_scraped_filings.json` - Latest scrape results