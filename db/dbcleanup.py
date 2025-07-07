import sqlite3
import os
import logging
import re
from typing import List, Dict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Database filenames expected to live in the same directory as this script
DB_FILES = [
    "congress_trades.db",
    "senate_trades.db",
    "combined_trades.db",
]

def _find_duplicates(cursor) -> Dict[str, List[int]]:
    """Return a mapping of lowercase member names to lists of member_ids that share that name (case-insensitive) and have length > 1."""
    cursor.execute("SELECT member_id, name FROM Members")
    rows = cursor.fetchall()
    bucket: Dict[str, List[int]] = {}
    for member_id, name in rows:
        key = name.lower().strip()
        bucket.setdefault(key, []).append(member_id)
    # Keep only duplicates (more than one id)
    return {k: v for k, v in bucket.items() if len(v) > 1}

def _merge_member_group(cursor, name_key: str, member_ids: List[int]):
    """Given all member_ids that represent the *same* person, pick the smallest id as canonical,
    repoint Filings to that id, and delete the redundant member rows."""
    canonical_id = min(member_ids)
    redundant_ids = [mid for mid in member_ids if mid != canonical_id]

    if not redundant_ids:
        return 0, canonical_id  # Nothing to do

    logging.info(f"Merging {len(redundant_ids)} duplicate(s) for '{name_key}' into canonical member_id {canonical_id}.")

    # Re-point child records (Filings → Members)
    cursor.execute(
        f"""UPDATE Filings SET member_id = ? WHERE member_id IN ({','.join('?' * len(redundant_ids))})""",
        [canonical_id, *redundant_ids],
    )

    # Delete redundant members
    cursor.execute(
        f"""DELETE FROM Members WHERE member_id IN ({','.join('?' * len(redundant_ids))})""",
        redundant_ids,
    )

    return len(redundant_ids), canonical_id

def _normalize_company_name_advanced(company_name: str) -> str:
    """Enhanced company name normalization to catch more duplicates"""
    if not company_name:
        return ""
    
    # Start with basic normalization
    normalized = company_name.strip().lower()
    
    # Remove parenthetical content (often fund details or secondary info)
    normalized = re.sub(r'\s*\([^)]*\)', '', normalized)
    
    # Remove common corporate suffixes (expanded list)
    suffixes = [
        r'\s+(inc|incorporated)\.?$',
        r'\s+(llc|ltd|limited)\.?$', 
        r'\s+(corp|corporation)\.?$',
        r'\s+(co|company)\.?$',
        r'\s+plc\.?$',
        r'\s+(sa|nv|ag|se)\.?$',  # European corporate forms
        r'\s+(common\s+stock|class\s+[a-z])$',
        r'\s+(ordinary\s+shares?)$',
        r'\s+(trust|fund)s?$',
        r'\s+(holdings?|group)$',
        r'\s+and\s+(subsidiaries|affiliates)$'
    ]
    
    for suffix_pattern in suffixes:
        normalized = re.sub(suffix_pattern, '', normalized)
    
    # Normalize punctuation and spacing
    normalized = re.sub(r'[,\.&]+', ' ', normalized)  # Replace punctuation with spaces
    normalized = re.sub(r'\s+', ' ', normalized)  # Collapse multiple spaces
    
    # Handle common variations
    normalized = re.sub(r'\bu\.?s\.?\s+', 'us ', normalized)  # U.S. -> us
    normalized = re.sub(r'\bint\'?l\b', 'international', normalized)  # Int'l -> international
    
    return normalized.strip()

def _find_asset_duplicates_enhanced(cursor) -> Dict[str, List[Dict]]:
    """Find asset duplicates using enhanced normalization"""
    cursor.execute("""
        SELECT asset_id, company_name, ticker, 
               COALESCE(
                   (SELECT COUNT(*) FROM Transactions WHERE asset_id = Assets.asset_id),
                   0
               ) as transaction_count
        FROM Assets
    """)
    
    assets = cursor.fetchall()
    
    # Group by normalized identifiers
    ticker_groups = {}
    name_groups = {}
    
    for asset_id, company_name, ticker, tx_count in assets:
        asset_info = {
            'asset_id': asset_id,
            'company_name': company_name or '',
            'ticker': ticker,
            'transaction_count': tx_count
        }
        
        # Group by normalized ticker (case-insensitive, trimmed)
        if ticker and ticker.strip():
            norm_ticker = ticker.strip().upper()
            ticker_groups.setdefault(norm_ticker, []).append(asset_info)
        else:
            # Group by normalized company name for assets without tickers
            norm_name = _normalize_company_name_advanced(company_name or '')
            if norm_name:  # Only group non-empty names
                name_groups.setdefault(norm_name, []).append(asset_info)
    
    # Find groups with duplicates
    duplicate_groups = {}
    
    # Ticker-based duplicates
    for ticker, group in ticker_groups.items():
        if len(group) > 1:
            duplicate_groups[f"ticker:{ticker}"] = group
    
    # Name-based duplicates (for assets without tickers)
    for name, group in name_groups.items():
        if len(group) > 1:
            duplicate_groups[f"name:{name}"] = group
    
    return duplicate_groups

