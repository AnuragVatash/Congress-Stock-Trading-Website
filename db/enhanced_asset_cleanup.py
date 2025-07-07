#!/usr/bin/env python3
"""
Enhanced Asset Cleanup Script for Congressional Trading Database
==============================================================

This script provides comprehensive duplicate detection and merging for all asset types:
- Stocks (by ticker and company name)
- Crypto tokens (by symbol and name)
- Treasury bonds and CDs (by normalized descriptions)
- Other financial instruments

Features:
- Advanced name normalization for different asset types
- Comprehensive duplicate detection logic
- Safe merging with foreign key preservation
- Detailed reporting and verification
- Backup and rollback capabilities
"""

import sqlite3
import os
import logging
import re
import json
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('asset_cleanup.log'),
        logging.StreamHandler()
    ]
)

@dataclass
class AssetRecord:
    """Represents an asset record with normalized identifiers"""
    asset_id: int
    company_name: str
    ticker: Optional[str]
    normalized_ticker: Optional[str]
    normalized_name: str
    asset_type: str  # 'stock', 'crypto', 'bond', 'cd', 'other'
    has_transactions: bool = False

class EnhancedAssetCleaner:
    """Enhanced asset cleanup with comprehensive duplicate detection"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.duplicate_groups: List[List[AssetRecord]] = []
        self.merge_stats = {
            'total_assets': 0,
            'duplicates_found': 0,
            'assets_merged': 0,
            'transactions_updated': 0,
            'by_type': {}
        }
    
    def normalize_ticker(self, ticker: str) -> Optional[str]:
        """Normalize ticker symbols for comparison"""
        if not ticker or not ticker.strip():
            return None
        
        # Remove common ticker suffixes and normalize
        normalized = ticker.strip().upper()
        
        # Remove exchange suffixes (e.g., .TO, .L)
        normalized = re.sub(r'\.[A-Z]{1,3}$', '', normalized)
        
        # Remove common crypto suffixes
        normalized = re.sub(r'-(USD|USDT|BTC|ETH)$', '', normalized)
        
        return normalized if normalized else None
    
    def normalize_company_name(self, company_name: str, asset_type: str = 'stock') -> str:
        """Normalize company names for comparison based on asset type"""
        if not company_name:
            return ""
        
        # Start with basic normalization
        normalized = company_name.strip().lower()
        
        # Remove parenthetical content (often fund details or secondary info)
        normalized = re.sub(r'\s*\([^)]*\)', '', normalized)
        
        if asset_type in ['stock', 'other']:
            # Stock company normalization
            # Remove common corporate suffixes
            suffixes = [
                r'\s+(inc|incorporated)\.?$',
                r'\s+(llc|ltd|limited)\.?$', 
                r'\s+(corp|corporation)\.?$',
                r'\s+(co|company)\.?$',
                r'\s+plc\.?$',
                r'\s+(sa|nv|ag|se)\.?$',  # European corporate forms
                r'\s+(common\s+stock|class\s+[a-z])$',
                r'\s+(ordinary\s+shares?)$'
            ]
            
            for suffix_pattern in suffixes:
                normalized = re.sub(suffix_pattern, '', normalized)
        
        elif asset_type == 'crypto':
            # Crypto token normalization
            # Remove common crypto suffixes
            crypto_suffixes = [
                r'\s+token$',
                r'\s+coin$',
                r'\s+(network|protocol|chain)$',
                r'\s+(finance|defi)$'
            ]
            
            for suffix_pattern in crypto_suffixes:
                normalized = re.sub(suffix_pattern, '', normalized)
        
        elif asset_type in ['bond', 'cd']:
            # Bond/CD normalization
            # Standardize treasury terms
            normalized = re.sub(r'\bu\.?s\.?\s+', 'us ', normalized)
            normalized = re.sub(r'\btreasury\s+(bill|note|bond)s?', 'treasury', normalized)
            normalized = re.sub(r'\bcertificate\s+of\s+deposit', 'cd', normalized)
            
            # Normalize date formats (e.g., "2025" -> "25", "05/15/2025" -> "2025")
            normalized = re.sub(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', r'\3', normalized)
            normalized = re.sub(r'\b20(\d{2})\b', r'\1', normalized)
            
            # Normalize percentage notation
            normalized = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'\1pct', normalized)
        
        # Final cleanup
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def classify_asset_type(self, company_name: str, ticker: Optional[str]) -> str:
        """Classify asset type based on name and ticker patterns"""
        name_lower = company_name.lower() if company_name else ""
        
        # Crypto indicators
        crypto_indicators = [
            'bitcoin', 'ethereum', 'crypto', 'token', 'coin', 'defi',
            'blockchain', 'protocol', 'dao', 'nft'
        ]
        if any(indicator in name_lower for indicator in crypto_indicators):
            return 'crypto'
        
        # Bond/Treasury indicators
        bond_indicators = [
            'treasury', 'bond', 'note', 'bill', 'government',
            'municipal', 'corporate bond', 't-bill', 't-note'
        ]
        if any(indicator in name_lower for indicator in bond_indicators):
            return 'bond'
        
        # CD indicators
        cd_indicators = [
            'certificate of deposit', 'cd ', ' cd', 'time deposit'
        ]
        if any(indicator in name_lower for indicator in cd_indicators):
            return 'cd'
        
        # Default to stock if has ticker, otherwise other
        return 'stock' if ticker else 'other'
    
    def get_asset_records(self) -> List[AssetRecord]:
        """Retrieve all asset records with enhanced classification"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get assets with transaction count
        cursor.execute("""
            SELECT 
                a.asset_id, 
                a.company_name, 
                a.ticker,
                COALESCE(t.transaction_count, 0) as transaction_count
            FROM Assets a
            LEFT JOIN (
                SELECT asset_id, COUNT(*) as transaction_count 
                FROM Transactions 
                GROUP BY asset_id
            ) t ON a.asset_id = t.asset_id
            ORDER BY a.asset_id
        """)
        
        assets = []
        for asset_id, company_name, ticker, tx_count in cursor.fetchall():
            asset_type = self.classify_asset_type(company_name, ticker)
            
            asset = AssetRecord(
                asset_id=asset_id,
                company_name=company_name or "",
                ticker=ticker,
                normalized_ticker=self.normalize_ticker(ticker),
                normalized_name=self.normalize_company_name(company_name or "", asset_type),
                asset_type=asset_type,
                has_transactions=(tx_count > 0)
            )
            assets.append(asset)
        
        conn.close()
        return assets
    
    def find_duplicate_groups(self, assets: List[AssetRecord]) -> List[List[AssetRecord]]:
        """Find groups of duplicate assets using comprehensive matching"""
        # Group assets by their matching criteria
        ticker_groups: Dict[str, List[AssetRecord]] = {}
        name_groups: Dict[str, List[AssetRecord]] = {}
        
        for asset in assets:
            # Group by normalized ticker (for assets with tickers)
            if asset.normalized_ticker:
                key = f"{asset.asset_type}:{asset.normalized_ticker}"
                ticker_groups.setdefault(key, []).append(asset)
            
            # Group by normalized name (for assets without tickers or as secondary check)
            if asset.normalized_name:
                key = f"{asset.asset_type}:{asset.normalized_name}"
                name_groups.setdefault(key, []).append(asset)
        
        # Find duplicate groups
        duplicate_groups = []
        processed_assets = set()
        
        # Process ticker-based duplicates first (more reliable)
        for group in ticker_groups.values():
            if len(group) > 1:
                # Remove assets already processed
                group = [a for a in group if a.asset_id not in processed_assets]
                if len(group) > 1:
                    duplicate_groups.append(group)
                    processed_assets.update(a.asset_id for a in group)
        
        # Process name-based duplicates for remaining assets
        for group in name_groups.values():
            if len(group) > 1:
                # Remove assets already processed
                group = [a for a in group if a.asset_id not in processed_assets]
                if len(group) > 1:
                    duplicate_groups.append(group)
                    processed_assets.update(a.asset_id for a in group)
        
        return duplicate_groups
    
    def choose_canonical_asset(self, group: List[AssetRecord]) -> AssetRecord:
        """Choose the best asset to keep from a duplicate group"""
        # Scoring criteria (higher score = better choice)
        def score_asset(asset: AssetRecord) -> Tuple[int, int, int, int]:
            score_ticker = 1 if asset.ticker and asset.ticker.strip() else 0
            score_transactions = 1 if asset.has_transactions else 0
            score_name_length = len(asset.company_name) if asset.company_name else 0
            score_id = -asset.asset_id  # Prefer lower IDs (older entries)
            
            return (score_ticker, score_transactions, score_name_length, score_id)
        
        # Sort by score (highest first)
        sorted_group = sorted(group, key=score_asset, reverse=True)
        return sorted_group[0]
    
    def merge_duplicate_group(self, group: List[AssetRecord]) -> int:
        """Merge a group of duplicate assets"""
        if len(group) <= 1:
            return 0
        
        canonical = self.choose_canonical_asset(group)
        duplicates = [a for a in group if a.asset_id != canonical.asset_id]
        
        if not duplicates:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        
        try:
            duplicate_ids = [str(a.asset_id) for a in duplicates]
            duplicate_names = [a.company_name[:30] for a in duplicates]
            
            logging.info(f"Merging {len(duplicates)} asset(s) into canonical asset_id {canonical.asset_id}")
            logging.info(f"  Canonical: {canonical.company_name} ({canonical.ticker or 'no ticker'})")
            logging.info(f"  Duplicates: {', '.join(duplicate_names)}")
            
            # Update all foreign key references
            cursor.execute(
                f"UPDATE Transactions SET asset_id = ? WHERE asset_id IN ({','.join('?' * len(duplicates))})",
                [canonical.asset_id] + [a.asset_id for a in duplicates]
            )
            transactions_updated = cursor.rowcount
            
            # Delete duplicate assets
            cursor.execute(
                f"DELETE FROM Assets WHERE asset_id IN ({','.join('?' * len(duplicates))})",
                [a.asset_id for a in duplicates]
            )
            
            conn.commit()
            
            self.merge_stats['transactions_updated'] += transactions_updated
            self.merge_stats['assets_merged'] += len(duplicates)
            
            # Update type-specific stats
            asset_type = canonical.asset_type
            if asset_type not in self.merge_stats['by_type']:
                self.merge_stats['by_type'][asset_type] = {'groups': 0, 'assets_merged': 0}
            
            self.merge_stats['by_type'][asset_type]['groups'] += 1
            self.merge_stats['by_type'][asset_type]['assets_merged'] += len(duplicates)
            
            return len(duplicates)
            
        except Exception as e:
            conn.rollback()
            logging.error(f"Error merging asset group: {e}")
            raise
        finally:
            conn.close()
    
    def create_enhanced_indexes(self):
        """Create enhanced indexes to prevent future duplicates"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Add virtual columns for normalization if they don't exist
            try:
                cursor.execute("""
                    ALTER TABLE Assets ADD COLUMN ticker_normalized 
                    TEXT GENERATED ALWAYS AS (UPPER(TRIM(ticker))) VIRTUAL
                """)
                logging.info("Added ticker_normalized virtual column")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e).lower():
                    raise
            
            try:
                cursor.execute("""
                    ALTER TABLE Assets ADD COLUMN name_normalized 
                    TEXT GENERATED ALWAYS AS (
                        LOWER(TRIM(
                            REPLACE(
                                REPLACE(
                                    REPLACE(company_name, ' Inc.', ''),
                                    ' LLC', ''
                                ),
                                ' Corp.', ''
                            )
                        ))
                    ) VIRTUAL
                """)
                logging.info("Added name_normalized virtual column")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e).lower():
                    raise
            
            # Create unique indexes
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_assets_ticker_unique 
                ON Assets(ticker_normalized) 
                WHERE ticker_normalized IS NOT NULL AND ticker_normalized != ''
            """)
            
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_assets_name_unique 
                ON Assets(name_normalized) 
                WHERE (ticker_normalized IS NULL OR ticker_normalized = '') 
                AND name_normalized IS NOT NULL AND name_normalized != ''
            """)
            
            conn.commit()
            logging.info("Created enhanced unique indexes")
            
        except Exception as e:
            conn.rollback()
            logging.error(f"Error creating indexes: {e}")
            raise
        finally:
            conn.close()
    
    def run_analysis(self) -> Dict:
        """Run comprehensive duplicate analysis without making changes"""
        logging.info("=" * 60)
        logging.info("ASSET DUPLICATE ANALYSIS")
        logging.info("=" * 60)
        
        assets = self.get_asset_records()
        self.merge_stats['total_assets'] = len(assets)
        
        # Classify assets by type
        type_counts = {}
        for asset in assets:
            type_counts[asset.asset_type] = type_counts.get(asset.asset_type, 0) + 1
        
        logging.info(f"Total assets: {len(assets)}")
        for asset_type, count in sorted(type_counts.items()):
            logging.info(f"  {asset_type.title()}: {count}")
        
        # Find duplicates
        duplicate_groups = self.find_duplicate_groups(assets)
        self.merge_stats['duplicates_found'] = len(duplicate_groups)
        
        if not duplicate_groups:
            logging.info("\n✅ No duplicate assets found!")
            return self.merge_stats
        
        logging.info(f"\n🔍 Found {len(duplicate_groups)} duplicate groups:")
        
        total_duplicates = 0
        for i, group in enumerate(duplicate_groups, 1):
            canonical = self.choose_canonical_asset(group)
            duplicates = [a for a in group if a.asset_id != canonical.asset_id]
            total_duplicates += len(duplicates)
            
            logging.info(f"\nGroup {i} ({group[0].asset_type}):")
            logging.info(f"  👑 Keep: {canonical.company_name} (ID: {canonical.asset_id}, {canonical.ticker or 'no ticker'})")
            
            for dup in duplicates:
                tx_info = f" - {dup.has_transactions and 'HAS TRANSACTIONS' or 'no transactions'}"
                logging.info(f"  🗑️  Merge: {dup.company_name} (ID: {dup.asset_id}, {dup.ticker or 'no ticker'}){tx_info}")
        
        logging.info(f"\n📊 Summary: {total_duplicates} assets would be merged")
        
        return self.merge_stats
    
    def run_cleanup(self, dry_run: bool = True) -> Dict:
        """Run the complete asset cleanup process"""
        logging.info("=" * 60)
        logging.info(f"ASSET CLEANUP - {'DRY RUN' if dry_run else 'LIVE RUN'}")
        logging.info("=" * 60)
        
        if not dry_run:
            # Create backup
            backup_path = f"{self.db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            import shutil
            shutil.copy2(self.db_path, backup_path)
            logging.info(f"Created backup: {backup_path}")
        
        # Run analysis first
        stats = self.run_analysis()
        
        if stats['duplicates_found'] == 0:
            return stats
        
        if dry_run:
            logging.info("\n⚠️  This was a DRY RUN - no changes made")
            logging.info("Run with dry_run=False to apply changes")
            return stats
        
        # Perform actual cleanup
        logging.info("\n🔧 Performing asset cleanup...")
        
        assets = self.get_asset_records()
        duplicate_groups = self.find_duplicate_groups(assets)
        
        for group in duplicate_groups:
            self.merge_duplicate_group(group)
        
        # Create enhanced indexes
        self.create_enhanced_indexes()
        
        logging.info("\n✅ Asset cleanup completed!")
        logging.info(f"📊 Final stats:")
        logging.info(f"   Assets merged: {self.merge_stats['assets_merged']}")
        logging.info(f"   Transactions updated: {self.merge_stats['transactions_updated']}")
        
        for asset_type, type_stats in self.merge_stats['by_type'].items():
            logging.info(f"   {asset_type.title()}: {type_stats['groups']} groups, {type_stats['assets_merged']} assets merged")
        
        return self.merge_stats

def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced Asset Cleanup for Congressional Trading Database")
    parser.add_argument("database", help="Database file path")
    parser.add_argument("--analyze-only", action="store_true", help="Only analyze, don't make changes")
    parser.add_argument("--live-run", action="store_true", help="Perform actual cleanup (default is dry run)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.database):
        logging.error(f"Database file not found: {args.database}")
        return 1
    
    cleaner = EnhancedAssetCleaner(args.database)
    
    if args.analyze_only:
        cleaner.run_analysis()
    else:
        cleaner.run_cleanup(dry_run=not args.live_run)
    
    return 0

if __name__ == "__main__":
    exit(main()) 