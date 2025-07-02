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

def _merge_asset_group(cursor: sqlite3.Cursor, asset_ids: List[int], reason: str):
    """
    Given a list of asset_ids for the same asset, picks one as canonical,
    re-points all Transactions to it, and deletes the redundant Asset rows.
    The canonical ID is chosen by preferring IDs with a ticker, then the smallest ID.
    """
    if not asset_ids or len(asset_ids) < 2:
        return 0

    # Determine the best row to keep (prefer non-null ticker, then smallest id)
    cursor.execute(
        f"SELECT asset_id, company_name, ticker FROM Assets WHERE asset_id IN ({','.join('?' * len(asset_ids))})",
        asset_ids
    )
    candidates = cursor.fetchall()
    
    with_ticker = [c for c in candidates if c[2] and c[2].strip()]
    
    if with_ticker:
        canonical_id = min(c[0] for c in with_ticker)
    else:
        canonical_id = min(c[0] for c in candidates)
        
    redundant_ids = [aid for aid in asset_ids if aid != canonical_id]

    if not redundant_ids:
        return 0

    logging.info(f"Merging {len(redundant_ids)} asset(s) for '{reason}' -> canonical asset_id {canonical_id}.")

    # Re-point child records (Transactions -> Assets)
    cursor.execute(
        f"UPDATE Transactions SET asset_id = ? WHERE asset_id IN ({','.join('?' * len(redundant_ids))})",
        [canonical_id, *redundant_ids]
    )

    # Delete redundant assets
    cursor.execute(
        f"DELETE FROM Assets WHERE asset_id IN ({','.join('?' * len(redundant_ids))})",
        redundant_ids
    )
    
    return len(redundant_ids)

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

        # --- 2. Asset Cleanup ---
        logging.info("--- Cleaning up duplicate Assets ---")
        total_merged_assets = 0

        # Merge assets with the same ticker
        cursor.execute("""
            SELECT UPPER(TRIM(ticker)), GROUP_CONCAT(asset_id)
            FROM Assets
            WHERE ticker IS NOT NULL AND TRIM(ticker) != ''
            GROUP BY 1 HAVING COUNT(*) > 1
        """)
        for ticker, ids_str in cursor.fetchall():
            asset_ids = [int(i) for i in ids_str.split(',')]
            total_merged_assets += _merge_asset_group(cursor, asset_ids, f"ticker: {ticker}")

        # Merge assets without tickers based on normalized names
        cursor.execute("SELECT asset_id, company_name FROM Assets WHERE ticker IS NULL OR TRIM(ticker) = ''")
        name_assets = cursor.fetchall()
        
        norm_name_map = {}
        for asset_id, name in name_assets:
            # Normalize name: lowercase, trim, remove suffixes and parenthesized content
            norm_name = str(name or '').lower().strip()
            norm_name = re.sub(r'\s*\(.*\)', '', norm_name) # e.g. (Some Fund)
            norm_name = re.sub(r'(\s|-)?(common stock|class [a-z])$', '', norm_name)
            norm_name = re.sub(r'\s+(inc|llc|corp|ltd)\.?$', '', norm_name)
            norm_name = norm_name.strip()
            
            norm_name_map.setdefault(norm_name, []).append(asset_id)

        for name, ids in norm_name_map.items():
            if len(ids) > 1:
                total_merged_assets += _merge_asset_group(cursor, ids, f"name: {name}")

        logging.info(f"Asset cleanup complete. Merged {total_merged_assets} duplicate rows.")
        
        # --- 3. Schema Hardening ---
        logging.info("--- Hardening database schema ---")
        # Member name index
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_members_name_nocase ON Members(name COLLATE NOCASE);")
        logging.info("Ensured unique index on Members(name).")
        
        # Asset schema hardening
        try:
            cursor.execute("ALTER TABLE Assets ADD COLUMN ticker_clean TEXT GENERATED ALWAYS AS (UPPER(TRIM(ticker))) VIRTUAL;")
            logging.info("Added virtual column 'ticker_clean'.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e): raise e
        
        try:
            # This normalization is simpler than the cleanup one but handles common cases for the constraint.
            cursor.execute("""
                ALTER TABLE Assets ADD COLUMN company_clean TEXT GENERATED ALWAYS AS (
                    LOWER(TRIM(REPLACE(REPLACE(company_name, ' common stock', ''), ' inc', '')))
                ) VIRTUAL;
            """)
            logging.info("Added virtual column 'company_clean'.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e): raise e

        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_asset_ticker ON Assets(ticker_clean) WHERE ticker_clean IS NOT NULL;")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_asset_name_no_ticker ON Assets(company_clean) WHERE ticker_clean IS NULL;")
        logging.info("Ensured unique indexes on Assets for tickers and company names.")

        conn.commit()
        logging.info(f"Cleanup complete for {db_path}.")

    except Exception as e:
        conn.rollback()
        logging.error(f"Error during cleanup of {db_path}: {e}. Rolled back changes.")
    finally:
        conn.close()


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for db_filename in DB_FILES:
        db_fullpath = os.path.join(script_dir, db_filename)
        cleanup_database(db_fullpath)

if __name__ == "__main__":
    main()
