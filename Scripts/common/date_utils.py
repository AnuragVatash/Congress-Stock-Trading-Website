"""
Shared date utilities for congressional trading document processing.
Handles date parsing, validation, and the Senate notification date fallback logic.
"""
import logging
import re
from datetime import datetime
from typing import Optional, Tuple

def _format_date_to_iso(date_str_mmddyyyy: str) -> Optional[str]:
    """
    Converts MM/DD/YYYY or MM-DD-YYYY to YYYY-MM-DD. 
    Returns None if parsing fails.
    
    Args:
        date_str_mmddyyyy: Date string in various formats
        
    Returns:
        ISO formatted date string or None if parsing fails
    """
    if not date_str_mmddyyyy:
        return None
    try:
        # Normalize separators to '/'
        normalized_date_str = date_str_mmddyyyy.replace('-', '/')
        parts = normalized_date_str.split('/')
        if len(parts) == 3:
            month, day, year = parts
            if len(year) == 2:
                year = "20" + year  # Assuming 21st century
            return f"{year}-{int(month):02d}-{int(day):02d}"
        return None  # Invalid format
    except ValueError:
        logging.warning(f"Could not parse date: {date_str_mmddyyyy}")
        return None

def parse_filing_date(date_str: str) -> datetime:
    """
    Parse filing date string to datetime for sorting.
    Handles multiple date formats commonly found in congressional documents.
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        Parsed datetime object, or datetime.min if parsing fails
    """
    if not date_str or not date_str.strip():
        return datetime.min
    
    date_str = date_str.strip()
    
    try:
        # Handle different date formats that might appear
        if '/' in date_str:
            # MM/DD/YYYY format
            return datetime.strptime(date_str, '%m/%d/%Y')
        elif '-' in date_str:
            # YYYY-MM-DD or MM-DD-YYYY format
            if len(date_str.split('-')[0]) == 4:
                return datetime.strptime(date_str, '%Y-%m-%d')
            else:
                return datetime.strptime(date_str, '%m-%d-%Y')
        else:
            # If it doesn't contain date separators, it's likely not a date
            # (could be a name or other text that was incorrectly extracted)
            if any(char.isalpha() for char in date_str):
                logging.debug(f"Skipping non-date text: {date_str}")
                return datetime.min
            else:
                logging.warning(f"Unknown date format: {date_str}")
                return datetime.min
    except Exception as e:
        logging.error(f"Error parsing date '{date_str}': {e}")
        return datetime.min

def default_notification_date(transaction_date_str: str, notification_date_str: str, doc_id: str = "unknown") -> str:
    """
    Handle missing notification dates by defaulting to transaction date.
    This addresses the Senate document notification date issue.
    
    Args:
        transaction_date_str: The transaction date
        notification_date_str: The notification date (may be empty)
        doc_id: Document ID for logging
        
    Returns:
        Valid notification date string
    """
    # Fix for Senate documents: If notification date is empty, use transaction date
    if not notification_date_str or not notification_date_str.strip():
        logging.info(f"[{doc_id}] Empty notification date, defaulting to transaction date: {transaction_date_str}")
        return transaction_date_str
    
    # Validate the notification date format
    if not re.match(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', notification_date_str):
        logging.warning(f"[{doc_id}] Invalid notification date format '{notification_date_str}', defaulting to transaction date: {transaction_date_str}")
        return transaction_date_str
    
    return notification_date_str

def validate_date_format(date_str: str, doc_id: str = "unknown") -> bool:
    """
    Validate that a date string matches expected formats.
    
    Args:
        date_str: Date string to validate
        doc_id: Document ID for logging
        
    Returns:
        True if date format is valid, False otherwise
    """
    if not date_str or not date_str.strip():
        return False
    
    if not re.match(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', date_str):
        logging.warning(f"[{doc_id}] Invalid date format '{date_str}'")
        return False
    
    return True

def normalize_date_format(date_str: str) -> str:
    """
    Normalize date format to MM/DD/YYYY.
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        Normalized date string
    """
    if not date_str:
        return ""
    
    # Replace hyphens with slashes for consistency
    normalized = date_str.replace('-', '/')
    
    # Handle 2-digit years
    parts = normalized.split('/')
    if len(parts) == 3 and len(parts[2]) == 2:
        parts[2] = "20" + parts[2]
        normalized = "/".join(parts)
    
    return normalized 