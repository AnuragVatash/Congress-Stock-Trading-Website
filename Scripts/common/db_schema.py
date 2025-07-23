"""
Shared database schema utilities for congressional trading document processing.
Ensures identical database structure between HOR and Senate scripts.
"""
import sqlite3
import logging
from typing import Optional

def create_tables(conn: sqlite3.Connection) -> None:
    """
    Create the standardized database tables for congressional trading data.
    This ensures identical schema between HOR and Senate scripts.
    
    Args:
        conn: SQLite database connection
    """
    cursor = conn.cursor()
    
    # Create Members table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Members (
            member_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            photo_url TEXT,
            party TEXT,
            state TEXT,
            chamber TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create Filings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Filings (
            filing_id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER NOT NULL,
            doc_id TEXT NOT NULL UNIQUE,
            url TEXT NOT NULL,
            filing_date TEXT,
            verified BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (member_id) REFERENCES Members(member_id)
        )
    ''')
    
    # Create Assets table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Assets (
            asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            ticker TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(company_name, ticker)
        )
    ''')
    
    # Create Transactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filing_id INTEGER NOT NULL,
            asset_id INTEGER NOT NULL,
            owner_code TEXT,
            transaction_type TEXT NOT NULL,
            transaction_date TEXT,
            amount_range_low INTEGER,
            amount_range_high INTEGER,
            raw_llm_csv_line TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (filing_id) REFERENCES Filings(filing_id),
            FOREIGN KEY (asset_id) REFERENCES Assets(asset_id)
        )
    ''')

    # Create API_Requests table with all necessary columns
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS API_Requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filing_id INTEGER NOT NULL,
            doc_id TEXT NOT NULL,
            generation_id TEXT,
            model TEXT NOT NULL,
            max_tokens INTEGER NOT NULL,
            text_length INTEGER NOT NULL,
            approx_tokens INTEGER NOT NULL,
            finish_reason TEXT,
            response_status INTEGER,
            error_message TEXT,
            pdf_link TEXT,
            raw_text TEXT,
            llm_response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (filing_id) REFERENCES Filings(filing_id)
        )
    ''')
    
    # Create StockPrices table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS StockPrices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume INTEGER NOT NULL,
            adj_open REAL,
            adj_high REAL,
            adj_low REAL,
            adj_close REAL,
            adj_volume INTEGER,
            split_factor REAL DEFAULT 1.0,
            dividend REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP,
            UNIQUE(ticker, date)
        )
    ''')

    conn.commit()
    logging.info("Database tables ensured/created with standardized schema")

def get_or_create_member(cursor: sqlite3.Cursor, member_name: str) -> int:
    """
    Gets MemberID if member exists, else creates and returns new MemberID.
    
    Args:
        cursor: Database cursor
        member_name: Name of the congressional member
        
    Returns:
        Member ID
    """
    cursor.execute("SELECT member_id FROM Members WHERE name = ?", (member_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    else:
        cursor.execute("INSERT INTO Members (name) VALUES (?)", (member_name,))
        return cursor.lastrowid

def get_or_create_asset(cursor: sqlite3.Cursor, company_name: str, ticker: Optional[str]) -> int:
    """
    Gets AssetID if asset exists, else creates and returns new AssetID.
    
    Args:
        cursor: Database cursor
        company_name: Name of the company
        ticker: Stock ticker symbol (may be None)
        
    Returns:
        Asset ID
    """
    # Normalize ticker: empty string to NULL for DB consistency
    ticker_to_db = ticker if ticker and ticker.strip() else None

    if ticker_to_db:
        cursor.execute("SELECT asset_id FROM Assets WHERE company_name = ? AND ticker = ?", (company_name, ticker_to_db))
    else: # Search for company_name where ticker IS NULL
        cursor.execute("SELECT asset_id FROM Assets WHERE company_name = ? AND ticker IS NULL", (company_name,))

    row = cursor.fetchone()
    if row:
        return row[0]
    else:
        cursor.execute("INSERT INTO Assets (company_name, ticker) VALUES (?, ?)", (company_name, ticker_to_db))
        return cursor.lastrowid

def get_existing_doc_ids(conn: sqlite3.Connection) -> set:
    """
    Retrieves a set of all DocIDs currently stored in the Filings table.
    
    Args:
        conn: Database connection
        
    Returns:
        Set of existing document IDs
    """
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT doc_id FROM Filings")
    doc_ids = {row[0] for row in cursor.fetchall()}
    return doc_ids

def verify_schema_consistency(conn: sqlite3.Connection) -> bool:
    """
    Verify that the database schema matches the expected structure.
    
    Args:
        conn: Database connection
        
    Returns:
        True if schema is consistent, False otherwise
    """
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    
    required_tables = {'Members', 'Filings', 'Assets', 'Transactions', 'API_Requests', 'StockPrices'}
    
    if not required_tables.issubset(tables):
        missing = required_tables - tables
        logging.error(f"Missing required tables: {missing}")
        return False
    
    # Verify table schemas
    table_schemas = {
        'Members': ['member_id', 'name', 'photo_url', 'party', 'state', 'chamber', 'created_at'],
        'Filings': ['filing_id', 'member_id', 'doc_id', 'url', 'filing_date', 'verified', 'created_at'],
        'Assets': ['asset_id', 'company_name', 'ticker', 'created_at'],
        'Transactions': ['transaction_id', 'filing_id', 'asset_id', 'owner_code', 'transaction_type', 
                        'transaction_date', 'amount_range_low', 'amount_range_high', 'raw_llm_csv_line', 'created_at'],
        'API_Requests': ['request_id', 'filing_id', 'doc_id', 'generation_id', 'model', 'max_tokens',
                        'text_length', 'approx_tokens', 'finish_reason', 'response_status', 'error_message',
                        'pdf_link', 'raw_text', 'llm_response', 'created_at'],
        'StockPrices': ['id', 'ticker', 'date', 'open', 'high', 'low', 'close', 'volume', 'adj_open', 'adj_high', 'adj_low', 'adj_close', 'adj_volume', 'split_factor', 'dividend', 'created_at', 'updated_at']
    }
    
    for table, expected_columns in table_schemas.items():
        cursor.execute(f"PRAGMA table_info({table})")
        actual_columns = [row[1] for row in cursor.fetchall()]
        
        if not set(expected_columns).issubset(set(actual_columns)):
            missing = set(expected_columns) - set(actual_columns)
            logging.error(f"Table '{table}' missing columns: {missing}")
            return False
    
    logging.info("Database schema verification passed")
    return True 