#!/usr/bin/env python3
"""
Update Member Photo URLs Script
==============================

This script updates all Members.photo_url fields in the database, replacing
'theunitedstates.io' with 'unitedstates.github.io' for all non-blank photo_url values.
"""
import sqlite3
import os
import argparse


def update_photo_urls(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Find all members with a non-blank photo_url containing 'theunitedstates.io'
    cursor.execute("""
        SELECT member_id, photo_url FROM Members
        WHERE photo_url IS NOT NULL AND TRIM(photo_url) != '' AND photo_url LIKE '%theunitedstates.io%'
    """)
    rows = cursor.fetchall()
    
    updated_count = 0
    for member_id, photo_url in rows:
        new_url = photo_url.replace('theunitedstates.io', 'unitedstates.github.io')
        if new_url != photo_url:
            cursor.execute(
                "UPDATE Members SET photo_url = ? WHERE member_id = ?",
                (new_url, member_id)
            )
            updated_count += 1
    
    conn.commit()
    conn.close()
    print(f"Updated {updated_count} photo_url entr{'y' if updated_count == 1 else 'ies'} in {db_path}.")


def main():
    parser = argparse.ArgumentParser(description="Update Members.photo_url to use unitedstates.github.io.")
    parser.add_argument(
        "db_path",
        nargs='?',
        default=os.path.join(os.path.dirname(__file__), "combined_trades.db"),
        help="Path to the SQLite database file (default: db/combined_trades.db)"
    )
    args = parser.parse_args()

    if not os.path.exists(args.db_path):
        print(f"Error: Database file not found at '{args.db_path}'")
        return

    update_photo_urls(args.db_path)

if __name__ == "__main__":
    main() 