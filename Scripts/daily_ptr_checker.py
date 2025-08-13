#!/usr/bin/env python3
"""
Daily PTR Checker - Main Script
Checks for new House PTR filings, processes them, and uploads to Supabase
"""

import os
import sys
import logging
import argparse
import schedule
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import our modules
from house_scraper import HouseDisclosureScraper
from pdf_processor import PDFProcessor
from supabase_integration import SupabaseSync

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    handlers=[
        logging.FileHandler('daily_ptr_checker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DailyPTRChecker:
    """Main orchestrator for daily PTR checking and processing"""
    
    def __init__(self, 
                 db_path: str = None,
                 max_workers: int = 5,
                 headless: bool = True):
        """
        Initialize the daily checker
        
        Args:
            db_path: Path to SQLite database
            max_workers: Maximum number of parallel workers for processing
            headless: Whether to run browser in headless mode
        """
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), 'congressional_trades.db')
        self.max_workers = max_workers
        self.headless = headless
        
        # Initialize components
        self.scraper = HouseDisclosureScraper(headless=headless)
        self.processor = PDFProcessor(db_path=self.db_path)
        self.supabase_sync = None
        
        # Try to initialize Supabase (will fail if not configured)
        try:
            self.supabase_sync = SupabaseSync(sqlite_db_path=self.db_path)
            logger.info("Supabase integration initialized")
        except ValueError as e:
            logger.warning(f"Supabase not configured: {e}")
            
        # Statistics
        self.stats = {
            'filings_scraped': 0,
            'filings_processed': 0,
            'filings_failed': 0,
            'filings_synced': 0,
            'start_time': None,
            'end_time': None
        }
        
    def scrape_new_filings(self, year: int = None, max_pages: int = None) -> List[Dict]:
        """
        Scrape new PTR filings from House website
        
        Args:
            year: Year to scrape (default: current year)
            max_pages: Maximum pages to scrape (None for all)
            
        Returns:
            List of new filing dictionaries
        """
        if year is None:
            year = datetime.now().year
            
        logger.info(f"Starting scrape for year {year}")
        
        # Scrape all filings
        all_filings = self.scraper.scrape_ptr_filings(year=year, max_pages=max_pages)
        self.stats['filings_scraped'] = len(all_filings)
        
        # Save scraped filings for reference
        self.scraper.save_scraped_filings()
        
        # Get existing doc_ids from both SQLite and Supabase
        existing_doc_ids = self.processor.get_existing_doc_ids()
        
        if self.supabase_sync:
            try:
                supabase_doc_ids = self.supabase_sync.get_existing_doc_ids()
                existing_doc_ids = existing_doc_ids.union(supabase_doc_ids)
            except Exception as e:
                logger.warning(f"Could not get Supabase doc_ids: {e}")
                
        # Filter to only new filings
        new_filings = [f for f in all_filings if f['doc_id'] not in existing_doc_ids]
        
        logger.info(f"Found {len(new_filings)} new filings out of {len(all_filings)} total")
        
        return new_filings
        
    def process_filing_batch(self, filings: List[Dict]) -> Dict[str, List[str]]:
        """
        Process a batch of filings in parallel
        
        Args:
            filings: List of filing dictionaries to process
            
        Returns:
            Dictionary with successful and failed doc_ids
        """
        results = {
            'successful': [],
            'failed': []
        }
        
        if not filings:
            logger.info("No filings to process")
            return results
            
        logger.info(f"Processing {len(filings)} filings with {self.max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all filing processing tasks
            future_to_filing = {
                executor.submit(self.processor.process_filing, filing): filing
                for filing in filings
            }
            
            # Process results as they complete
            for future in as_completed(future_to_filing):
                filing = future_to_filing[future]
                doc_id = filing['doc_id']
                
                try:
                    success = future.result(timeout=300)  # 5 minute timeout per filing
                    
                    if success:
                        results['successful'].append(doc_id)
                        self.stats['filings_processed'] += 1
                        logger.info(f"Successfully processed {doc_id}")
                    else:
                        results['failed'].append(doc_id)
                        self.stats['filings_failed'] += 1
                        logger.warning(f"Failed to process {doc_id}")
                        
                except Exception as e:
                    results['failed'].append(doc_id)
                    self.stats['filings_failed'] += 1
                    logger.error(f"Exception processing {doc_id}: {e}")
                    
        logger.info(f"Batch processing complete: {len(results['successful'])} successful, {len(results['failed'])} failed")
        
        return results
        
    def sync_to_supabase(self, doc_ids: Optional[List[str]] = None):
        """
        Sync processed filings to Supabase
        
        Args:
            doc_ids: Specific doc_ids to sync (None for all new)
        """
        if not self.supabase_sync:
            logger.warning("Supabase not configured, skipping sync")
            return
            
        logger.info("Starting Supabase sync")
        
        try:
            # Sync members first
            self.supabase_sync.sync_members()
            
            # Sync filings
            synced_count = self.supabase_sync.sync_new_filings(doc_ids)
            self.stats['filings_synced'] = synced_count
            
            logger.info(f"Synced {synced_count} filings to Supabase")
            
        except Exception as e:
            logger.error(f"Error syncing to Supabase: {e}")
            
    def run_daily_check(self, 
                       year: int = None,
                       max_pages: int = None,
                       max_filings: int = None,
                       sync_to_supabase: bool = True):
        """
        Run the complete daily check process
        
        Args:
            year: Year to check (default: current year)
            max_pages: Maximum pages to scrape
            max_filings: Maximum number of filings to process
            sync_to_supabase: Whether to sync results to Supabase
            
        Returns:
            Processing statistics dictionary
        """
        logger.info("=" * 60)
        logger.info("Starting daily PTR check")
        logger.info("=" * 60)
        
        self.stats['start_time'] = datetime.now()
        
        try:
            # Step 1: Scrape new filings
            new_filings = self.scrape_new_filings(year=year, max_pages=max_pages)
            
            if not new_filings:
                logger.info("No new filings found")
                self.stats['end_time'] = datetime.now()
                return self.stats
                
            # Limit number of filings if specified
            if max_filings and len(new_filings) > max_filings:
                logger.info(f"Limiting processing to {max_filings} filings")
                new_filings = new_filings[:max_filings]
                
            # Step 2: Process filings
            results = self.process_filing_batch(new_filings)
            
            # Step 3: Sync to Supabase
            if sync_to_supabase and results['successful']:
                self.sync_to_supabase(results['successful'])
                
        except Exception as e:
            logger.error(f"Error in daily check: {e}")
            
        finally:
            self.stats['end_time'] = datetime.now()
            self._print_statistics()
            
        return self.stats
        
    def _print_statistics(self):
        """Print processing statistics"""
        duration = self.stats['end_time'] - self.stats['start_time']
        
        logger.info("=" * 60)
        logger.info("Daily Check Complete")
        logger.info(f"Duration: {duration}")
        logger.info(f"Filings scraped: {self.stats['filings_scraped']}")
        logger.info(f"Filings processed: {self.stats['filings_processed']}")
        logger.info(f"Filings failed: {self.stats['filings_failed']}")
        logger.info(f"Filings synced to Supabase: {self.stats['filings_synced']}")
        logger.info("=" * 60)
        
    def schedule_daily_runs(self, run_time: str = "09:00"):
        """
        Schedule daily runs at specified time
        
        Args:
            run_time: Time to run daily in HH:MM format (default: 09:00)
        """
        logger.info(f"Scheduling daily runs at {run_time}")
        
        # Schedule the job
        schedule.every().day.at(run_time).do(self.run_daily_check)
        
        logger.info("Daily checker scheduled. Press Ctrl+C to stop.")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Daily checker stopped by user")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Daily PTR Checker for House Filings')
    parser.add_argument('--year', type=int, help='Year to check (default: current year)')
    parser.add_argument('--max-pages', type=int, help='Maximum pages to scrape')
    parser.add_argument('--max-filings', type=int, help='Maximum filings to process')
    parser.add_argument('--workers', type=int, default=5, help='Number of parallel workers')
    parser.add_argument('--no-headless', action='store_true', help='Show browser window')
    parser.add_argument('--no-supabase', action='store_true', help='Skip Supabase sync')
    parser.add_argument('--schedule', action='store_true', help='Run on schedule instead of once')
    parser.add_argument('--schedule-time', default='09:00', help='Time for scheduled runs (HH:MM)')
    parser.add_argument('--db-path', help='Path to SQLite database')
    
    args = parser.parse_args()
    
    # Initialize checker
    checker = DailyPTRChecker(
        db_path=args.db_path,
        max_workers=args.workers,
        headless=not args.no_headless
    )
    
    if args.schedule:
        # Run on schedule
        checker.schedule_daily_runs(args.schedule_time)
    else:
        # Run once
        stats = checker.run_daily_check(
            year=args.year,
            max_pages=args.max_pages,
            max_filings=args.max_filings,
            sync_to_supabase=not args.no_supabase
        )
        
        # Exit with appropriate code
        if stats['filings_failed'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)


if __name__ == "__main__":
    main()