#!/usr/bin/env python3
"""
Interactive Member Merging Script
=================================

This script provides an interactive command-line interface to find and merge
duplicate member records in the database.
"""
import sqlite3
import os
import logging
from collections import defaultdict
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_last_name(name: str) -> str:
    """
    Extracts a plausible last name from a full name string for grouping.
    It handles common suffixes and different name formats.
    """
    name = name.strip()
    
    # Handle "Last, First" format, which may include suffixes in the first name part
    if ',' in name:
        base_name = name.split(',')[0]
        # It could also be "First Last, Suffix"
        if len(name.split(',')) > 1:
            suffix_part = name.split(',')[1].strip().lower().replace('.', '')
            suffixes = ['jr', 'sr', 'i', 'ii', 'iii', 'iv', 'v']
            if suffix_part in suffixes:
                # Format is "First M Last, Suffix"
                return base_name.strip().split()[-1]
        return base_name.strip()

    # Handle "First M. Last Suffix" format
    parts = name.split()
    if len(parts) > 1:
        suffixes = ['jr', 'sr', 'i', 'ii', 'iii', 'iv', 'v']
        last_word = parts[-1].lower().replace('.', '')
        if last_word in suffixes:
            return parts[-2]
    
    return parts[-1] if parts else ""

def find_duplicate_groups(cursor: sqlite3.Cursor) -> dict:
    """Finds potential duplicate members by grouping by last name."""
    cursor.execute("SELECT member_id, name FROM Members ORDER BY name")
    members = cursor.fetchall()
    
    groups = defaultdict(list)
    for member_id, name in members:
        last_name = get_last_name(name)
        if last_name:
            groups[last_name].append({'id': member_id, 'name': name})
            
    return {name: group for name, group in groups.items() if len(group) > 1}

def merge_member_records(db_path: str, id1: int, id2: int):
    """
    Merges two member records. The one with the lower ID is kept and
    updated with data from the one with the higher ID.
    """
    low_id = min(id1, id2)
    high_id = max(id1, id2)
    
    logging.info(f"Beginning merge of member {high_id} into {low_id}")
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN TRANSACTION;")
        
        # 1. Get data from the higher_id member
        cursor.execute("SELECT chamber, party, state, photo_url FROM Members WHERE member_id = ?", (high_id,))
        data_to_move = cursor.fetchone()
        
        if not data_to_move:
            raise ValueError(f"Member with ID {high_id} not found.")
        
        # Get names for logging
        cursor.execute("SELECT name FROM Members WHERE member_id = ?", (low_id,))
        low_id_name = cursor.fetchone()[0]
        cursor.execute("SELECT name FROM Members WHERE member_id = ?", (high_id,))
        high_id_name = cursor.fetchone()[0]

        logging.info(f"Canonical member: {low_id} ('{low_id_name}')")
        logging.info(f"Redundant member: {high_id} ('{high_id_name}')")
        
        # 2. Update the lower_id member
        update_query = "UPDATE Members SET chamber = ?, party = ?, state = ?, photo_url = ? WHERE member_id = ?"
        cursor.execute(update_query, (*data_to_move, low_id))
        logging.info(f"Updated member {low_id} with details from member {high_id}.")
        print(f"\nUpdated '{low_id_name}' with data from '{high_id_name}'.")

        # 3. Re-point Filings from high_id to low_id
        cursor.execute("UPDATE Filings SET member_id = ? WHERE member_id = ?", (low_id, high_id))
        filings_count = cursor.rowcount
        logging.info(f"Reassigned {filings_count} filings from member {high_id} to {low_id}.")
        print(f"Reassigned {filings_count} filings.")

        # 4. Delete the higher_id member
        cursor.execute("DELETE FROM Members WHERE member_id = ?", (high_id,))
        logging.info(f"Deleted member {high_id}.")
        print(f"Deleted member record for '{high_id_name}' ({high_id}).")
        
        conn.commit()
        print("\n✅ Merge successful!")

    except Exception as e:
        conn.rollback()
        logging.error(f"An error occurred during merge: {e}. Transaction rolled back.")
        print(f"\n❌ An error occurred: {e}. Transaction rolled back.")
    finally:
        conn.close()

