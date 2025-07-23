#!/usr/bin/env python3
"""
Master Congressional Trading Data Processor
==========================================

This script serves as the central coordinator for collecting and processing
congressional trading data from both House and Senate sources, applying the
enhanced database schema with member profile information.

Features:
- Integrates House script (2025.xml FD file processing)
- Integrates Senate script (web scraping approach) 
- Enhanced database schema with member profile fields
- Applies updates to Combined Copy Mod Curr database
- Comprehensive data validation and cleanup
"""

import sys
import os
import sqlite3
import logging
import argparse
import time
import threading
import queue
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import requests
import json
import unicodedata

# Add individual script directories to Python path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
hor_script_path = os.path.join(script_dir, 'HOR Script')
senate_script_path = os.path.join(script_dir, 'Senate Script')
common_script_path = os.path.join(script_dir, 'common')

# Add paths in order of priority
for path in [hor_script_path, senate_script_path, common_script_path]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Import existing functionality with proper error handling
hor_scraper = None
hor_db = None
senate_scraper = None
senate_db = None
db_schema = None

try:
    import scrapeLinks as hor_scraper
    import db_processor as hor_db
    logging.info("✅ Successfully imported House script modules")
except ImportError as e:
    logging.error(f"❌ Could not import House script modules: {e}")

try:
    import combined_scraper as senate_scraper
    import senate_db_processor as senate_db
    logging.info("✅ Successfully imported Senate script modules")
except ImportError as e:
    logging.error(f"❌ Could not import Senate script modules: {e}")

try:
    import db_schema
    logging.info("✅ Successfully imported common database schema module")
except ImportError as e:
    logging.error(f"❌ Could not import common database schema: {e}")

