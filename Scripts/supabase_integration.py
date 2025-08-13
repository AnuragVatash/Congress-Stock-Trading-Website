"""
Supabase Integration Module
Handles syncing congressional trading data from local SQLite to Supabase PostgreSQL
"""

import os
import logging
import json
from typing import List, Dict, Optional, Set
from datetime import datetime
from supabase import create_client, Client
import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv
import sqlite3

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SupabaseSync:
    """Handles syncing data from local SQLite to Supabase"""
    
    def __init__(self, sqlite_db_path: str = None):
        """
        Initialize Supabase connection
        
        Args:
            sqlite_db_path: Path to local SQLite database
        """
        # Get Supabase credentials from environment
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        self.database_url = os.getenv('DATABASE_URL')
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env file")
            
        # Initialize Supabase client
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        
        # SQLite database path
        if sqlite_db_path:
            self.sqlite_db_path = sqlite_db_path
        else:
            self.sqlite_db_path = os.path.join(os.path.dirname(__file__), 'congressional_trades.db')
            
        logger.info("Supabase integration initialized")
        
    def create_supabase_tables(self):
        """Create tables in Supabase if they don't exist"""
        
        # Use direct PostgreSQL connection for DDL operations
        if not self.database_url:
            logger.error("DATABASE_URL not set, cannot create tables")
            return False
            
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            
            # Create Members table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS members (
                    member_id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    photo_url TEXT,
                    party TEXT,
                    state TEXT,
                    chamber TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create Filings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS filings (
                    filing_id SERIAL PRIMARY KEY,
                    member_id INTEGER NOT NULL REFERENCES members(member_id),
                    doc_id TEXT NOT NULL UNIQUE,
                    url TEXT NOT NULL,
                    filing_date TEXT,
                    filing_type TEXT,
                    verified BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create Assets table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS assets (
                    asset_id SERIAL PRIMARY KEY,
                    company_name TEXT NOT NULL,
                    ticker TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(company_name, ticker)
                )
            ''')
            
            # Create Transactions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id SERIAL PRIMARY KEY,
                    filing_id INTEGER NOT NULL REFERENCES filings(filing_id),
                    asset_id INTEGER NOT NULL REFERENCES assets(asset_id),
                    owner_code TEXT,
                    transaction_type TEXT NOT NULL,
                    transaction_date TEXT,
                    amount_range_low INTEGER,
                    amount_range_high INTEGER,
                    raw_llm_csv_line TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create API_Requests table for tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_requests (
                    request_id SERIAL PRIMARY KEY,
                    filing_id INTEGER NOT NULL REFERENCES filings(filing_id),
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create StockPrices table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_prices (
                    id SERIAL PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    date DATE NOT NULL,
                    open DECIMAL(10, 2) NOT NULL,
                    high DECIMAL(10, 2) NOT NULL,
                    low DECIMAL(10, 2) NOT NULL,
                    close DECIMAL(10, 2) NOT NULL,
                    volume BIGINT NOT NULL,
                    adj_open DECIMAL(10, 2),
                    adj_high DECIMAL(10, 2),
                    adj_low DECIMAL(10, 2),
                    adj_close DECIMAL(10, 2),
                    adj_volume BIGINT,
                    split_factor DECIMAL(10, 4) DEFAULT 1.0,
                    dividend DECIMAL(10, 4) DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    UNIQUE(ticker, date)
                )
            ''')
            
            # Create index for better query performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_filings_doc_id ON filings(doc_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_filing_id ON transactions(filing_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_asset_id ON transactions(asset_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_prices_ticker_date ON stock_prices(ticker, date)')
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info("Supabase tables created/verified successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error creating Supabase tables: {e}")
            return False
            
    def get_existing_doc_ids(self) -> Set[str]:
        """
        Get set of doc_ids already in Supabase
        
        Returns:
            Set of existing doc_ids
        """
        try:
            response = self.supabase.table('filings').select('doc_id').execute()
            doc_ids = {row['doc_id'] for row in response.data}
            logger.info(f"Found {len(doc_ids)} existing doc_ids in Supabase")
            return doc_ids
            
        except Exception as e:
            logger.error(f"Error fetching existing doc_ids from Supabase: {e}")
            return set()
            
    def sync_members(self) -> int:
        """
        Sync members from SQLite to Supabase
        
        Returns:
            Number of members synced
        """
        try:
            # Connect to SQLite
            sqlite_conn = sqlite3.connect(self.sqlite_db_path)
            sqlite_cursor = sqlite_conn.cursor()
            
            # Get all members from SQLite
            sqlite_cursor.execute("SELECT name, photo_url, party, state, chamber FROM Members")
            members = sqlite_cursor.fetchall()
            
            synced_count = 0
            
            for member in members:
                try:
                    # Insert or update member in Supabase
                    data = {
                        'name': member[0],
                        'photo_url': member[1],
                        'party': member[2],
                        'state': member[3],
                        'chamber': member[4]
                    }
                    
                    # Upsert (insert or update) member
                    self.supabase.table('members').upsert(data, on_conflict='name').execute()
                    synced_count += 1
                    
                except Exception as e:
                    logger.warning(f"Error syncing member {member[0]}: {e}")
                    
            sqlite_conn.close()
            logger.info(f"Synced {synced_count} members to Supabase")
            return synced_count
            
        except Exception as e:
            logger.error(f"Error syncing members: {e}")
            return 0
            
    def sync_new_filings(self, doc_ids: Optional[List[str]] = None) -> int:
        """
        Sync new filings and their transactions from SQLite to Supabase
        
        Args:
            doc_ids: List of specific doc_ids to sync (None for all new)
            
        Returns:
            Number of filings synced
        """
        try:
            # Get existing doc_ids in Supabase
            existing_doc_ids = self.get_existing_doc_ids()
            
            # Connect to SQLite
            sqlite_conn = sqlite3.connect(self.sqlite_db_path)
            sqlite_cursor = sqlite_conn.cursor()
            
            # Build query for new filings
            if doc_ids:
                # Sync specific doc_ids that aren't already in Supabase
                new_doc_ids = [doc_id for doc_id in doc_ids if doc_id not in existing_doc_ids]
                if not new_doc_ids:
                    logger.info("No new filings to sync")
                    return 0
                placeholders = ','.join('?' * len(new_doc_ids))
                query = f'''
                    SELECT f.doc_id, f.url, f.filing_date, f.verified, m.name
                    FROM Filings f
                    JOIN Members m ON f.member_id = m.member_id
                    WHERE f.doc_id IN ({placeholders})
                '''
                sqlite_cursor.execute(query, new_doc_ids)
            else:
                # Sync all new filings
                query = '''
                    SELECT f.doc_id, f.url, f.filing_date, f.verified, m.name
                    FROM Filings f
                    JOIN Members m ON f.member_id = m.member_id
                '''
                sqlite_cursor.execute(query)
                
            filings = sqlite_cursor.fetchall()
            
            # Filter out already existing filings
            new_filings = [f for f in filings if f[0] not in existing_doc_ids]
            
            if not new_filings:
                logger.info("No new filings to sync")
                sqlite_conn.close()
                return 0
                
            synced_count = 0
            
            for filing in new_filings:
                try:
                    doc_id = filing[0]
                    
                    # Get member_id from Supabase
                    member_response = self.supabase.table('members').select('member_id').eq('name', filing[4]).execute()
                    if not member_response.data:
                        logger.warning(f"Member {filing[4]} not found in Supabase, skipping filing {doc_id}")
                        continue
                        
                    member_id = member_response.data[0]['member_id']
                    
                    # Insert filing
                    filing_data = {
                        'member_id': member_id,
                        'doc_id': doc_id,
                        'url': filing[1],
                        'filing_date': filing[2],
                        'verified': bool(filing[3]),
                        'filing_type': 'PTR'  # House PTRs
                    }
                    
                    filing_response = self.supabase.table('filings').insert(filing_data).execute()
                    filing_id = filing_response.data[0]['filing_id']
                    
                    # Sync transactions for this filing
                    self._sync_filing_transactions(sqlite_cursor, doc_id, filing_id)
                    
                    synced_count += 1
                    logger.debug(f"Synced filing {doc_id}")
                    
                except Exception as e:
                    logger.error(f"Error syncing filing {doc_id}: {e}")
                    
            sqlite_conn.close()
            logger.info(f"Synced {synced_count} new filings to Supabase")
            return synced_count
            
        except Exception as e:
            logger.error(f"Error syncing filings: {e}")
            return 0
            
    def _sync_filing_transactions(self, sqlite_cursor, doc_id: str, filing_id: int):
        """
        Sync transactions for a specific filing
        
        Args:
            sqlite_cursor: SQLite cursor
            doc_id: Document ID
            filing_id: Supabase filing ID
        """
        try:
            # Get transactions from SQLite
            query = '''
                SELECT a.company_name, a.ticker, t.owner_code, t.transaction_type,
                       t.transaction_date, t.amount_range_low, t.amount_range_high,
                       t.raw_llm_csv_line
                FROM Transactions t
                JOIN Filings f ON t.filing_id = f.filing_id
                JOIN Assets a ON t.asset_id = a.asset_id
                WHERE f.doc_id = ?
            '''
            sqlite_cursor.execute(query, (doc_id,))
            transactions = sqlite_cursor.fetchall()
            
            for transaction in transactions:
                # Get or create asset in Supabase
                asset_data = {
                    'company_name': transaction[0],
                    'ticker': transaction[1]
                }
                
                # Try to get existing asset
                asset_response = self.supabase.table('assets').select('asset_id').eq(
                    'company_name', transaction[0]
                ).eq('ticker', transaction[1] or '').execute()
                
                if asset_response.data:
                    asset_id = asset_response.data[0]['asset_id']
                else:
                    # Create new asset
                    asset_response = self.supabase.table('assets').insert(asset_data).execute()
                    asset_id = asset_response.data[0]['asset_id']
                    
                # Insert transaction
                transaction_data = {
                    'filing_id': filing_id,
                    'asset_id': asset_id,
                    'owner_code': transaction[2],
                    'transaction_type': transaction[3],
                    'transaction_date': transaction[4],
                    'amount_range_low': transaction[5],
                    'amount_range_high': transaction[6],
                    'raw_llm_csv_line': transaction[7]
                }
                
                self.supabase.table('transactions').insert(transaction_data).execute()
                
            logger.debug(f"Synced {len(transactions)} transactions for filing {doc_id}")
            
        except Exception as e:
            logger.error(f"Error syncing transactions for filing {doc_id}: {e}")
            
    def sync_api_requests(self, doc_ids: Optional[List[str]] = None) -> int:
        """
        Sync API request logs to Supabase for tracking
        
        Args:
            doc_ids: List of specific doc_ids to sync (None for all)
            
        Returns:
            Number of API requests synced
        """
        try:
            # Connect to SQLite
            sqlite_conn = sqlite3.connect(self.sqlite_db_path)
            sqlite_cursor = sqlite_conn.cursor()
            
            # Build query
            if doc_ids:
                placeholders = ','.join('?' * len(doc_ids))
                query = f'''
                    SELECT a.*, f.filing_id as sqlite_filing_id
                    FROM API_Requests a
                    JOIN Filings f ON a.filing_id = f.filing_id
                    WHERE a.doc_id IN ({placeholders})
                '''
                sqlite_cursor.execute(query, doc_ids)
            else:
                query = '''
                    SELECT a.*, f.filing_id as sqlite_filing_id
                    FROM API_Requests a
                    JOIN Filings f ON a.filing_id = f.filing_id
                '''
                sqlite_cursor.execute(query)
                
            api_requests = sqlite_cursor.fetchall()
            
            synced_count = 0
            
            for request in api_requests:
                try:
                    # Get filing_id from Supabase
                    filing_response = self.supabase.table('filings').select('filing_id').eq('doc_id', request[2]).execute()
                    if not filing_response.data:
                        logger.warning(f"Filing {request[2]} not found in Supabase")
                        continue
                        
                    filing_id = filing_response.data[0]['filing_id']
                    
                    # Insert API request
                    api_data = {
                        'filing_id': filing_id,
                        'doc_id': request[2],
                        'generation_id': request[3],
                        'model': request[4],
                        'max_tokens': request[5],
                        'text_length': request[6],
                        'approx_tokens': request[7],
                        'finish_reason': request[8],
                        'response_status': request[9],
                        'error_message': request[10],
                        'pdf_link': request[11],
                        'raw_text': request[12],
                        'llm_response': request[13]
                    }
                    
                    self.supabase.table('api_requests').insert(api_data).execute()
                    synced_count += 1
                    
                except Exception as e:
                    logger.warning(f"Error syncing API request for doc_id {request[2]}: {e}")
                    
            sqlite_conn.close()
            logger.info(f"Synced {synced_count} API requests to Supabase")
            return synced_count
            
        except Exception as e:
            logger.error(f"Error syncing API requests: {e}")
            return 0
            
    def full_sync(self) -> Dict[str, int]:
        """
        Perform a full sync of all data to Supabase
        
        Returns:
            Dictionary with counts of synced items
        """
        logger.info("Starting full sync to Supabase")
        
        results = {
            'members': 0,
            'filings': 0,
            'api_requests': 0
        }
        
        # Ensure tables exist
        if not self.create_supabase_tables():
            logger.error("Failed to create/verify tables, aborting sync")
            return results
            
        # Sync members first (referenced by filings)
        results['members'] = self.sync_members()
        
        # Sync new filings and transactions
        results['filings'] = self.sync_new_filings()
        
        # Sync API requests
        results['api_requests'] = self.sync_api_requests()
        
        logger.info(f"Full sync complete: {results}")
        return results


def main():
    """Main function for testing the Supabase sync"""
    
    # Initialize sync
    sync = SupabaseSync()
    
    # Create tables if needed
    sync.create_supabase_tables()
    
    # Perform full sync
    results = sync.full_sync()
    
    print(f"\nSync Results:")
    print(f"  Members synced: {results['members']}")
    print(f"  Filings synced: {results['filings']}")
    print(f"  API Requests synced: {results['api_requests']}")


if __name__ == "__main__":
    main()