def main():
    """Main interactive loop for the script."""
    parser = argparse.ArgumentParser(description="Interactively merge duplicate member records.")
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

    print("Starting interactive member merge tool...")
    skipped_pairs = set()

    # --- PHASE 1: Process all pairs ---
    print("\n--- Phase 1: Processing pairs (groups of 2) ---")
    conn = sqlite3.connect(args.db_path)
    cursor = conn.cursor()
    initial_duplicate_groups = find_duplicate_groups(cursor)
    conn.close()

    pairs = {name: members for name, members in initial_duplicate_groups.items() if len(members) == 2}
    
    if not pairs:
        print("No pairs found to process.")
    else:
        print(f"Found {len(pairs)} pairs to review.")
        for i, (last_name, members) in enumerate(pairs.items()):
            print(f"\n--- Reviewing Pair {i+1} of {len(pairs)} ---")
            print(f"Last Name: {last_name}")
            for member in members:
                print(f"  ID: {member['id']:<5} Name: {member['name']}")

            merge_choice = input("\nPress Enter to merge this pair, or any other key to skip (or 'q' to quit phase 1): ")

            if merge_choice.lower() == 'q':
                print("Skipping to Phase 2.")
                break

            if merge_choice == '':
                id1, id2 = members[0]['id'], members[1]['id']
                merge_member_records(args.db_path, id1, id2)
            else:
                pair_ids = frozenset({members[0]['id'], members[1]['id']})
                skipped_pairs.add(pair_ids)
                print("Skipping merge for this pair.")

            if i < len(pairs) - 1:
                input("\nPress Enter to continue to the next pair...")

    # --- PHASE 2: Process larger groups ---
    print("\n\n--- Phase 2: Processing larger groups (3+ members) ---")

    skipped_groups = set()  # Track skipped groups by their member ID sets

    while True:
        # Re-fetch groups from the DB to get the current state after pair merges
        conn = sqlite3.connect(args.db_path)
        cursor = conn.cursor()
        current_duplicate_groups = find_duplicate_groups(cursor)
        conn.close()

        # Filter for groups with 2+ members (not just 3+)
        all_groups = {name: members for name, members in current_duplicate_groups.items() if len(members) > 1}

        # Filter out skipped groups (by member ID set) and skipped pairs from phase 1
        display_groups = []
        for last_name, members in all_groups.items():
            member_ids_set = frozenset(m['id'] for m in members)
            if member_ids_set in skipped_groups:
                continue
            if len(members) == 2 and member_ids_set in skipped_pairs:
                continue
            display_groups.append((last_name, members, member_ids_set))

        if not display_groups:
            print("\nNo more groups to process. All done!")
            break

        print("\n--- Potential Duplicate Groups (2+ members) ---")
        for i, (last_name, members, _) in enumerate(display_groups):
            print(f"  [{i+1}] {last_name} ({len(members)} members)")

        try:
            choice = input("\nEnter group number to inspect (or 'q' to quit): ")
            if choice.lower() == 'q':
                print("Exiting tool.")
                break
            
            group_idx = int(choice) - 1
            if not (0 <= group_idx < len(display_groups)):
                print("Invalid group number.")
                continue

            _, selected_group, group_id_set = display_groups[group_idx]
            
            print("\n--- Members in Selected Group ---")
            for idx, member in enumerate(selected_group, 1):
                print(f"  {idx}. ID: {member['id']:<5} Name: {member['name']}")
            
            ids_str = input("\nEnter two numbers to merge (e.g., 1,2), or 's' to skip this group: ")
            if ids_str.lower() == 's':
                skipped_groups.add(group_id_set)
                print("Skipping this group for this session.")
                continue
            
            id_parts = [p.strip() for p in ids_str.split(',')]
            if len(id_parts) != 2 or not all(p.isdigit() for p in id_parts):
                print("Invalid input. Please enter exactly two numbers.")
                continue
            
            idx1, idx2 = int(id_parts[0]), int(id_parts[1])
            if not (1 <= idx1 <= len(selected_group)) or not (1 <= idx2 <= len(selected_group)) or idx1 == idx2:
                print("Invalid selection. Please pick two different valid numbers from the list.")
                continue
            
            id1 = selected_group[idx1 - 1]['id']
            id2 = selected_group[idx2 - 1]['id']
            merge_member_records(args.db_path, id1, id2)
            input("\nPress Enter to continue...")

        except (ValueError, IndexError):
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\nExiting.")
            break
            
if __name__ == "__main__":
    main() 