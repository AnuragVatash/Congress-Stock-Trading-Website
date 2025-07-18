#!/usr/bin/env python3
"""
Validate Member Photo URLs Script
================================

This script checks all Members.photo_url fields in the database to see if they
lead to a valid JPEG file. It prints a summary of how many links are invalid.
"""
import sqlite3
import os
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed


def is_jpeg_url(url, response):
    # Check content-type header
    content_type = response.headers.get('Content-Type', '').lower()
    if 'image/jpeg' in content_type:
        return True
    # Fallback: check URL ending
    if url.lower().endswith('.jpg') or url.lower().endswith('.jpeg'):
        return True
    return False


def validate_photo_urls(db_path: str, timeout: float = 5.0, max_workers: int = 20):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT member_id, name, photo_url FROM Members
        WHERE photo_url IS NOT NULL AND TRIM(photo_url) != ''
    """)
    rows = cursor.fetchall()
    conn.close()

    total = len(rows)
    invalid = []

    print(f"Checking {total} photo URLs with {max_workers} threads...")

    def check_url(member_id, name, url):
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code != 200 or not is_jpeg_url(url, resp):
                return (member_id, name, url, resp.status_code, resp.headers.get('Content-Type', ''))
        except Exception as e:
            return (member_id, name, url, str(e), None)
        return None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_row = {executor.submit(check_url, member_id, name, url): (member_id, name, url) for member_id, name, url in rows}
        for future in as_completed(future_to_row):
            result = future.result()
            if result:
                invalid.append(result)

    print(f"\nValidation complete. {len(invalid)} of {total} photo URLs are invalid.")
    if invalid:
        print("\nInvalid photo URLs:")
        for member_id, name, url, status, content_type in invalid:
            print(f"  ID: {member_id} | Name: {name} | URL: {url} | Status: {status} | Content-Type: {content_type}")


def main():
    parser = argparse.ArgumentParser(description="Validate Members.photo_url links (should be JPEGs).")
    parser.add_argument(
        "db_path",
        nargs='?',
        default=os.path.join(os.path.dirname(__file__), "combined_trades.db"),
        help="Path to the SQLite database file (default: db/combined_trades.db)"
    )
    parser.add_argument('--timeout', type=float, default=5.0, help='Timeout for HTTP requests (seconds)')
    parser.add_argument('--threads', type=int, default=20, help='Number of threads to use (default: 20)')
    args = parser.parse_args()

    if not os.path.exists(args.db_path):
        print(f"Error: Database file not found at '{args.db_path}'")
        return

    validate_photo_urls(args.db_path, timeout=args.timeout, max_workers=args.threads)

if __name__ == "__main__":
    main() 