if not all([hor_scraper, hor_db, senate_db]):
    logging.warning("⚠️ Some script modules could not be imported. Functionality may be limited.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
    handlers=[
        logging.FileHandler(f'master_processor_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

class MasterDataProcessor:
    """Main coordinator for congressional trading data collection and processing"""
    
    def __init__(self, target_db_path: str):
        self.target_db_path = target_db_path
        self.temp_house_db = 'temp_house_trades.db'
        self.temp_senate_db = 'temp_senate_trades.db'
        
        # Statistics tracking
        self.stats = {
            'house_documents_processed': 0,
            'senate_documents_processed': 0,
            'total_transactions_added': 0,
            'members_enriched': 0,
            'errors': []
        }
        
        # Member information cache for enrichment
        self.member_info_cache = {}
        
    def upgrade_database_schema(self):
        """Upgrade target database to include enhanced member fields"""
        logging.info("🔧 Upgrading database schema with member profile fields...")
        
        conn = sqlite3.connect(self.target_db_path)
        cursor = conn.cursor()
        
        try:
            # Check if new columns already exist
            cursor.execute("PRAGMA table_info(Members)")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Add new member profile columns if they don't exist
            new_columns = [
                ('photo_url', 'TEXT'),
                ('party', 'TEXT'), 
                ('state', 'TEXT'),
                ('chamber', 'TEXT')
            ]
            
            for col_name, col_type in new_columns:
                if col_name not in columns:
                    cursor.execute(f"ALTER TABLE Members ADD COLUMN {col_name} {col_type}")
                    logging.info(f"Added column {col_name} to Members table")
            
            # Create enhanced indexes if they don't exist
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_members_party ON Members(party)",
                "CREATE INDEX IF NOT EXISTS idx_members_state ON Members(state)", 
                "CREATE INDEX IF NOT EXISTS idx_members_chamber ON Members(chamber)",
                "CREATE INDEX IF NOT EXISTS idx_filings_filing_date ON Filings(filing_date)",
                "CREATE INDEX IF NOT EXISTS idx_transactions_date ON Transactions(transaction_date)",
                "CREATE INDEX IF NOT EXISTS idx_assets_ticker ON Assets(ticker)",
                "CREATE INDEX IF NOT EXISTS idx_assets_company_name ON Assets(company_name)"
            ]
            
            for index_sql in indexes:
                cursor.execute(index_sql)
            
            conn.commit()
            logging.info("✅ Database schema upgrade completed")
            
        except Exception as e:
            conn.rollback()
            logging.error(f"❌ Error upgrading database schema: {e}")
            raise
        finally:
            conn.close()
    
    def load_member_info_cache(self):
        """Load member information for enrichment"""
        logging.info("📚 Loading member information cache...")
        
        self.member_info_cache = {}
        
        # Load from enrichment data file
        enrichment_file = os.path.join(os.path.dirname(__file__), 'member_enrichment_data.json')
        if os.path.exists(enrichment_file):
            try:
                with open(enrichment_file, 'r') as f:
                    enrichment_data = json.load(f)
                
                # Load house members
                for name, info in enrichment_data.get('house_members', {}).items():
                    self.member_info_cache[name.lower().strip()] = info
                
                # Load senate members
                for name, info in enrichment_data.get('senate_members', {}).items():
                    self.member_info_cache[name.lower().strip()] = info
                
                logging.info(f"✅ Loaded {len(self.member_info_cache)} members from enrichment file")
                
            except Exception as e:
                logging.warning(f"⚠️ Could not load member enrichment data: {e}")
        else:
            logging.warning(f"⚠️ Member enrichment file not found: {enrichment_file}")
        
        # Try to load from existing enhanced data in target database
        if os.path.exists(self.target_db_path):
            conn = sqlite3.connect(self.target_db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute("SELECT name, party, state, chamber, photo_url FROM Members WHERE party IS NOT NULL")
                existing_count = 0
                for name, party, state, chamber, photo_url in cursor.fetchall():
                    name_key = name.lower().strip()
                    if name_key not in self.member_info_cache:
                        self.member_info_cache[name_key] = {
                            'party': party,
                            'state': state, 
                            'chamber': chamber,
                            'photo_url': photo_url
                        }
                        existing_count += 1
                
                if existing_count > 0:
                    logging.info(f"✅ Added {existing_count} additional members from existing database")
                    
            except sqlite3.OperationalError:
                # Columns might not exist yet
                logging.info("ℹ️ Enhanced member columns not yet available in target database")
            finally:
                conn.close()
            
        logging.info(f"📊 Total member cache size: {len(self.member_info_cache)} records")
    
    def enrich_member_info(self, member_name: str, source: str = None) -> Dict:
        """Enrich member information with party, state, chamber data"""
        name_key = member_name.lower().strip()
        
        if name_key in self.member_info_cache:
            return self.member_info_cache[name_key]
        
        # Basic inference from source
        enriched_info = {
            'party': None,
            'state': None,
            'chamber': source if source in ['House', 'Senate'] else None,
            'photo_url': None
        }
        
        # Try to infer chamber from source context
        if not enriched_info['chamber']:
            if 'house' in str(source).lower() or 'hor' in str(source).lower():
                enriched_info['chamber'] = 'House'
            elif 'senate' in str(source).lower():
                enriched_info['chamber'] = 'Senate'
        
        # Cache the result
        self.member_info_cache[name_key] = enriched_info
        return enriched_info
    
    def _create_basic_schema(self, db_path: str):
        """Create basic database schema if common schema not available"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create basic Members table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Members (
                member_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                party TEXT,
                state TEXT,
                chamber TEXT,
                photo_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create basic Filings table
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
        
        conn.commit()
        conn.close()
        logging.info(f"✅ Created basic schema for {db_path}")
    
    def _store_basic_filing(self, db_path: str, member_name: str, doc_id: str, url: str, enriched_info: Dict):
        """Store basic filing information in temporary database"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Get or create member
            cursor.execute("SELECT member_id FROM Members WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))", (member_name,))
            existing_member = cursor.fetchone()
            
            if existing_member:
                member_id = existing_member[0]
            else:
                # Create new member
                cursor.execute("""
                    INSERT INTO Members (name, party, state, chamber, photo_url, created_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (member_name, enriched_info['party'], enriched_info['state'], 
                     enriched_info['chamber'], enriched_info['photo_url']))
                member_id = cursor.lastrowid
            
            # Check if filing already exists
            cursor.execute("SELECT filing_id FROM Filings WHERE doc_id = ?", (doc_id,))
            if not cursor.fetchone():
                # Create filing
                cursor.execute("""
                    INSERT INTO Filings (member_id, doc_id, url, filing_date, verified, created_at)
                    VALUES (?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
                """, (member_id, doc_id, url, None))
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            logging.error(f"❌ Error storing filing {doc_id}: {e}")
            raise
        finally:
            conn.close()
    
    def run_house_data_collection(self):
        """Collect and process new House documents directly into the main database."""
        if not hor_scraper or not hor_db:
            logging.error("❌ House script modules not available")
            return
        
        logging.info("🏛️ Starting House data collection (2025.xml FD processing)...")
        
        try:
            # Use ONLY the main database - no temp databases
            main_db_path = os.path.abspath(self.target_db_path)
            logging.info(f"🔍 Processing directly into main database: {main_db_path}")
            
            # Step 1: Get new doc_ids from XML vs main database
            results_from_scraper = hor_scraper.scrape(db_path=main_db_path)
            
            if not results_from_scraper:
                logging.info("📭 No new House documents found to process")
                self.stats['house_documents_processed'] = 0
                return
            
            logging.info(f"🔍 Found {len(results_from_scraper)} new House documents to process")
            
            # Step 2: Process each document with LLM directly into main database
            documents_processed = 0
            
            for pdf_info in results_from_scraper:
                try:
                    member_data = pdf_info.get('member_data', {})
                    pdf_url = pdf_info.get('url')
                    doc_id = member_data.get('DocID')
                    
                    # Construct member name
                    first_name = member_data.get('First', '')
                    last_name = member_data.get('Last', '')
                    if first_name or last_name:
                        member_name = f"{first_name} {last_name}".strip()
                    else:
                        member_name = member_data.get('Officename', '').strip()
                    
                    if not member_name:
                        member_name = "Unknown Member"
                    
                    if not all([doc_id, pdf_url]):
                        logging.warning(f"⚠️ Skipping document with missing data: DocID={doc_id}, URL={pdf_url}")
                        continue
                    
                    logging.info(f"📄 Processing House doc {doc_id} for {member_name}")
                    
                    # Step 3: Process with LLM and store directly in main database
                    try:
                        # Import LLM functions
                        from scanToTextLLM import scan_with_openrouter, parse_llm_transactions
                        
                        # Get raw LLM output
                        llm_raw_output = scan_with_openrouter(pdf_url, member_data)
                        
                        # Parse into structured transactions
                        parsed_transactions = parse_llm_transactions(llm_raw_output, member_data)
                        
                        logging.info(f"📊 Parsed {len(parsed_transactions)} transactions from {doc_id}")
                        
                        # Step 4: Store directly in main database
                        if parsed_transactions:
                            num_inserted = hor_db.process_and_store_scraped_data(
                                member_name=member_name,
                                doc_id=doc_id,
                                url=pdf_url,
                                llm_transactions=parsed_transactions,
                                db_path=main_db_path
                            )
                            logging.info(f"✅ Stored {num_inserted} transactions for {doc_id}")
                        else:
                            # Still create the filing record even if no transactions
                            hor_db.process_and_store_scraped_data(
                                member_name=member_name,
                                doc_id=doc_id,
                                url=pdf_url,
                                llm_transactions=[],
                                db_path=main_db_path
                            )
                            logging.info(f"📝 Created filing record for {doc_id} (no transactions)")
                        
                        documents_processed += 1
                        
                    except Exception as llm_error:
                        logging.error(f"❌ LLM processing failed for {doc_id}: {llm_error}")
                        
                except Exception as e:
                    logging.error(f"❌ Error processing House document: {e}")
                    self.stats['errors'].append(f"House processing error: {e}")
            
            self.stats['house_documents_processed'] = documents_processed
            logging.info(f"✅ House data collection completed: {documents_processed} documents")
            
        except Exception as e:
            logging.error(f"❌ Fatal error in House data collection: {e}")
            self.stats['errors'].append(f"House collection error: {e}")

    def run_senate_data_collection(self):
        """Collect and process new Senate documents directly into the main database."""
        if not senate_scraper or not senate_db:
            logging.error("❌ Senate script modules not available")
            return
        
        logging.info("🏛️ Starting Senate data collection (web scraping)...")
        
        try:
            # Use ONLY the main database - no temp databases
            main_db_path = os.path.abspath(self.target_db_path)
            logging.info(f"🔍 Processing directly into main database: {main_db_path}")
            
            # Step 1: Get new filings from website vs main database
            documents_processed = 0
            
            try:
                logging.info("🔍 Scraping Senate website for new PTR filings...")
                
                # Get new links using the actual scraper, checking against main database
                all_links = senate_scraper.scrape_all_ptr_links(force_rescrape=False, db_path=main_db_path)
                
                if not all_links:
                    logging.info("📭 No new Senate documents found to process")
                    self.stats['senate_documents_processed'] = 0
                    return
                
                logging.info(f"🔍 Found {len(all_links)} new Senate documents to process")
                
                # Step 2: Process each document with LLM directly into main database
                for link_info in all_links:
                    try:
                        member_name = link_info.get('member_name', 'Unknown Member')
                        doc_id = link_info.get('doc_id')
                        url = link_info.get('url')
                        
                        if not all([doc_id, url]):
                            logging.warning(f"⚠️ Skipping Senate document with missing data: DocID={doc_id}, URL={url}")
                            continue
                        
                        logging.info(f"📄 Processing Senate doc {doc_id} for {member_name}")
                        
                        # Step 3: Process with LLM and store directly in main database
                        try:
                            # Import LLM functions
                            from scanToTextLLM import scan_with_openrouter, parse_llm_transactions
                            
                            # Prepare member data for LLM
                            member_data = {
                                'DocID': doc_id,
                                'Name': member_name,
                                'URL': url
                            }
                            
                            # Get raw LLM output
                            llm_raw_output = scan_with_openrouter(url, member_data)
                            
                            # Parse into structured transactions
                            parsed_transactions = parse_llm_transactions(llm_raw_output, member_data)
                            
                            logging.info(f"📊 Parsed {len(parsed_transactions)} transactions from {doc_id}")
                            
                            # Step 4: Store directly in main database
                            if parsed_transactions:
                                num_inserted = senate_db.process_and_store_scraped_data(
                                    member_name=member_name,
                                    doc_id=doc_id,
                                    url=url,
                                    llm_transactions=parsed_transactions,
                                    db_path=main_db_path
                                )
                                logging.info(f"✅ Stored {num_inserted} transactions for {doc_id}")
                            else:
                                # Still create the filing record even if no transactions
                                senate_db.process_and_store_scraped_data(
                                    member_name=member_name,
                                    doc_id=doc_id,
                                    url=url,
                                    llm_transactions=[],
                                    db_path=main_db_path
                                )
                                logging.info(f"📝 Created filing record for {doc_id} (no transactions)")
                            
                            documents_processed += 1
                            
                        except Exception as llm_error:
                            logging.error(f"❌ LLM processing failed for {doc_id}: {llm_error}")
                        
                    except Exception as e:
                        logging.error(f"❌ Error processing Senate document {doc_id}: {e}")
                        self.stats['errors'].append(f"Senate processing error: {e}")
                
            except Exception as scrape_error:
                logging.error(f"❌ Error during Senate scraping: {scrape_error}")
                self.stats['errors'].append(f"Senate scraping error: {scrape_error}")
            
            self.stats['senate_documents_processed'] = documents_processed
            logging.info(f"✅ Senate data collection completed: {documents_processed} documents")
            
        except Exception as e:
            logging.error(f"❌ Fatal error in Senate data collection: {e}")
            self.stats['errors'].append(f"Senate collection error: {e}")
    
    def merge_collected_data(self):
        """Merge collected data into target database with enhanced schema"""
        logging.info("🔄 Merging collected data into target database...")
        
        target_conn = sqlite3.connect(self.target_db_path)
        target_conn.execute("PRAGMA foreign_keys = ON")
        target_cursor = target_conn.cursor()
        
        transactions_added = 0
        members_enriched = 0
        
        try:
            # Process house data if exists
            if os.path.exists(self.temp_house_db):
                house_conn = sqlite3.connect(self.temp_house_db)
                house_cursor = house_conn.cursor()
                
                # Get members from house database
                house_cursor.execute("SELECT member_id, name FROM Members")
                house_members = house_cursor.fetchall()
                
                for member_id, name in house_members:
                    # Check if member exists in target database
                    target_cursor.execute("SELECT member_id FROM Members WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))", (name,))
                    existing_member = target_cursor.fetchone()
                    
                    if not existing_member:
                        # Add new member with enhanced info
                        enriched_info = self.enrich_member_info(name, 'House')
                        
                        target_cursor.execute("""
                            INSERT INTO Members (name, party, state, chamber, photo_url, created_at)
                            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """, (name, enriched_info['party'], enriched_info['state'], 
                             enriched_info['chamber'], enriched_info['photo_url']))
                        
                        members_enriched += 1
                        logging.info(f"➕ Added member: {name} ({enriched_info['chamber']})")
                    else:
                        # Update existing member with enhanced info if needed
                        enriched_info = self.enrich_member_info(name, 'House')
                        
                        target_cursor.execute("""
                            UPDATE Members 
                            SET party = COALESCE(party, ?),
                                state = COALESCE(state, ?),
                                chamber = COALESCE(chamber, ?),
                                photo_url = COALESCE(photo_url, ?)
                            WHERE member_id = ?
                        """, (enriched_info['party'], enriched_info['state'],
                             enriched_info['chamber'], enriched_info['photo_url'],
                             existing_member[0]))
                        
                        if target_cursor.rowcount > 0:
                            members_enriched += 1
                            logging.info(f"🔄 Enriched member: {name}")
                
                house_conn.close()
            
            # Process senate data if exists
            if os.path.exists(self.temp_senate_db):
                senate_conn = sqlite3.connect(self.temp_senate_db)
                senate_cursor = senate_conn.cursor()
                
                # Similar processing for senate data
                senate_cursor.execute("SELECT member_id, name FROM Members")
                senate_members = senate_cursor.fetchall()
                
                for member_id, name in senate_members:
                    # Check if member exists in target database
                    target_cursor.execute("SELECT member_id FROM Members WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))", (name,))
                    existing_member = target_cursor.fetchone()
                    
                    if not existing_member:
                        # Add new member with enhanced info
                        enriched_info = self.enrich_member_info(name, 'Senate')
                        
                        target_cursor.execute("""
                            INSERT INTO Members (name, party, state, chamber, photo_url, created_at)
                            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """, (name, enriched_info['party'], enriched_info['state'],
                             enriched_info['chamber'], enriched_info['photo_url']))
                        
                        members_enriched += 1
                        logging.info(f"➕ Added member: {name} ({enriched_info['chamber']})")
                    else:
                        # Update existing member with enhanced info if needed
                        enriched_info = self.enrich_member_info(name, 'Senate')
                        
                        target_cursor.execute("""
                            UPDATE Members 
                            SET party = COALESCE(party, ?),
                                state = COALESCE(state, ?),
                                chamber = COALESCE(chamber, ?),
                                photo_url = COALESCE(photo_url, ?)
                            WHERE member_id = ?
                        """, (enriched_info['party'], enriched_info['state'],
                             enriched_info['chamber'], enriched_info['photo_url'],
                             existing_member[0]))
                        
                        if target_cursor.rowcount > 0:
                            members_enriched += 1
                            logging.info(f"🔄 Enriched member: {name}")
                
                senate_conn.close()
            
            target_conn.commit()
            
            self.stats['total_transactions_added'] = transactions_added
            self.stats['members_enriched'] = members_enriched
            
            logging.info(f"✅ Data merge completed: {members_enriched} members enriched")
            
        except Exception as e:
            target_conn.rollback()
            logging.error(f"❌ Error merging data: {e}")
            self.stats['errors'].append(f"Data merge error: {e}")
            raise
        finally:
            target_conn.close()
    
    def cleanup_temp_files(self):
        """Clean up temporary database files"""
        for temp_db in [self.temp_house_db, self.temp_senate_db]:
            if os.path.exists(temp_db):
                try:
                    os.remove(temp_db)
                    logging.info(f"🗑️ Cleaned up {temp_db}")
                except Exception as e:
                    logging.warning(f"⚠️ Could not remove {temp_db}: {e}")
    
    def load_search_json(self):
        """Load and index search.json for member enrichment, with a fallback."""
        primary_path = os.path.join(os.path.dirname(__file__), 'search.json')
        fallback_path = os.path.join(os.path.dirname(__file__), 'search (1).json')
        
        search_path = None
        if os.path.exists(primary_path):
            search_path = primary_path
            logging.info(f"Using primary member info file: {primary_path}")
        elif os.path.exists(fallback_path):
            search_path = fallback_path
            logging.info(f"Primary search.json not found. Using fallback: {fallback_path}")
        else:
            logging.warning(f"Neither search.json nor search (1).json found.")
            return {}

        with open(search_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Index by normalized full name and by id
        index = {}
        for entry in data:
            # Normalize name: first + last, lower, no accents
            full_name = f"{entry.get('givenName','')} {entry.get('familyName','')}".strip()
            norm_name = self._normalize_name(full_name)
            index[norm_name] = entry
        return index

    def _normalize_name(self, name):
        # Remove accents, lowercase, strip
        return ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn').lower().strip()

    def enrich_all_members_from_search_json(self):
        """Update all members in the DB with info from search.json if missing."""
        search_index = self.load_search_json()
        if not search_index:
            logging.warning("No search.json data loaded for enrichment.")
            return
        conn = sqlite3.connect(self.target_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT member_id, name, party, state, chamber, photo_url FROM Members")
        updates = 0
        for member_id, name, party, state, chamber, photo_url in cursor.fetchall():
            norm_name = self._normalize_name(name)
            entry = search_index.get(norm_name)
            if not entry:
                continue
            # Get latest congress info
            latest_congress = None
            for c in reversed(entry['congresses']):
                if c.get('position') in ('Representative', 'Senator'):
                    latest_congress = c
                    break
            if not latest_congress:
                continue
            new_party = party or (latest_congress['parties'][0] if latest_congress.get('parties') else None)
            new_state = state or latest_congress.get('stateName')
            new_chamber = chamber or ('House' if latest_congress['position'] == 'Representative' else 'Senate')
            new_photo_url = photo_url or f"https://unitedstates.github.io/images/congress/225x275/{entry['id']}.jpg"
            # Only update if something is missing
            if (party != new_party) or (state != new_state) or (chamber != new_chamber) or (photo_url != new_photo_url):
                cursor.execute("""
                    UPDATE Members SET party=?, state=?, chamber=?, photo_url=? WHERE member_id=?
                """, (new_party, new_state, new_chamber, new_photo_url, member_id))
                updates += 1
        conn.commit()
        conn.close()
        logging.info(f"Enriched {updates} members from search.json.")

    def run_full_processing(self):
        """Run the complete processing pipeline with proper error handling."""
        try:
            logging.info("🚀 Starting Master Congressional Trading Data Processing")
            logging.info("============================================================")
            
            # Step 1: Upgrade database schema
            self.upgrade_database_schema()
            
            # Step 2: Load member information cache
            self.load_member_info_cache()
            
            # Step 3: Run house data collection (directly into main database)
            self.run_house_data_collection()
            
            # Step 4: Run senate data collection (directly into main database)
            self.run_senate_data_collection()
            
            # Step 5: Enrich member information
            logging.info("👥 Starting member enrichment process...")
            self.enrich_all_members_from_search_json()
            
            logging.info("🎉 Master processing pipeline completed successfully!")
            
        except Exception as e:
            logging.error(f"❌ Fatal error in processing pipeline: {e}")
            self.stats['errors'].append(f"Pipeline error: {e}")
        
        finally:
            # Generate final report
            self.generate_final_report()
    
    def generate_final_report(self):
        """Generate a final processing report"""
        logging.info("\n" + "="*60)
        logging.info("📊 MASTER PROCESSING REPORT")
        logging.info("="*60)
        
        logging.info(f"🏛️ House documents processed: {self.stats['house_documents_processed']}")
        logging.info(f"🏛️ Senate documents processed: {self.stats['senate_documents_processed']}")
        logging.info(f"👥 Members enriched: {self.stats['members_enriched']}")
        logging.info(f"💰 Total transactions added: {self.stats['total_transactions_added']}")
        
        if self.stats['errors']:
            logging.info(f"⚠️ Errors encountered: {len(self.stats['errors'])}")
            for error in self.stats['errors']:
                logging.info(f"   • {error}")
        else:
            logging.info("✅ No errors encountered")
        
        # Database statistics
        conn = sqlite3.connect(self.target_db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM Members")
        total_members = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM Members WHERE party IS NOT NULL")
        enriched_members = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM Transactions")
        total_transactions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM Assets")
        total_assets = cursor.fetchone()[0]
        
        conn.close()
        
        logging.info(f"\n📈 Final Database Statistics:")
        logging.info(f"   Members: {total_members} total, {enriched_members} enriched ({enriched_members/total_members*100:.1f}%)")
        logging.info(f"   Transactions: {total_transactions}")
        logging.info(f"   Assets: {total_assets}")
        
        logging.info("=" * 60)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Master Congressional Trading Data Processor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python master_data_processor.py                           # Use default database
  python master_data_processor.py --db "Combined Trades Mod Curr.db"  # Specify database
  python master_data_processor.py --house-only             # Only process House data
  python master_data_processor.py --senate-only            # Only process Senate data
        """
    )
    
    parser.add_argument(
        '--db', 
        default=os.path.join('db', 'Combined Trades Mod Curr.db'),
        help='Path to target database (default: db/Combined Trades Mod Curr.db)'
    )
    
    parser.add_argument(
        '--house-only',
        action='store_true',
        help='Only process House data (2025.xml FD sources)'
    )
    
    parser.add_argument(
        '--senate-only', 
        action='store_true',
        help='Only process Senate data (web scraping)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without making database changes'
    )
    
    args = parser.parse_args()
    
    # Validate database path
    if not os.path.exists(args.db):
        print(f"❌ Error: Database file not found at '{args.db}'")
        print("Please ensure the database file exists or specify a different path with --db")
        return 1
    
    if args.house_only and args.senate_only:
        print("❌ Error: Cannot specify both --house-only and --senate-only")
        return 1
    
    # Initialize processor
    processor = MasterDataProcessor(args.db)
    
    if args.dry_run:
        logging.info("🚨 DRY RUN MODE - No database changes will be made")
        # In dry run, we would simulate the operations
        return 0
    
    # Run processing pipeline
    try:
        if args.house_only:
            logging.info("🏛️ Running House-only processing")
            processor.upgrade_database_schema()
            processor.load_member_info_cache()
            processor.run_house_data_collection()
            processor.merge_collected_data()
        elif args.senate_only:
            logging.info("🏛️ Running Senate-only processing")
            processor.upgrade_database_schema()
            processor.load_member_info_cache()
            processor.run_senate_data_collection()
            processor.merge_collected_data()
        else:
            logging.info("🏛️ Running full House + Senate processing")
            processor.run_full_processing()
        
        processor.generate_final_report()
        logging.info("🎉 Processing completed successfully!")
        return 0
        
    except KeyboardInterrupt:
        logging.info("⚠️ Processing interrupted by user")
        processor.cleanup_temp_files()
        return 1
    except Exception as e:
        logging.error(f"❌ Fatal error: {e}")
        processor.cleanup_temp_files()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 