def _merge_asset_group(cursor: sqlite3.Cursor, asset_infos: List[Dict], reason: str):
    """
    Given a list of asset_infos for the same asset, picks one as canonical,
    re-points all Transactions to it, and deletes the redundant Asset rows.
    Enhanced to prefer assets with tickers and transaction history.
    """
    if not asset_infos or len(asset_infos) < 2:
        return 0

    # Choose canonical asset using enhanced criteria
    def score_asset(asset_info):
        """Score asset for canonical selection (higher is better)"""
        score = 0
        
        # Prefer assets with tickers
        if asset_info['ticker'] and asset_info['ticker'].strip():
            score += 1000
        
        # Prefer assets with transactions
        if asset_info['transaction_count'] > 0:
            score += 100
        
        # Prefer longer company names (more complete)
        score += len(asset_info['company_name'])
        
        # Prefer lower IDs (older entries) as tiebreaker
        score -= asset_info['asset_id'] * 0.001
        
        return score
    
    # Sort by score (highest first)
    sorted_assets = sorted(asset_infos, key=score_asset, reverse=True)
    canonical = sorted_assets[0]
    duplicates = sorted_assets[1:]
    
    canonical_id = canonical['asset_id']
    duplicate_ids = [a['asset_id'] for a in duplicates]
    
    logging.info(f"Merging {len(duplicate_ids)} asset(s) for '{reason}' -> canonical asset_id {canonical_id}")
    logging.info(f"  Canonical: {canonical['company_name']} (ticker: {canonical['ticker'] or 'none'}, {canonical['transaction_count']} transactions)")
    
    for dup in duplicates:
        logging.info(f"  Merging: {dup['company_name']} (ticker: {dup['ticker'] or 'none'}, {dup['transaction_count']} transactions)")

    # Re-point child records (Transactions -> Assets)
    cursor.execute(
        f"UPDATE Transactions SET asset_id = ? WHERE asset_id IN ({','.join('?' * len(duplicate_ids))})",
        [canonical_id] + duplicate_ids
    )

    # Delete redundant assets
    cursor.execute(
        f"DELETE FROM Assets WHERE asset_id IN ({','.join('?' * len(duplicate_ids))})",
        duplicate_ids
    )
    
    return len(duplicate_ids)

def cleanup_database(db_path: str):
    logging.info(f"\n===== Cleaning database: {db_path} =====")
    if not os.path.exists(db_path):
        logging.warning(f"Database file not found: {db_path}. Skipping.")
        return

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    try:
        conn.execute("BEGIN TRANSACTION;")

        # --- 1. Member Cleanup ---
        logging.info("--- Cleaning up duplicate Members ---")
        duplicates = _find_duplicates(cursor)
        total_removed_members = 0

        for name_key, ids in duplicates.items():
            removed, _ = _merge_member_group(cursor, name_key, ids)
            total_removed_members += removed
            
        logging.info(f"Member cleanup complete. Merged {total_removed_members} duplicate rows.")

        # --- 2. Enhanced Asset Cleanup ---
        logging.info("--- Cleaning up duplicate Assets (Enhanced) ---")
        total_merged_assets = 0
        
        # Use enhanced duplicate detection
        duplicate_groups = _find_asset_duplicates_enhanced(cursor)
        
        if duplicate_groups:
            logging.info(f"Found {len(duplicate_groups)} duplicate groups to process")
            
            for reason, asset_group in duplicate_groups.items():
                merged_count = _merge_asset_group(cursor, asset_group, reason)
                total_merged_assets += merged_count
        else:
            logging.info("No duplicate asset groups found")

        logging.info(f"Enhanced asset cleanup complete. Merged {total_merged_assets} duplicate rows.")
        
        # --- 3. Schema Hardening ---
        logging.info("--- Hardening database schema ---")
        
        # Member name index
        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_members_name_nocase ON Members(name COLLATE NOCASE);")
            logging.info("Ensured unique index on Members(name).")
        except sqlite3.OperationalError as e:
            if "UNIQUE constraint failed" in str(e):
                logging.warning("Some duplicate members still exist - manual review may be needed")
            else:
                logging.warning(f"Could not create member index: {e}")
        
        # Enhanced asset schema hardening
        try:
            cursor.execute("ALTER TABLE Assets ADD COLUMN ticker_clean TEXT GENERATED ALWAYS AS (UPPER(TRIM(ticker))) VIRTUAL;")
            logging.info("Added virtual column 'ticker_clean'.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e): 
                logging.debug(f"Ticker column creation: {e}")

        try:
            # Enhanced company name normalization for the constraint
            cursor.execute("""
                ALTER TABLE Assets ADD COLUMN company_clean TEXT GENERATED ALWAYS AS (
                    LOWER(TRIM(REPLACE(REPLACE(REPLACE(REPLACE(
                        company_name, 
                        ' common stock', ''), 
                        ' inc.', ''), 
                        ' inc', ''), 
                        ' corp', '')))
                ) VIRTUAL;
            """)
            logging.info("Added virtual column 'company_clean'.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e): 
                logging.debug(f"Company column creation: {e}")

        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_asset_ticker ON Assets(ticker_clean) WHERE ticker_clean IS NOT NULL AND ticker_clean != '';")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_asset_name_no_ticker ON Assets(company_clean) WHERE (ticker_clean IS NULL OR ticker_clean = '') AND company_clean IS NOT NULL AND company_clean != '';")
            logging.info("Ensured unique indexes on Assets for tickers and company names.")
        except sqlite3.OperationalError as e:
            if "UNIQUE constraint failed" in str(e):
                logging.warning("Some duplicate assets still exist after cleanup - manual review may be needed")
            else:
                logging.warning(f"Could not create asset indexes: {e}")

        conn.commit()
        logging.info(f"Cleanup complete for {db_path}.")

    except Exception as e:
        conn.rollback()
        logging.error(f"Error during cleanup of {db_path}: {e}. Rolled back changes.")
        raise
    finally:
        conn.close()


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for db_filename in DB_FILES:
        db_fullpath = os.path.join(script_dir, db_filename)
        cleanup_database(db_fullpath)

if __name__ == "__main__":
    main()
