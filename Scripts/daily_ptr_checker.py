"""
Daily PTR Pipeline Orchestrator

Steps:
1) Scrape House Financial Disclosure site for PTR filings for a given year
2) Compare against existing `Filings.doc_id` in Supabase to find new filings
3) For each new filing, process the PDF and extract transactions (LLM-backed)
4) Store members, assets, filings, and transactions into Supabase

Usage:
  python daily_ptr_checker.py --year 2025 --limit 5 --headless true

Environment:
  Reads credentials from Scripts/.env via submodules
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from typing import List, Dict

# Local imports
from house_ptr_scraper import HouseDisclosureScraper
from ptr_pdf_processor import process_ptr_pdf
from supabase_db_processor import SupabaseDBProcessor

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Run the full House PTR pipeline")
	parser.add_argument("--year", type=int, default=datetime.now().year, help="Filing year to scrape")
	parser.add_argument("--headless", type=str, default="true", choices=["true", "false"], help="Run Chrome headless")
	parser.add_argument("--limit", type=int, default=10, help="Max number of new filings to process this run")
	parser.add_argument("--max-pages", type=int, default=0, help="Optional cap on pages to scan (0 = all)")
	parser.add_argument("--dry-run", action="store_true", help="Scrape and parse but skip DB writes")
	parser.add_argument("--save-scrape-json", action="store_true", help="Save scraped filings JSON to disk")
	return parser


def scrape_ptrs(year: int, headless: bool, max_pages: int) -> List[Dict]:
	logger.info(f"Starting scrape for year={year}, headless={headless}, max_pages={'ALL' if max_pages <= 0 else max_pages}")
	scraper = HouseDisclosureScraper(headless=headless)
	filings = scraper.scrape_ptr_filings(
		year=year,
		max_pages=None if max_pages <= 0 else max_pages,
		find_first_ptr=False,
	)
	if filings:
		logger.info(f"Scrape complete: {len(filings)} filings found")
	else:
		logger.warning("Scrape returned no filings")
	return filings


def filter_new_filings(filings: List[Dict], existing_doc_ids: set, limit: int) -> List[Dict]:
	new_filings: List[Dict] = []
	for f in filings:
		doc_id = f.get("doc_id")
		if not doc_id:
			continue
		if doc_id not in existing_doc_ids:
			new_filings.append(f)
			if 0 < limit <= len(new_filings):
				break
	logger.info(f"Filtered new filings: {len(new_filings)} (from {len(filings)} total scraped)")
	return new_filings


def process_filings_to_transactions(new_filings: List[Dict]) -> List[Dict]:
	"""Process each filing PDF, returning flattened transaction records with filing metadata."""
	all_transactions: List[Dict] = []
	for idx, filing in enumerate(new_filings, start=1):
		doc_id = filing.get("doc_id")
		pdf_url = filing.get("pdf_url")
		member_name = filing.get("member_name")
		office = filing.get("office")
		logger.info(f"[{idx}/{len(new_filings)}] Processing filing doc_id={doc_id} member={member_name}")
		try:
			processed = process_ptr_pdf(pdf_url, doc_id) or {}
			transactions = processed.get("transactions", [])
			for t in transactions:
				# Augment transaction with filing metadata expected by DB processor
				tx = dict(t)
				tx["doc_id"] = doc_id
				tx["member_name"] = member_name
				tx["office"] = office
				tx["pdf_url"] = pdf_url
				all_transactions.append(tx)
			logger.info(f"doc_id={doc_id}: extracted {len(transactions)} transaction(s)")
		except Exception as e:
			logger.error(f"Failed processing doc_id={doc_id}: {e}")
	return all_transactions


def persist_transactions(transactions: List[Dict], dry_run: bool) -> Dict:
	if dry_run:
		logger.info("Dry-run enabled: skipping DB writes. Preview of first transaction (if any):")
		if transactions:
			logger.info(json.dumps(transactions[0], indent=2))
		return {"dry_run": True, "transactions": len(transactions)}

	db = SupabaseDBProcessor()
	stats = db.process_transactions_batch(transactions)
	return stats


def main():
	parser = build_arg_parser()
	args = parser.parse_args()

	headless = args.headless.lower() == "true"
	year = args.year
	limit = max(0, args.limit)
	max_pages = int(args.max_pages)
	dry_run = args.dry_run

	# 1) Scrape
	filings = scrape_ptrs(year=year, headless=headless, max_pages=max_pages)
	if args.save_scrape_json:
		out_path = os.path.join(os.path.dirname(__file__), f"house_scraped_filings_{year}.json")
		with open(out_path, "w") as f:
			json.dump({"year": year, "filings": filings, "scraped_at": datetime.now().isoformat()}, f, indent=2)
		logger.info(f"Saved scraped filings JSON to {out_path}")

	if not filings:
		logger.info("Nothing to process - exiting.")
		return

	# 2) Fetch existing doc_ids
	try:
		db = SupabaseDBProcessor()
		existing_doc_ids = db.get_existing_doc_ids()
	except Exception as e:
		logger.error(f"Database initialization failed: {e}")
		return

	# 3) Filter new filings
	new_filings = filter_new_filings(filings, existing_doc_ids, limit)
	if not new_filings:
		logger.info("No new filings to process - exiting.")
		return

	# 4) Process PDFs -> transactions
	transactions = process_filings_to_transactions(new_filings)
	if not transactions:
		logger.info("No transactions extracted - exiting.")
		return

	# 5) Persist
	stats = persist_transactions(transactions, dry_run=dry_run)
	logger.info(f"Pipeline complete. Summary: {json.dumps(stats, indent=2)}")


if __name__ == "__main__":
	main()
