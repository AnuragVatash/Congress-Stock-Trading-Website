# Master Congressional Trading Data Processor

## Overview

The Master Congressional Trading Data Processor is a comprehensive script that integrates data collection from both House and Senate sources, applying an enhanced database schema with member profile information to your Combined Copy Mod Curr database.

## Features

- **Integrated Data Collection**: Combines House (2025.xml FD file processing) and Senate (web scraping) approaches
- **Enhanced Database Schema**: Adds member profile fields (photo_url, party, state, chamber)
- **Smart Member Enrichment**: Automatically populates member information with party affiliation, state, and chamber
- **Robust Error Handling**: Graceful handling of missing modules and data sources
- **Comprehensive Logging**: Detailed logging of all operations and statistics
- **Flexible Operation Modes**: Run House-only, Senate-only, or combined processing

## Prerequisites

1. **Database**: Ensure your `Combined Trades Mod Curr.db` exists in the `/db` directory
2. **Scripts**: Maintain the existing Scripts directory structure:
   ```
   Scripts/
   ├── HOR Script/
   │   ├── scrapeLinks.py
   │   ├── db_processor.py
   │   └── ...
   ├── Senate Script/
   │   ├── combined_scraper.py
   │   ├── senate_db_processor.py
   │   └── ...
   └── common/
       ├── db_schema.py
       └── ...
   ```
3. **Dependencies**: Python packages required by your existing scripts

## Installation & Setup

1. **Place the Script**: Put `master_data_processor.py` in your project root directory
2. **Member Data**: The script includes `member_enrichment_data.json` with common member information
3. **Permissions**: Ensure write access to the database and temp file creation

## Usage

### Basic Usage

```bash
# Process both House and Senate data with default database
python master_data_processor.py

# Specify a different database
python master_data_processor.py --db "path/to/your/database.db"
```

### Advanced Options

```bash
# Process only House data (2025.xml FD sources)
python master_data_processor.py --house-only

# Process only Senate data (web scraping)
python master_data_processor.py --senate-only

# Dry run (no database changes)
python master_data_processor.py --dry-run

# Combine options
python master_data_processor.py --db "db/Combined Trades Mod Curr.db" --house-only
```

## What the Script Does

### 1. Database Schema Upgrade

- Adds enhanced member fields to existing database:
  - `photo_url` - URL to member's photo
  - `party` - Political party (Democrat, Republican, Independent)
  - `state` - State represented
  - `chamber` - House or Senate
- Creates performance indexes for better query speed

### 2. Member Information Enrichment

- Loads member data from `member_enrichment_data.json`
- Enriches existing database members with party, state, chamber info
- Caches member information for efficient processing

### 3. House Data Collection

- Uses existing `scrapeLinks.py` functionality
- Processes 2025.xml FD file for new documents
- Applies member enrichment to new filings
- Stores data in enhanced schema format

### 4. Senate Data Collection

- Integrates with existing `combined_scraper.py`
- Performs web scraping for new Senate filings
- Applies member enrichment to new filings
- Stores data in enhanced schema format

### 5. Data Merging & Cleanup

- Merges collected data into target database
- Prevents duplicate entries
- Updates existing members with enhanced information
- Maintains data integrity with foreign key constraints

## Output & Logging

The script generates comprehensive logs including:

- **Operation Progress**: Step-by-step processing updates
- **Statistics**: Documents processed, members enriched, errors encountered
- **Database Changes**: Schema updates, record additions/updates
- **Error Handling**: Detailed error messages and recovery actions

### Sample Output

```
🚀 Starting Master Congressional Trading Data Processing
============================================================
🔧 Upgrading database schema with member profile fields...
✅ Database schema upgrade completed
📚 Loading member information cache...
✅ Loaded 25 members from enrichment file
📊 Total member cache size: 25 records
🏛️ Starting House data collection (2025.xml FD processing)...
🔍 Found 15 new House documents to process
📄 Processed House doc DOC123456 for Nancy Pelosi
✅ House data collection completed: 15 documents
🏛️ Starting Senate data collection (web scraping approach)...
✅ Senate data collection completed: 5 documents
🔄 Merging collected data into target database...
➕ Added member: John Smith (House)
🔄 Enriched member: Jane Doe
✅ Data merge completed: 8 members enriched

📊 MASTER PROCESSING REPORT
============================================================
🏛️ House documents processed: 15
🏛️ Senate documents processed: 5
👥 Members enriched: 8
💰 Total transactions added: 0
✅ No errors encountered

📈 Final Database Statistics:
   Members: 245 total, 156 enriched (63.7%)
   Transactions: 15,432
   Assets: 3,241
============================================================
```

## Enhanced Database Schema

After running the script, your database will have enhanced member information:

```sql
-- Members table now includes:
SELECT member_id, name, party, state, chamber, photo_url
FROM Members
WHERE party IS NOT NULL;

-- Example results:
-- member_id | name           | party      | state        | chamber | photo_url
-- 1         | Nancy Pelosi   | Democrat   | California   | House   | https://...
-- 2         | Ted Cruz       | Republican | Texas        | Senate  | https://...
```

## Customization

### Adding More Members

Edit `member_enrichment_data.json` to add more member information:

```json
{
  "house_members": {
    "new member name": {
      "party": "Democrat",
      "state": "California",
      "chamber": "House",
      "photo_url": "https://..."
    }
  }
}
```

### Adjusting Processing Limits

Modify the script to change processing limits:

```python
# In run_house_data_collection()
for pdf_info in results_from_scraper[:50]:  # Increase from 10 to 50
```

## Error Handling

The script handles various error conditions gracefully:

- **Missing Script Modules**: Continues with available functionality
- **Database Access Issues**: Reports errors and continues where possible
- **Network/Scraping Failures**: Logs errors and processes available data
- **Schema Conflicts**: Safely handles existing enhanced columns

## Maintenance

### Regular Updates

1. **Update Member Data**: Regularly update `member_enrichment_data.json` with new members
2. **Monitor Logs**: Check log files for processing issues or failures
3. **Database Cleanup**: Periodically run the existing cleanup scripts in `/db`
4. **Performance Monitoring**: Monitor database size and query performance

### Troubleshooting

**Common Issues:**

1. **Import Errors**: Ensure Scripts directory structure is intact
2. **Database Locked**: Close other applications accessing the database
3. **Insufficient Permissions**: Ensure write access to database and temp directories
4. **Network Issues**: Check internet connectivity for Senate web scraping

## Integration with Existing Scripts

The master script is designed to work alongside your existing infrastructure:

- **Preserves Original Scripts**: Does not modify existing House/Senate scripts
- **Temporary Databases**: Uses temporary databases to avoid conflicts
- **Configurable Database Paths**: Works with your existing database files
- **Backward Compatible**: Enhanced schema is backward compatible

## Support

For issues or questions:

1. Check the log files for detailed error information
2. Verify all prerequisites are met
3. Test with `--dry-run` first to identify potential issues
4. Run individual components (`--house-only`, `--senate-only`) to isolate problems

---

**Note**: This script is designed to enhance your existing congressional trading data infrastructure while preserving the functionality of your current House and Senate processing scripts.
