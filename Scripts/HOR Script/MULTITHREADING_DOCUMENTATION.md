# HOR Script Multithreading Documentation

## Overview

The House of Representatives (HOR) script implements a sophisticated multithreading architecture for efficient PDF processing and database operations.

## Multithreading Architecture

### Components

1. **Main Thread**

   - Coordinates the overall process
   - Scrapes PDF links from XML files
   - Manages thread pool creation

2. **Thread Pool Executor**

   - Configurable number of worker threads (1-50)
   - Default: 50 threads (based on rate limit)
   - Processes PDFs in parallel

3. **Database Consumer Thread**
   - Single thread for sequential database writes
   - Prevents database locking issues
   - Uses queue-based communication

### Data Flow

```
XML Files → Main Thread → PDF Queue → Worker Threads → Result Queue → DB Consumer → Database
```

### Key Features

- **Rate Limiting**: 50 requests per 10 seconds (configured in `rate_limiter.py`)
- **Error Handling**: Failed PDFs are logged but don't stop processing
- **Progress Tracking**: Real-time updates on processing status
- **Duplicate Prevention**: Checks existing DocIDs before processing

## Database Schema

Both HOR and Senate scripts use identical database schemas:

### Tables

1. **Members**

   ```sql
   member_id INTEGER PRIMARY KEY AUTOINCREMENT
   name TEXT NOT NULL
   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   ```

2. **Filings**

   ```sql
   filing_id INTEGER PRIMARY KEY AUTOINCREMENT
   member_id INTEGER NOT NULL
   doc_id TEXT NOT NULL UNIQUE
   url TEXT NOT NULL
   filing_date TEXT
   verified BOOLEAN DEFAULT 0
   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   FOREIGN KEY (member_id) REFERENCES Members(member_id)
   ```

3. **Assets**

   ```sql
   asset_id INTEGER PRIMARY KEY AUTOINCREMENT
   company_name TEXT NOT NULL
   ticker TEXT
   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   UNIQUE(company_name, ticker)
   ```

4. **Transactions**

   ```sql
   transaction_id INTEGER PRIMARY KEY AUTOINCREMENT
   filing_id INTEGER NOT NULL
   asset_id INTEGER NOT NULL
   owner_code TEXT
   transaction_type TEXT NOT NULL
   transaction_date TEXT
   amount_range_low INTEGER
   amount_range_high INTEGER
   raw_llm_csv_line TEXT
   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   FOREIGN KEY (filing_id) REFERENCES Filings(filing_id)
   FOREIGN KEY (asset_id) REFERENCES Assets(asset_id)
   ```

5. **API_Requests**
   ```sql
   request_id INTEGER PRIMARY KEY AUTOINCREMENT
   filing_id INTEGER NOT NULL
   doc_id TEXT NOT NULL
   generation_id TEXT
   model TEXT NOT NULL
   max_tokens INTEGER NOT NULL
   text_length INTEGER NOT NULL
   approx_tokens INTEGER NOT NULL
   finish_reason TEXT
   response_status INTEGER
   error_message TEXT
   pdf_link TEXT
   raw_text TEXT
   llm_response TEXT
   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   FOREIGN KEY (filing_id) REFERENCES Filings(filing_id)
   ```

## Usage

### Running the Script

```bash
python script.py
```

When prompted, enter the number of threads (1-50). Press Enter for default (50).

### Testing

1. **Verify Multithreading**:

   ```bash
   python verify_multithreading.py
   ```

2. **Performance Testing**:
   ```bash
   python performance_test.py
   ```

## Performance Considerations

1. **Optimal Thread Count**:

   - I/O-bound tasks (PDF downloads): 20-50 threads
   - CPU-bound tasks (PDF processing): 4-8 threads
   - Monitor system resources to avoid overload

2. **Database Performance**:

   - Single consumer thread prevents locking
   - Batch inserts could improve performance
   - Consider indexing frequently queried columns

3. **Memory Usage**:
   - Each thread holds PDF content in memory
   - Large PDFs may require memory limits
   - Queue size can be limited if needed

## Troubleshooting

1. **Database Locked Errors**:

   - Ensure only one DB consumer thread
   - Check for uncommitted transactions
   - Consider increasing database timeout

2. **Rate Limiting Issues**:

   - Adjust thread count based on API limits
   - Monitor `rate_limiter.py` effectiveness
   - Consider exponential backoff

3. **Memory Issues**:
   - Reduce thread count
   - Process PDFs in chunks
   - Clear processed data promptly

## Future Improvements

1. **Adaptive Threading**:

   - Dynamically adjust thread count based on load
   - Monitor system resources in real-time
   - Implement thread pool resizing

2. **Distributed Processing**:

   - Support multiple machines
   - Use message queues (RabbitMQ, Redis)
   - Implement job distribution

3. **Enhanced Monitoring**:
   - Real-time dashboard
   - Performance metrics collection
   - Error rate tracking
