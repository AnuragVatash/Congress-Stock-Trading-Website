#!/usr/bin/env python3
"""
Daily PTR Checker - Main Orchestrator
Automatically checks for new House PTR filings and processes them into the Supabase database
"""

import os
import sys
import logging
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Set
import time

# Import our modules
from house_ptr_scraper import HouseDisclosureScraper
from ptr_pdf_processor import PTRPDFProcessor
from supabase_db_processor import SupabaseDBProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'daily_ptr_checker_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DailyPTRChecker:
    """Main orchestrator for daily PTR checking and processing"""
    
    def __init__(self, year: int = None):
        """
        Initialize the daily checker
        
        Args:
            year: Year to check (defaults to current year)
        """
        self.year = year or datetime.now().year
        self.scraper = HouseDisclosureScraper(headless=True)
        self.pdf_processor = PTRPDFProcessor()
        self.db_processor = SupabaseDBProcessor()
        
        # Track statistics
        self.stats = {
            'start_time': datetime.now().isoformat(),
            'new_filings_found': 0,
            'filings_processed': 0,
            'transactions_extracted': 0,
            'transactions_uploaded': 0,
            'errors': 0
        }
        
        # File paths for persistence
        self.state_file = os.path.join(os.path.dirname(__file__), 'daily_checker_state.json')
        self.processed_docs_file = os.path.join(os.path.dirname(__file__), 'processed_doc_ids.json')
        
    def load_state(self) -> Dict:
        """Load the last run state from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading state: {e}")
        return {}
        
    def save_state(self, state: Dict):
        """Save the current run state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state: {e}")
            
    def load_processed_docs(self) -> Set[str]:
        """Load the set of previously processed document IDs"""
        try:
            if os.path.exists(self.processed_docs_file):
                with open(self.processed_docs_file, 'r') as f:
                    return set(json.load(f))
        except Exception as e:
            logger.error(f"Error loading processed docs: {e}")
        return set()
        
    def save_processed_docs(self, doc_ids: Set[str]):
        """Save the set of processed document IDs"""
        try:
            with open(self.processed_docs_file, 'w') as f:
                json.dump(list(doc_ids), f, indent=2)
        except Exception as e:
            logger.error(f"Error saving processed docs: {e}")
            
    def check_for_new_filings(self) -> List[Dict]:
        """
        Check for new PTR filings on the House website
        
        Returns:
            List of new filing dictionaries
        """
        logger.info(f"Checking for new PTR filings for year {self.year}")
        
        try:
            # Scrape all PTR filings for the year
            all_filings = self.scraper.scrape_ptr_filings(year=self.year, max_pages=None)
            
            if not all_filings:
                logger.warning("No filings found from scraper")
                return []
                
            # Get existing document IDs from database
            existing_db_ids = self.db_processor.get_existing_doc_ids()
            
            # Get locally tracked processed IDs
            processed_local_ids = self.load_processed_docs()
            
            # Combine both sets of existing IDs
            all_existing_ids = existing_db_ids | processed_local_ids
            
            # Filter to only new filings
            new_filings = []
            for filing in all_filings:
                doc_id = filing.get('doc_id')
                if doc_id and doc_id not in all_existing_ids:
                    new_filings.append(filing)
                    
            logger.info(f"Found {len(new_filings)} new filings out of {len(all_filings)} total")
            self.stats['new_filings_found'] = len(new_filings)
            
            return new_filings
            
        except Exception as e:
            logger.error(f"Error checking for new filings: {e}")
            self.stats['errors'] += 1
            return []
            
    def process_new_filings(self, new_filings: List[Dict], batch_size: int = 10) -> List[Dict]:
        """
        Process new filings through the PDF processor to extract transactions
        
        Args:
            new_filings: List of new filing dictionaries
            batch_size: Number of filings to process in each batch
            
        Returns:
            List of extracted transactions
        """
        all_transactions = []
        processed_doc_ids = self.load_processed_docs()
        
        # Process in batches to manage memory and API rate limits
        for i in range(0, len(new_filings), batch_size):
            batch = new_filings[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(new_filings) + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} filings)")
            
            try:
                # Process batch through PDF processor
                batch_transactions = self.pdf_processor.process_filings_batch(batch)
                all_transactions.extend(batch_transactions)
                
                # Track processed documents
                for filing in batch:
                    doc_id = filing.get('doc_id')
                    if doc_id:
                        processed_doc_ids.add(doc_id)
                        self.stats['filings_processed'] += 1
                        
                # Save progress after each batch
                self.save_processed_docs(processed_doc_ids)
                
                logger.info(f"Batch {batch_num} complete: {len(batch_transactions)} transactions extracted")
                
                # Rate limiting between batches
                if i + batch_size < len(new_filings):
                    logger.info("Pausing between batches...")
                    time.sleep(5)
                    
            except Exception as e:
                logger.error(f"Error processing batch {batch_num}: {e}")
                self.stats['errors'] += 1
                continue
                
        self.stats['transactions_extracted'] = len(all_transactions)
        logger.info(f"Total transactions extracted: {len(all_transactions)}")
        
        return all_transactions
        
    def upload_to_database(self, transactions: List[Dict]) -> bool:
        """
        Upload extracted transactions to Supabase database
        
        Args:
            transactions: List of transaction dictionaries
            
        Returns:
            True if successful, False otherwise
        """
        if not transactions:
            logger.info("No transactions to upload")
            return True
            
        logger.info(f"Uploading {len(transactions)} transactions to database")
        
        try:
            # Process transactions batch
            result = self.db_processor.process_transactions_batch(transactions)
            
            self.stats['transactions_uploaded'] = result.get('transactions_created', 0)
            self.stats['errors'] += result.get('errors', 0)
            
            logger.info(f"Database upload complete: {result}")
            
            return result.get('errors', 0) == 0
            
        except Exception as e:
            logger.error(f"Error uploading to database: {e}")
            self.stats['errors'] += 1
            return False
            
    def generate_report(self) -> str:
        """
        Generate a summary report of the daily check
        
        Returns:
            Report string
        """
        self.stats['end_time'] = datetime.now().isoformat()
        
        # Calculate duration
        start = datetime.fromisoformat(self.stats['start_time'])
        end = datetime.fromisoformat(self.stats['end_time'])
        duration = end - start
        
        # Get database statistics
        db_stats = self.db_processor.get_member_stats()
        
        report = f"""
========================================
Daily PTR Checker Report
========================================
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Year Checked: {self.year}
Duration: {duration}

New Filings Found: {self.stats['new_filings_found']}
Filings Processed: {self.stats['filings_processed']}
Transactions Extracted: {self.stats['transactions_extracted']}
Transactions Uploaded: {self.stats['transactions_uploaded']}
Errors: {self.stats['errors']}

Database Statistics:
- Total Members: {db_stats.get('total_members', 0)}
- Total Filings: {db_stats.get('total_filings', 0)}
- Total Transactions: {db_stats.get('total_transactions', 0)}
- Total Assets: {db_stats.get('total_assets', 0)}

Status: {'SUCCESS' if self.stats['errors'] == 0 else 'COMPLETED WITH ERRORS'}
========================================
"""
        return report
        
    def run(self, force_all: bool = False) -> bool:
        """
        Run the daily check process
        
        Args:
            force_all: If True, process all filings regardless of existing records
            
        Returns:
            True if successful, False if errors occurred
        """
        logger.info("="*50)
        logger.info("Starting Daily PTR Checker")
        logger.info(f"Time: {datetime.now()}")
        logger.info(f"Year: {self.year}")
        logger.info(f"Force All: {force_all}")
        logger.info("="*50)
        
        try:
            # Step 1: Check for new filings
            logger.info("Step 1: Checking for new filings...")
            new_filings = self.check_for_new_filings()
            
            if not new_filings and not force_all:
                logger.info("No new filings found. Exiting.")
                return True
                
            # Step 2: Process new filings
            logger.info(f"Step 2: Processing {len(new_filings)} new filings...")
            transactions = self.process_new_filings(new_filings)
            
            # Step 3: Upload to database
            if transactions:
                logger.info("Step 3: Uploading to database...")
                self.upload_to_database(transactions)
            else:
                logger.info("No transactions to upload")
                
            # Step 4: Generate and display report
            report = self.generate_report()
            print(report)
            
            # Save report to file
            report_file = f"daily_ptr_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(report_file, 'w') as f:
                f.write(report)
            logger.info(f"Report saved to {report_file}")
            
            # Save final state
            self.save_state(self.stats)
            
            return self.stats['errors'] == 0
            
        except Exception as e:
            logger.error(f"Fatal error in daily check: {e}")
            self.stats['errors'] += 1
            return False
            
def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Daily PTR Checker - Check for new House PTR filings')
    parser.add_argument('--year', type=int, default=None,
                       help='Year to check (default: current year)')
    parser.add_argument('--force-all', action='store_true',
                       help='Process all filings regardless of existing records')
    parser.add_argument('--batch-size', type=int, default=10,
                       help='Number of filings to process per batch (default: 10)')
    
    args = parser.parse_args()
    
    # Create and run checker
    checker = DailyPTRChecker(year=args.year)
    success = checker.run(force_all=args.force_all)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)
    
if __name__ == "__main__":
    main()