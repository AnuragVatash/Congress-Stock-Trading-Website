# Congress Trading Scripts Usage Guide

This guide explains how to use the HOR (House of Representatives) and Senate scripts for processing congressional trading documents.

## Overview

Both scripts now support user-configurable threading and document processing limits for better control and testing.

## House of Representatives Script

### Location

`Scripts/HOR Script/script.py`

### Running the Script

```bash
cd "Scripts/HOR Script"
python script.py
```

### User Inputs

1. **Thread Count**: Enter number of threads (1-50), default is 50
2. **Processing Limit**: Enter max documents to process (0 for no limit), default is 10

### Features

- Multithreaded PDF processing with configurable thread pool
- Rate limiting (50 requests per 10 seconds)
- LLM-based transaction extraction using OpenRouter API
- Comprehensive database storage with detailed tracking
- Progress logging and timing information

## Senate Script

### Location

`Scripts/Senate Script/scrape.py`

### Running the Script

```bash
cd "Scripts/Senate Script"
python scrape.py
```

### User Inputs

1. **Thread Count**: Enter number of threads (1-50), default is 10
2. **Processing Limit**: Enter max documents to process (0 for no limit), default is 0 (no limit)
3. **Force Rescrape**: Choose whether to force rescrape all links (y/n), default is no

### Features

- **Smart Link Optimization**: Saves scraped links and only processes new documents
- **Document Type Detection**: Automatically handles both table PTR (`/view/ptr/`) and PDF PTR (`/view/paper/`) documents
- **Correct Table Parsing**: Properly extracts member names (First + Last), filing dates, and document links from Senate table structure
- **Date-based Sorting**: Processes newest documents first for optimal efficiency
- Multithreaded document processing with configurable thread pool
- Session management with cookie persistence
- Both table scraping and LLM fallback processing
- Database storage with duplicate detection
- Progress logging and timing information

### Optimization Features

The Senate script includes several optimizations:

1. **Link Caching**: All scraped links are saved to `senate_scraped_links.json` with metadata including:

   - Document ID and URL
   - Member name and filing date
   - Document type (table vs PDF)
   - Scraping timestamp

2. **Smart Processing**: On subsequent runs, the script:

   - Loads existing scraped links
   - Checks if the newest document is already processed
   - Only scrapes new pages if needed
   - Processes documents in chronological order (newest first)
   - Stops when it hits an already-processed document

3. **Force Rescrape Option**: Users can force a complete rescrape when needed

## Flask Web Applications

Both HOR and Senate scripts include Flask web applications for document verification and management.

### HOR Flask App

```bash
cd "Scripts/HOR Script"
python app.py
```

- Runs on: http://localhost:5000
- Features: Document verification, transaction viewing, pagination

### Senate Flask App

```bash
cd "Scripts/Senate Script"
python app.py
```

- Runs on: http://localhost:5001
- Features: Document verification, transaction viewing, pagination

## Database Schema

Both scripts use identical database schemas with the following tables:

- **Members**: Congressional member information
- **Filings**: Document filing records
- **Assets**: Company and ticker information
- **Transactions**: Trading transaction details
- **API_Requests**: LLM API request tracking

**Database Files:**

- HOR Script: `congress_trades.db`
- Senate Script: `senate_trades.db`

## Configuration Options

### Thread Count Guidelines

- **I/O-bound tasks** (PDF downloads): 20-50 threads
- **CPU-bound tasks** (PDF processing): 4-8 threads
- **Default HOR**: 50 threads (optimized for rate limits)
- **Default Senate**: 10 threads (conservative default)

### Processing Limits

- Use processing limits for testing and development
- Set to 0 for production runs (no limit)
- Useful for debugging specific document issues

## Troubleshooting

### Common Issues

1. **Rate Limiting**: Reduce thread count if hitting API limits
2. **Memory Issues**: Lower thread count for large PDF processing
3. **Database Locks**: Ensure only one consumer thread for DB writes

### Logs and Debugging

- Check console output for real-time progress
- Error logs are written to console with full stack traces
- Failed documents are tracked in script-specific JSON files

**HOR Script Files:**

- `Scripts/HOR Script/generation_ids.json`
- `Scripts/HOR Script/text_extraction_failures.json`
- `Scripts/HOR Script/length_limit_failures.json`
- `Scripts/HOR Script/hor_llm_parse_errors.txt`
- `Scripts/HOR Script/hor_deleted_docs.json`

**Senate Script Files:**

- `Scripts/Senate Script/senate_scraped_links.json` (cached scraped links with metadata)
- `Scripts/Senate Script/senate_generation_ids.json`
- `Scripts/Senate Script/senate_text_extraction_failures.json`
- `Scripts/Senate Script/senate_length_limit_failures.json`
- `Scripts/Senate Script/senate_llm_parse_errors.txt`
- `Scripts/Senate Script/senate_deleted_docs.json`

## Performance Tips

1. **Optimal Thread Count**: Test different thread counts for your system
2. **Processing Limits**: Use small limits (5-10) for initial testing
3. **System Resources**: Monitor CPU and memory usage during processing
4. **Rate Limits**: Respect API rate limits to avoid blocking

## Dependencies

Install required packages:

```bash
pip install -r requirements.txt
```

Required packages include:

- Flask (web interface)
- Selenium (web scraping)
- BeautifulSoup4 (HTML parsing)
- PyMuPDF (PDF processing)
- Requests (HTTP requests)
- And others listed in requirements.txt

## Security Notes

- API keys should be stored in `gitignore/secrets.json`
- Session cookies are saved for reuse
- Database files contain sensitive trading information
- Use appropriate file permissions for data files
