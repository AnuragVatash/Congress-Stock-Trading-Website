#!/usr/bin/env python3
"""
Quick Asset Duplicate Analysis
=============================

This script quickly analyzes the database for potential duplicate assets
and provides a detailed report of what duplicates exist.
"""

import sqlite3
import os
import re
from collections import defaultdict

def normalize_ticker(ticker):
    """Normalize ticker for comparison"""
    if not ticker:
        return None
    return ticker.strip().upper()

def normalize_name(name):
    """Normalize company name for comparison"""
    if not name:
        return ""
    
    # Basic normalization
    normalized = name.strip().lower()
    
    # Remove parenthetical content
    normalized = re.sub(r'\s*\([^)]*\)', '', normalized)
    
    # Remove common suffixes
    patterns = [
        r'\s+(inc|incorporated)\.?$',
        r'\s+(llc|ltd|limited)\.?$',
        r'\s+(corp|corporation)\.?$',
        r'\s+(co|company)\.?$',
        r'\s+plc\.?$',
        r'\s+(common\s+stock|class\s+[a-z])$'
    ]
    
    for pattern in patterns:
        normalized = re.sub(pattern, '', normalized)
    
    return normalized.strip()

def analyze_database(db_path):
    """Analyze database for duplicate assets"""
    print(f"Analyzing database: {db_path}")
    print("=" * 60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all assets with transaction counts
    cursor.execute("""
        SELECT 
            a.asset_id,
            a.company_name,
            a.ticker,
            COALESCE(t.tx_count, 0) as transaction_count
        FROM Assets a
        LEFT JOIN (
            SELECT asset_id, COUNT(*) as tx_count 
            FROM Transactions 
            GROUP BY asset_id
        ) t ON a.asset_id = t.asset_id
        ORDER BY a.asset_id
    """)
    
    assets = cursor.fetchall()
    print(f"Total assets: {len(assets)}")
    
    # Group by normalized ticker
    ticker_groups = defaultdict(list)
    name_groups = defaultdict(list)
    
    for asset_id, company_name, ticker, tx_count in assets:
        norm_ticker = normalize_ticker(ticker)
        norm_name = normalize_name(company_name)
        
        if norm_ticker:
            ticker_groups[norm_ticker].append((asset_id, company_name, ticker, tx_count))
        else:
            name_groups[norm_name].append((asset_id, company_name, ticker, tx_count))
    
    # Find ticker duplicates
    ticker_duplicates = {k: v for k, v in ticker_groups.items() if len(v) > 1}
    
    # Find name duplicates
    name_duplicates = {k: v for k, v in name_groups.items() if len(v) > 1 and k}
    
    print(f"\nTicker-based duplicates: {len(ticker_duplicates)} groups")
    if ticker_duplicates:
        for ticker, group in ticker_duplicates.items():
            print(f"\n  Ticker '{ticker}' ({len(group)} assets):")
            for asset_id, company_name, orig_ticker, tx_count in group:
                tx_info = f" [{tx_count} transactions]" if tx_count > 0 else " [no transactions]"
                print(f"    ID {asset_id}: {company_name} ({orig_ticker}){tx_info}")
    
    print(f"\nName-based duplicates: {len(name_duplicates)} groups")
    if name_duplicates:
        for norm_name, group in name_duplicates.items():
            print(f"\n  Name '{norm_name}' ({len(group)} assets):")
            for asset_id, company_name, ticker, tx_count in group:
                tx_info = f" [{tx_count} transactions]" if tx_count > 0 else " [no transactions]"
                ticker_info = f" (ticker: {ticker})" if ticker else " (no ticker)"
                print(f"    ID {asset_id}: {company_name}{ticker_info}{tx_info}")
    
    # Fuzzy matching for similar names
    print(f"\n\nLooking for fuzzy name matches...")
    
    # Get assets without tickers for fuzzy matching
    no_ticker_assets = [(asset_id, company_name, tx_count) 
                       for asset_id, company_name, ticker, tx_count in assets 
                       if not ticker]
    
    potential_fuzzy = []
    for i, (id1, name1, tx1) in enumerate(no_ticker_assets):
        norm1 = normalize_name(name1)
        if len(norm1) < 3:  # Skip very short names
            continue
            
        for id2, name2, tx2 in no_ticker_assets[i+1:]:
            norm2 = normalize_name(name2)
            if len(norm2) < 3:
                continue
                
            # Simple fuzzy matching - check if one is contained in the other
            if norm1 in norm2 or norm2 in norm1:
                if abs(len(norm1) - len(norm2)) <= 3:  # Similar lengths
                    potential_fuzzy.append(((id1, name1, tx1), (id2, name2, tx2)))
    
    if potential_fuzzy:
        print(f"Found {len(potential_fuzzy)} potential fuzzy matches:")
        for (id1, name1, tx1), (id2, name2, tx2) in potential_fuzzy:
            print(f"  ID {id1}: '{name1}' [{tx1} tx]")
            print(f"  ID {id2}: '{name2}' [{tx2} tx]")
            print()
    
    # Asset type analysis
    print(f"\nAsset type analysis:")
    
    stock_count = sum(1 for _, _, ticker, _ in assets if ticker)
    bond_count = sum(1 for _, name, ticker, _ in assets 
                    if not ticker and any(word in name.lower() 
                                        for word in ['treasury', 'bond', 'note', 'bill']))
    crypto_count = sum(1 for _, name, ticker, _ in assets 
                      if not ticker and any(word in name.lower() 
                                          for word in ['bitcoin', 'crypto', 'token', 'coin']))
    other_count = len(assets) - stock_count - bond_count - crypto_count
    
    print(f"  Stocks (with ticker): {stock_count}")
    print(f"  Bonds/Treasury: {bond_count}")
    print(f"  Crypto: {crypto_count}")
    print(f"  Other: {other_count}")
    
    conn.close()
    
    # Summary
    total_duplicates = len(ticker_duplicates) + len(name_duplicates)
    if total_duplicates == 0:
        print(f"\n✅ No obvious duplicates found!")
        print("Your current cleanup script appears to be working well.")
    else:
        print(f"\n⚠️  Found {total_duplicates} duplicate groups that may need attention.")
        
        if ticker_duplicates:
            ticker_assets = sum(len(group) - 1 for group in ticker_duplicates.values())
            print(f"   - {ticker_assets} assets could be merged by ticker")
        
        if name_duplicates:
            name_assets = sum(len(group) - 1 for group in name_duplicates.values())
            print(f"   - {name_assets} assets could be merged by name")

def main():
    """Main function"""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python analyze_duplicates.py <database_file>")
        return 1
    
    db_path = sys.argv[1]
    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found")
        return 1
    
    analyze_database(db_path)
    return 0

if __name__ == "__main__":
    exit(main()) 