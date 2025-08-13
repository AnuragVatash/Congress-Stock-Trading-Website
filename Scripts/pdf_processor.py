"""
PDF Processor for Congressional Trading Documents
Processes PTR PDFs using LLM to extract transaction data
"""

import os
import re
import json
import logging
import sqlite3
import requests
import fitz  # PyMuPDF
from io import BytesIO
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv
import sys

# Add parent directory to path for common modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common import db_schema, ocr_utils

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# OpenRouter API configuration
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

if not OPENROUTER_API_KEY:
    logger.warning("OPENROUTER_API_KEY not found in .env file")


class PDFProcessor:
    """Processes PTR PDFs and extracts transaction data"""
    
    def __init__(self, db_path: str = None):
        """
        Initialize PDF processor
        
        Args:
            db_path: Path to SQLite database
        """
        if db_path:
            self.db_path = db_path
        else:
            self.db_path = os.path.join(os.path.dirname(__file__), 'congressional_trades.db')
            
        # Initialize database
        self._init_database()
        
        # Track processing failures
        self.text_extraction_failures = set()
        self.length_limit_failures = set()
        self.generation_ids = {}
        
        # Load previous failures
        self._load_tracking_data()
        
    def _init_database(self):
        """Initialize database with required tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            db_schema.create_tables(conn)
            conn.close()
            logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            
    def _load_tracking_data(self):
        """Load tracking data from JSON files"""
        # Load text extraction failures
        try:
            filepath = os.path.join(os.path.dirname(__file__), 'text_extraction_failures.json')
            with open(filepath, 'r') as f:
                self.text_extraction_failures = set(json.load(f))
            logger.info(f"Loaded {len(self.text_extraction_failures)} text extraction failures")
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error(f"Error loading text extraction failures: {e}")
            
        # Load generation IDs
        try:
            filepath = os.path.join(os.path.dirname(__file__), 'generation_ids.json')
            with open(filepath, 'r') as f:
                self.generation_ids = json.load(f)
            logger.info(f"Loaded {len(self.generation_ids)} generation IDs")
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error(f"Error loading generation IDs: {e}")
            
    def _save_tracking_data(self):
        """Save tracking data to JSON files"""
        # Save text extraction failures
        try:
            filepath = os.path.join(os.path.dirname(__file__), 'text_extraction_failures.json')
            with open(filepath, 'w') as f:
                json.dump(list(self.text_extraction_failures), f)
        except Exception as e:
            logger.error(f"Error saving text extraction failures: {e}")
            
        # Save generation IDs
        try:
            filepath = os.path.join(os.path.dirname(__file__), 'generation_ids.json')
            with open(filepath, 'w') as f:
                json.dump(self.generation_ids, f)
        except Exception as e:
            logger.error(f"Error saving generation IDs: {e}")
            
    def download_pdf(self, url: str) -> Optional[bytes]:
        """
        Download PDF from URL
        
        Args:
            url: URL of the PDF
            
        Returns:
            PDF content as bytes or None if failed
        """
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            logger.debug(f"Downloaded PDF from {url}")
            return response.content
        except Exception as e:
            logger.error(f"Error downloading PDF from {url}: {e}")
            return None
            
    def extract_text_from_pdf(self, pdf_content: bytes) -> Optional[str]:
        """
        Extract text from PDF content
        
        Args:
            pdf_content: PDF file content as bytes
            
        Returns:
            Extracted text or None if failed
        """
        try:
            # First try direct text extraction with PyMuPDF
            pdf_document = fitz.open(stream=pdf_content, filetype="pdf")
            text = ""
            
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                page_text = page.get_text()
                
                # Check if page has meaningful text
                if page_text and len(page_text.strip()) > 50:
                    text += page_text + "\n"
                else:
                    # Try OCR if no text found
                    logger.debug(f"Page {page_num + 1} has no text, attempting OCR")
                    ocr_text = ocr_utils.ocr_page(page)
                    if ocr_text:
                        text += ocr_text + "\n"
                        
            pdf_document.close()
            
            # Clean up the text
            text = text.strip()
            
            if len(text) < 100:
                logger.warning("Extracted text too short, likely extraction failed")
                return None
                
            return text
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return None
            
    def parse_amount_range(self, amount_range_str: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Parse amount range string into low and high values
        
        Args:
            amount_range_str: String like "$1,001 - $15,000" or "Over $1,000,000"
            
        Returns:
            Tuple of (low, high) values
        """
        if not amount_range_str:
            return None, None
            
        # Handle list input
        if isinstance(amount_range_str, list):
            amount_range_str = ''.join(amount_range_str)
            
        # Split on dash for ranges
        if '-' in amount_range_str:
            parts = amount_range_str.split('-')
            if len(parts) == 2:
                try:
                    low_str = parts[0].replace('$', '').replace(' ', '').replace(',', '')
                    high_str = parts[1].replace('$', '').replace(' ', '').replace(',', '')
                    low = int(low_str)
                    high = int(high_str)
                    return low, high
                except ValueError:
                    pass
                    
        # Handle "Over" case
        m = re.match(r'Over\s*([\d,]+)', amount_range_str, re.IGNORECASE)
        if m:
            try:
                low = int(m.group(1).replace(',', ''))
                return low, None
            except ValueError:
                pass
                
        return None, None
        
    def call_llm_api(self, text: str, doc_id: str) -> Optional[str]:
        """
        Call OpenRouter API to extract transaction data from text
        
        Args:
            text: Extracted text from PDF
            doc_id: Document ID
            
        Returns:
            LLM response or None if failed
        """
        if not OPENROUTER_API_KEY:
            logger.error("OpenRouter API key not configured")
            return None
            
        try:
            # Prepare the prompt
            prompt = f"""Extract all stock transactions from the following Periodic Transaction Report.

Format your response as a CSV with these exact columns:
Owner,Ticker,Asset,Transaction Type,Date,Amount,Company

Rules:
- Owner: Should be one of: JT (Joint), SP (Spouse), DC (Dependent Child), or blank if self
- Ticker: Stock ticker symbol (leave empty if not a stock)
- Asset: Full asset description
- Transaction Type: P (Purchase) or S (Sale) or S (partial) for partial sale
- Date: In MM/DD/YYYY format
- Amount: Range like "$1,001 - $15,000" or "Over $1,000,000"
- Company: Company name

Only include actual transactions. Skip header rows and metadata.

Document text:
{text}"""

            # Make API request
            response = requests.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/congress-trades",
                    "X-Title": "Congress Trades PTR Processor"
                },
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": 4000,
                    "temperature": 0.1
                }
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Extract generation ID if available
            if 'id' in result:
                self.generation_ids[doc_id] = result['id']
                
            # Get the response content
            if 'choices' in result and len(result['choices']) > 0:
                llm_response = result['choices'][0]['message']['content']
                logger.debug(f"LLM response received for doc_id {doc_id}")
                return llm_response
            else:
                logger.error(f"Unexpected API response structure for doc_id {doc_id}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for doc_id {doc_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error calling LLM API for doc_id {doc_id}: {e}")
            return None
            
    def parse_llm_response(self, llm_response: str) -> List[Dict]:
        """
        Parse LLM response CSV into transaction dictionaries
        
        Args:
            llm_response: CSV formatted response from LLM
            
        Returns:
            List of transaction dictionaries
        """
        transactions = []
        
        try:
            # Split into lines and process as CSV
            lines = llm_response.strip().split('\n')
            
            for line in lines:
                # Skip empty lines and headers
                if not line.strip() or 'Owner,Ticker' in line:
                    continue
                    
                # Parse CSV line
                parts = [p.strip() for p in line.split(',')]
                
                if len(parts) >= 7:
                    owner = parts[0]
                    ticker = parts[1] if parts[1] and parts[1] != 'N/A' else None
                    asset = parts[2]
                    transaction_type = parts[3]
                    date = parts[4]
                    amount = parts[5]
                    company = parts[6]
                    
                    # Parse amount range
                    amount_low, amount_high = self.parse_amount_range(amount)
                    
                    transaction = {
                        'owner_code': owner,
                        'ticker': ticker,
                        'asset': asset,
                        'company_name': company,
                        'transaction_type': transaction_type,
                        'transaction_date': date,
                        'amount_range_low': amount_low,
                        'amount_range_high': amount_high,
                        'raw_llm_csv_line': line
                    }
                    
                    transactions.append(transaction)
                    
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            
        return transactions
        
    def save_to_database(self, filing_data: Dict, transactions: List[Dict]) -> bool:
        """
        Save filing and transaction data to database
        
        Args:
            filing_data: Dictionary with filing information
            transactions: List of transaction dictionaries
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get or create member
            member_id = db_schema.get_or_create_member(cursor, filing_data['member_name'])
            
            # Insert filing
            cursor.execute("""
                INSERT INTO Filings (member_id, doc_id, url, filing_date, verified)
                VALUES (?, ?, ?, ?, ?)
            """, (member_id, filing_data['doc_id'], filing_data['pdf_url'], 
                  filing_data.get('filing_date'), 1))
            
            filing_id = cursor.lastrowid
            
            # Insert transactions
            for transaction in transactions:
                # Get or create asset
                asset_id = db_schema.get_or_create_asset(
                    cursor, 
                    transaction['company_name'],
                    transaction.get('ticker')
                )
                
                # Insert transaction
                cursor.execute("""
                    INSERT INTO Transactions (
                        filing_id, asset_id, owner_code, transaction_type,
                        transaction_date, amount_range_low, amount_range_high,
                        raw_llm_csv_line
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    filing_id, asset_id, transaction.get('owner_code'),
                    transaction['transaction_type'], transaction['transaction_date'],
                    transaction.get('amount_range_low'), transaction.get('amount_range_high'),
                    transaction['raw_llm_csv_line']
                ))
                
            conn.commit()
            conn.close()
            
            logger.info(f"Saved filing {filing_data['doc_id']} with {len(transactions)} transactions")
            return True
            
        except sqlite3.IntegrityError as e:
            logger.warning(f"Filing {filing_data['doc_id']} already exists in database")
            return False
        except Exception as e:
            logger.error(f"Error saving to database: {e}")
            return False
            
    def process_filing(self, filing_data: Dict) -> bool:
        """
        Process a single filing from scraper data
        
        Args:
            filing_data: Dictionary with filing information from scraper
            
        Returns:
            True if successful, False otherwise
        """
        doc_id = filing_data['doc_id']
        
        # Skip if already failed text extraction
        if doc_id in self.text_extraction_failures:
            logger.debug(f"Skipping {doc_id} - previous text extraction failure")
            return False
            
        logger.info(f"Processing filing {doc_id} - {filing_data['member_name']}")
        
        # Download PDF
        pdf_content = self.download_pdf(filing_data['pdf_url'])
        if not pdf_content:
            logger.error(f"Failed to download PDF for {doc_id}")
            return False
            
        # Extract text
        text = self.extract_text_from_pdf(pdf_content)
        if not text:
            logger.error(f"Failed to extract text from PDF for {doc_id}")
            self.text_extraction_failures.add(doc_id)
            self._save_tracking_data()
            return False
            
        # Call LLM API
        llm_response = self.call_llm_api(text, doc_id)
        if not llm_response:
            logger.error(f"Failed to get LLM response for {doc_id}")
            return False
            
        # Parse transactions
        transactions = self.parse_llm_response(llm_response)
        if not transactions:
            logger.warning(f"No transactions found for {doc_id}")
            # Still save the filing even if no transactions
            
        # Save to database
        success = self.save_to_database(filing_data, transactions)
        
        # Save tracking data
        self._save_tracking_data()
        
        return success
        
    def get_existing_doc_ids(self) -> set:
        """
        Get set of doc_ids already in database
        
        Returns:
            Set of existing doc_ids
        """
        try:
            conn = sqlite3.connect(self.db_path)
            doc_ids = db_schema.get_existing_doc_ids(conn)
            conn.close()
            return doc_ids
        except Exception as e:
            logger.error(f"Error getting existing doc_ids: {e}")
            return set()


def main():
    """Main function for testing the PDF processor"""
    
    # Initialize processor
    processor = PDFProcessor()
    
    # Test with a sample filing
    test_filing = {
        'doc_id': '20026537',
        'member_name': 'Allen, Hon. Richard W.',
        'pdf_url': 'https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2025/20026537.pdf',
        'filing_type': 'PTR Original',
        'office': 'GA12',
        'filing_year': '2025'
    }
    
    # Process the filing
    success = processor.process_filing(test_filing)
    
    if success:
        print(f"Successfully processed filing {test_filing['doc_id']}")
    else:
        print(f"Failed to process filing {test_filing['doc_id']}")


if __name__ == "__main__":
    main()