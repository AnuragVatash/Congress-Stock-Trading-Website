import sqlite3
import os
import datetime
import re # For parsing asset description
import logging
from common.db_schema import create_tables

DB_FILE = 'congress_trades.db'  # New database file name

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

def get_db_connection(db_path=None):
    """Creates a database connection and ensures foreign keys are enabled."""
    if not db_path:
        db_path = os.path.join(os.path.dirname(__file__), DB_FILE)
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn

# The create_tables function is now imported from common.db_schema

def _format_date_to_iso(date_str_mmddyyyy):
    """Converts MM/DD/YYYY or MM-DD-YYYY to YYYY-MM-DD. Returns None if parsing fails."""
    if not date_str_mmddyyyy:
        return None
    try:
        # Normalize separators to '/'
        normalized_date_str = date_str_mmddyyyy.replace('-', '/')
        parts = normalized_date_str.split('/')
        if len(parts) == 3:
            month, day, year = parts
            if len(year) == 2:
                year = "20" + year # Assuming 21st century
            return f"{year}-{int(month):02d}-{int(day):02d}"
        return None # Invalid format
    except ValueError:
        logging.warning(f"Could not parse date: {date_str_mmddyyyy}")
        return None

def _get_or_create_member(cursor, member_name):
    """Gets MemberID if member exists, else creates and returns new MemberID."""
    cursor.execute("SELECT member_id FROM Members WHERE name = ?", (member_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    else:
        cursor.execute("INSERT INTO Members (name) VALUES (?)", (member_name,))
        return cursor.lastrowid

def _get_or_create_asset(cursor, company_name, ticker):
    """Gets AssetID if asset exists, else creates and returns new AssetID."""
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

def process_and_store_scraped_data(member_name: str, doc_id: str, url: str, llm_transactions: list, db_path=None):
    """
    Processes a list of transactions from a single scraped PDF (DocID) and stores them.
    Args:
        member_name (str): Name of the member filing the report.
        doc_id (str): The unique document ID of the filing.
        url (str): The URL of the scraped PDF.
        llm_transactions (list): A list of transaction dictionaries.
                                 Each dict should be like the example structure shown
                                 in the thought process (parsed by parse_llm_transactions).
    Returns:
        int: Number of transactions successfully inserted for this document.
    """
    if not llm_transactions:
        logging.info(f"No transactions provided for DocID {doc_id}, Member {member_name}. Skipping.")
        return 0

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    inserted_count = 0

    try:
        # 1. Get or Create Member
        member_id = _get_or_create_member(cursor, member_name)

        # 2. Check if Filing already exists (by doc_id)
        cursor.execute("SELECT filing_id FROM Filings WHERE doc_id = ?", (doc_id,))
        existing_filing = cursor.fetchone()
        if existing_filing:
            filing_id = existing_filing[0]
            logging.info(f"Filing DocID {doc_id} already exists (filing_id: {filing_id}). Using existing filing for transaction storage.")
            
            # Check if transactions already exist for this filing
            cursor.execute("SELECT COUNT(*) FROM Transactions WHERE filing_id = ?", (filing_id,))
            existing_tx_count = cursor.fetchone()[0]
            if existing_tx_count > 0:
                logging.info(f"Filing {doc_id} already has {existing_tx_count} transactions. Skipping to avoid duplicates.")
                return 0
        else:
            # 3. Create Filing
            # Assuming notification_date_str is consistent for all transactions in the list
            # and represents the filing date.
            filing_date_iso = _format_date_to_iso(llm_transactions[0].get('notification_date_str'))
            if not filing_date_iso:
                logging.warning(f"Could not determine a valid filing date for DocID {doc_id}. Using NULL.")

            cursor.execute("INSERT INTO Filings (doc_id, member_id, url, filing_date) VALUES (?, ?, ?, ?)",
                           (doc_id, member_id, url, filing_date_iso))
            filing_id = cursor.lastrowid

        # 4. Process each transaction
        logging.info(f"[{doc_id}] Processing {len(llm_transactions)} transactions for database insertion")
        
        for i, tx_data in enumerate(llm_transactions):
            logging.debug(f"[{doc_id}] Processing transaction {i+1}: {tx_data}")
            
            company_name = tx_data.get('company_name')
            ticker = tx_data.get('ticker')
            if not company_name:
                logging.warning(f"Skipping transaction {i+1} for DocID {doc_id} due to missing company name: {tx_data.get('raw_llm_line')}")
                continue

            asset_id = _get_or_create_asset(cursor, company_name, ticker)

            transaction_date_iso = _format_date_to_iso(tx_data.get('transaction_date_str'))
            if not transaction_date_iso:
                logging.warning(f"Skipping transaction {i+1} for DocID {doc_id} due to invalid transaction date '{tx_data.get('transaction_date_str')}': {tx_data.get('raw_llm_line')}")
                continue

            transaction_type_full = tx_data.get('transaction_type_full', "Unknown") # Ensure parse_llm_transactions provides this

            logging.info(f"[{doc_id}] Inserting transaction {i+1}: {company_name} ({ticker}) - {transaction_type_full} on {transaction_date_iso}")

            cursor.execute('''
                INSERT INTO Transactions (
                    filing_id, asset_id, owner_code, transaction_type,
                    transaction_date, amount_range_low, amount_range_high, raw_llm_csv_line
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                filing_id,
                asset_id,
                tx_data.get('owner_code'),
                transaction_type_full,
                transaction_date_iso,
                tx_data.get('amount_low'),
                tx_data.get('amount_high'),
                tx_data.get('raw_llm_line')
            ))
            inserted_count += 1

        conn.commit()
        logging.info(f"Successfully processed and stored {inserted_count} transactions for DocID {doc_id}, Member: {member_name}.")

    except sqlite3.Error as e:
        conn.rollback()
        logging.error(f"Database error for DocID {doc_id}, Member {member_name}: {e}. Rolled back changes for this document.")
        inserted_count = 0 # Reset count on error for this doc
    except Exception as e:
        conn.rollback()
        logging.error(f"Unexpected error processing DocID {doc_id}, Member {member_name}: {e}. Rolled back changes for this document.")
        inserted_count = 0
    finally:
        conn.close()

    return inserted_count

def get_existing_doc_ids(db_path=None):
    """Retrieves a set of all DocIDs currently stored in the Filings table."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT doc_id FROM Filings")
        doc_ids = {row[0] for row in cursor.fetchall()}
    except sqlite3.OperationalError as e:
        logging.error(f"Error fetching existing DocIDs from {db_path}: {e}")
        doc_ids = set()
    finally:
        conn.close()
    return doc_ids