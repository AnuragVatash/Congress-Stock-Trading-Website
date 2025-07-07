import sqlite3
import os
import logging
from typing import Dict, Tuple, Set

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DatabaseMerger:
    def __init__(self, senate_db_path: str, congress_db_path: str, merged_db_path: str):
        self.senate_db_path = senate_db_path
        self.congress_db_path = congress_db_path
        self.merged_db_path = merged_db_path
        
        # ID offset maps for each table to avoid conflicts
        self.id_offsets: Dict[str, int] = {}
        self.id_maps: Dict[str, Dict[int, int]] = {
            'members': {},
            'assets': {},
            'filings': {},
            'transactions': {},
            'api_requests': {}
        }
        
    def get_max_id(self, conn: sqlite3.Connection, table: str, id_column: str) -> int:
        """Get the maximum ID from a table."""
        cursor = conn.cursor()
        cursor.execute(f"SELECT MAX({id_column}) FROM {table}")
        result = cursor.fetchone()[0]
        return result if result else 0
    
    def create_merged_database(self):
        """Create the merged database with the same schema."""
        # Delete existing merged database if it exists
        if os.path.exists(self.merged_db_path):
            os.remove(self.merged_db_path)
            logging.info(f"Removed existing {self.merged_db_path}")
        
        # Connect to congress database to get schema
        congress_conn = sqlite3.connect(self.congress_db_path)
        congress_cursor = congress_conn.cursor()
        
        # Get all table creation statements (excluding system tables)
        congress_cursor.execute("""
            SELECT sql FROM sqlite_master 
            WHERE type='table' 
            AND sql IS NOT NULL 
            AND name NOT LIKE 'sqlite_%'
        """)
        create_statements = congress_cursor.fetchall()
        
        # Get all index creation statements
        congress_cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL")
        index_statements = congress_cursor.fetchall()
        
        congress_conn.close()
        
        # Create merged database
        merged_conn = sqlite3.connect(self.merged_db_path)
        merged_cursor = merged_conn.cursor()
        
        # Create tables
        for (sql,) in create_statements:
            if sql:
                merged_cursor.execute(sql)
        
        # Create indexes
        for (sql,) in index_statements:
            if sql:
                try:
                    merged_cursor.execute(sql)
                except sqlite3.OperationalError as e:
                    # Ignore if index already exists
                    if "already exists" not in str(e):
                        raise
        
        merged_conn.commit()
        merged_conn.close()
        logging.info("Created merged database with schema")
    
    def calculate_offsets(self):
        """Calculate ID offsets to avoid conflicts."""
        congress_conn = sqlite3.connect(self.congress_db_path)
        
        # Get max IDs from congress database
        self.id_offsets['members'] = self.get_max_id(congress_conn, 'Members', 'member_id') + 1000
        self.id_offsets['assets'] = self.get_max_id(congress_conn, 'Assets', 'asset_id') + 1000
        self.id_offsets['filings'] = self.get_max_id(congress_conn, 'Filings', 'filing_id') + 1000
        self.id_offsets['transactions'] = self.get_max_id(congress_conn, 'Transactions', 'transaction_id') + 1000
        self.id_offsets['api_requests'] = self.get_max_id(congress_conn, 'API_Requests', 'request_id') + 1000
        
        congress_conn.close()
        logging.info(f"Calculated ID offsets: {self.id_offsets}")
    
    def merge_members(self, source_conn: sqlite3.Connection, target_conn: sqlite3.Connection, 
                     source_name: str, use_offset: bool = False):
        """Merge Members table, handling duplicates."""
        source_cursor = source_conn.cursor()
        target_cursor = target_conn.cursor()
        
        # Get existing members in target for duplicate detection
        target_cursor.execute("SELECT member_id, LOWER(TRIM(name)) FROM Members")
        existing_members = {name: mid for mid, name in target_cursor.fetchall()}
        
        source_cursor.execute("SELECT * FROM Members")
        members = source_cursor.fetchall()
        
        for member in members:
            old_id = member[0]
            name = member[1]
            name_key = name.lower().strip()
            
            # Check if this member already exists
            if name_key in existing_members:
                # Map to existing member
                new_id = existing_members[name_key]
                self.id_maps['members'][old_id] = new_id
                logging.info(f"[{source_name}] Member '{name}' already exists, mapping {old_id} -> {new_id}")
            else:
                # Insert new member
                if use_offset:
                    new_id = old_id + self.id_offsets['members']
                else:
                    new_id = old_id
                
                self.id_maps['members'][old_id] = new_id
                
                # Insert with new ID
                values = list(member)
                values[0] = new_id
                placeholders = ','.join(['?' for _ in values])
                target_cursor.execute(f"INSERT INTO Members VALUES ({placeholders})", values)
                
                # Add to existing members
                existing_members[name_key] = new_id
        
        target_conn.commit()
        logging.info(f"[{source_name}] Merged {len(members)} members")
    
    def merge_assets(self, source_conn: sqlite3.Connection, target_conn: sqlite3.Connection,
                    source_name: str, use_offset: bool = False):
        """Merge Assets table, handling duplicates."""
        source_cursor = source_conn.cursor()
        target_cursor = target_conn.cursor()
        
        # Get existing assets for duplicate detection
        target_cursor.execute("""
            SELECT asset_id, UPPER(TRIM(ticker)), LOWER(TRIM(company_name))
            FROM Assets
        """)
        existing_tickers = {}
        existing_names = {}
        
        for asset_id, ticker, name in target_cursor.fetchall():
            if ticker:
                existing_tickers[ticker] = asset_id
            else:
                # Normalize company name
                norm_name = name
                if norm_name:
                    import re
                    norm_name = re.sub(r'\s*\(.*\)', '', norm_name)
                    norm_name = re.sub(r'(\s|-)?(common stock|class [a-z])$', '', norm_name)
                    norm_name = re.sub(r'\s+(inc|llc|corp|ltd)\.?$', '', norm_name)
                    norm_name = norm_name.strip()
                    existing_names[norm_name] = asset_id
        
        source_cursor.execute("SELECT * FROM Assets")
        assets = source_cursor.fetchall()
        
        for asset in assets:
            old_id = asset[0]
            company_name = asset[1]
            ticker = asset[2] if len(asset) > 2 else None
            created_at = asset[3] if len(asset) > 3 else None
            
            # Check for duplicates
            duplicate_id = None
            
            if ticker:
                ticker_key = ticker.upper().strip()
                if ticker_key in existing_tickers:
                    duplicate_id = existing_tickers[ticker_key]
            else:
                # Check by normalized name
                import re
                norm_name = (company_name or '').lower().strip()
                norm_name = re.sub(r'\s*\(.*\)', '', norm_name)
                norm_name = re.sub(r'(\s|-)?(common stock|class [a-z])$', '', norm_name)
                norm_name = re.sub(r'\s+(inc|llc|corp|ltd)\.?$', '', norm_name)
                norm_name = norm_name.strip()
                
                if norm_name in existing_names:
                    duplicate_id = existing_names[norm_name]
            
            if duplicate_id:
                # Map to existing asset
                self.id_maps['assets'][old_id] = duplicate_id
                logging.info(f"[{source_name}] Asset '{company_name}' ({ticker}) already exists, mapping {old_id} -> {duplicate_id}")
            else:
                # Insert new asset
                if use_offset:
                    new_id = old_id + self.id_offsets['assets']
                else:
                    new_id = old_id
                
                self.id_maps['assets'][old_id] = new_id
                
                # Insert with new ID
                values = [new_id, company_name, ticker, created_at]
                placeholders = ','.join(['?' for _ in values])
                target_cursor.execute(f"INSERT INTO Assets VALUES ({placeholders})", values)
                
                # Add to tracking
                if ticker:
                    existing_tickers[ticker.upper().strip()] = new_id
                else:
                    import re
                    norm_name = (company_name or '').lower().strip()
                    norm_name = re.sub(r'\s*\(.*\)', '', norm_name)
                    norm_name = re.sub(r'(\s|-)?(common stock|class [a-z])$', '', norm_name)
                    norm_name = re.sub(r'\s+(inc|llc|corp|ltd)\.?$', '', norm_name)
                    norm_name = norm_name.strip()
                    existing_names[norm_name] = new_id
        
        target_conn.commit()
        logging.info(f"[{source_name}] Merged {len(assets)} assets")
    
    def merge_filings(self, source_conn: sqlite3.Connection, target_conn: sqlite3.Connection,
                     source_name: str, use_offset: bool = False):
        """Merge Filings table with updated member_id references."""
        source_cursor = source_conn.cursor()
        target_cursor = target_conn.cursor()
        
        source_cursor.execute("SELECT * FROM Filings")
        filings = source_cursor.fetchall()
        
        for filing in filings:
            old_id = filing[0]
            old_member_id = filing[1]
            
            # Map IDs
            if use_offset:
                new_id = old_id + self.id_offsets['filings']
            else:
                new_id = old_id
            
            self.id_maps['filings'][old_id] = new_id
            
            # Update member_id reference
            new_member_id = self.id_maps['members'].get(old_member_id, old_member_id)
            
            # Insert with new IDs
            values = list(filing)
            values[0] = new_id
            values[1] = new_member_id
            
            placeholders = ','.join(['?' for _ in values])
            target_cursor.execute(f"INSERT INTO Filings VALUES ({placeholders})", values)
        
        target_conn.commit()
        logging.info(f"[{source_name}] Merged {len(filings)} filings")
    
    def merge_transactions(self, source_conn: sqlite3.Connection, target_conn: sqlite3.Connection,
                          source_name: str, use_offset: bool = False):
        """Merge Transactions table with updated foreign key references."""
        source_cursor = source_conn.cursor()
        target_cursor = target_conn.cursor()
        
        source_cursor.execute("SELECT * FROM Transactions")
        transactions = source_cursor.fetchall()
        
        for transaction in transactions:
            old_id = transaction[0]
            old_filing_id = transaction[1]
            old_asset_id = transaction[2]
            
            # Map IDs
            if use_offset:
                new_id = old_id + self.id_offsets['transactions']
            else:
                new_id = old_id
            
            # Update foreign key references
            new_filing_id = self.id_maps['filings'].get(old_filing_id, old_filing_id)
            new_asset_id = self.id_maps['assets'].get(old_asset_id, old_asset_id)
            
            # Insert with new IDs
            values = list(transaction)
            values[0] = new_id
            values[1] = new_filing_id
            values[2] = new_asset_id
            
            placeholders = ','.join(['?' for _ in values])
            target_cursor.execute(f"INSERT INTO Transactions VALUES ({placeholders})", values)
        
        target_conn.commit()
        logging.info(f"[{source_name}] Merged {len(transactions)} transactions")
    
    def merge_api_requests(self, source_conn: sqlite3.Connection, target_conn: sqlite3.Connection,
                          source_name: str, use_offset: bool = False):
        """Merge API_Requests table with updated filing_id references."""
        source_cursor = source_conn.cursor()
        target_cursor = target_conn.cursor()
        
        # Check if API_Requests table exists
        source_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='API_Requests'")
        if not source_cursor.fetchone():
            logging.info(f"[{source_name}] No API_Requests table found, skipping")
            return
        
        source_cursor.execute("SELECT * FROM API_Requests")
        requests = source_cursor.fetchall()
        
        for request in requests:
            old_id = request[0]
            old_filing_id = request[1] if len(request) > 1 else None
            
            # Map IDs
            if use_offset:
                new_id = old_id + self.id_offsets['api_requests']
            else:
                new_id = old_id
            
            # Update filing_id reference if present
            values = list(request)
            values[0] = new_id
            if old_filing_id is not None and len(values) > 1:
                values[1] = self.id_maps['filings'].get(old_filing_id, old_filing_id)
            
            placeholders = ','.join(['?' for _ in values])
            target_cursor.execute(f"INSERT INTO API_Requests VALUES ({placeholders})", values)
        
        target_conn.commit()
        logging.info(f"[{source_name}] Merged {len(requests)} API requests")
    
    def merge_databases(self):
        """Main method to merge both databases."""
        logging.info("Starting database merge process...")
        
        # Create merged database
        self.create_merged_database()
        
        # Calculate offsets
        self.calculate_offsets()
        
        # Connect to all databases
        congress_conn = sqlite3.connect(self.congress_db_path)
        senate_conn = sqlite3.connect(self.senate_db_path)
        merged_conn = sqlite3.connect(self.merged_db_path)
        
        try:
            # First, merge congress database (no offset needed)
            logging.info("\n--- Merging Congress Database ---")
            self.merge_members(congress_conn, merged_conn, "Congress", use_offset=False)
            self.merge_assets(congress_conn, merged_conn, "Congress", use_offset=False)
            self.merge_filings(congress_conn, merged_conn, "Congress", use_offset=False)
            self.merge_transactions(congress_conn, merged_conn, "Congress", use_offset=False)
            self.merge_api_requests(congress_conn, merged_conn, "Congress", use_offset=False)
            
            # Clear ID maps for senate database
            for key in self.id_maps:
                self.id_maps[key].clear()
            
            # Then merge senate database (with offsets)
            logging.info("\n--- Merging Senate Database ---")
            self.merge_members(senate_conn, merged_conn, "Senate", use_offset=True)
            self.merge_assets(senate_conn, merged_conn, "Senate", use_offset=True)
            self.merge_filings(senate_conn, merged_conn, "Senate", use_offset=True)
            self.merge_transactions(senate_conn, merged_conn, "Senate", use_offset=True)
            self.merge_api_requests(senate_conn, merged_conn, "Senate", use_offset=True)
            
            # Get statistics
            merged_cursor = merged_conn.cursor()
            stats = {}
            for table in ['Members', 'Assets', 'Filings', 'Transactions', 'API_Requests']:
                # Check if table exists
                merged_cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                if merged_cursor.fetchone():
                    merged_cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = merged_cursor.fetchone()[0]
                    stats[table] = count
            
            logging.info("\n--- Merge Complete ---")
            logging.info("Final table counts:")
            for table, count in stats.items():
                logging.info(f"  {table}: {count} rows")
            
        finally:
            congress_conn.close()
            senate_conn.close()
            merged_conn.close()


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    senate_db = os.path.join(script_dir, "senate_trades.db")
    congress_db = os.path.join(script_dir, "congress_trades.db")
    merged_db = os.path.join(script_dir, "combined_trades.db")
    
    merger = DatabaseMerger(senate_db, congress_db, merged_db)
    merger.merge_databases()


if __name__ == "__main__":
    main() 