"""
PTR PDF Processor with LLM Integration
Processes House PTR PDFs using OpenRouter API to extract transaction data
"""

import os
import re
import json
import logging
import requests
import fitz  # PyMuPDF
import base64
from io import BytesIO
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv
import csv
from io import StringIO
import time

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

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
    logger.error("OPENROUTER_API_KEY not found in environment variables")

class PTRPDFProcessor:
    """Process House PTR PDFs to extract transaction data"""
    
    def __init__(self):
        """Initialize the processor"""
        self.api_key = OPENROUTER_API_KEY
        self.processed_docs = set()
        self.failed_docs = set()
        
    def download_pdf(self, pdf_url: str) -> Optional[bytes]:
        """
        Download PDF from URL
        
        Args:
            pdf_url: URL of the PDF file
            
        Returns:
            PDF content as bytes or None if failed
        """
        try:
            response = requests.get(pdf_url, timeout=30)
            response.raise_for_status()
            logger.info(f"Downloaded PDF from {pdf_url}")
            return response.content
        except Exception as e:
            logger.error(f"Error downloading PDF from {pdf_url}: {e}")
            return None
            
    def extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """
        Extract text from PDF content using PyMuPDF
        
        Args:
            pdf_content: PDF file content as bytes
            
        Returns:
            Extracted text from PDF
        """
        try:
            # Open PDF from bytes
            pdf_document = fitz.open(stream=pdf_content, filetype="pdf")
            
            text = ""
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                text += page.get_text()
                
            pdf_document.close()
            
            logger.info(f"Extracted {len(text)} characters from PDF")
            return text
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return ""
            
    def create_llm_prompt(self, pdf_text: str, member_info: Dict) -> str:
        """
        Create prompt for LLM to extract transaction data
        
        Args:
            pdf_text: Text extracted from PDF
            member_info: Dictionary with member information
            
        Returns:
            Formatted prompt for LLM
        """
        prompt = f"""Extract stock transactions from this House financial disclosure document.

Member Information:
- Name: {member_info.get('member_name', 'Unknown')}
- Office: {member_info.get('office', 'Unknown')}
- Document ID: {member_info.get('doc_id', 'Unknown')}

Document Text:
{pdf_text[:8000]}  # Limit text to avoid token limits

Please extract ALL stock transactions and format them as a CSV with these columns:
Transaction Date,Ticker,Asset Name,Transaction Type,Amount,Owner,Comment

Rules:
- Transaction Date: Format as MM/DD/YYYY
- Ticker: Stock ticker symbol (e.g., AAPL, GOOGL)
- Asset Name: Full company name
- Transaction Type: Must be exactly "Purchase" or "Sale"
- Amount: Use ranges like "$1,001 - $15,000" or exact amounts
- Owner: Who owns the asset (e.g., "Self", "Spouse", "Joint", "Dependent")
- Comment: Any additional notes or leave empty

Output ONLY the CSV data with header row. Include ALL transactions found in the document.
If no transactions are found, output: "NO_TRANSACTIONS_FOUND"
"""
        return prompt
        
    def call_openrouter_api(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """
        Call OpenRouter API to process the document
        
        Args:
            prompt: The prompt to send to the LLM
            max_retries: Maximum number of retry attempts
            
        Returns:
            LLM response text or None if failed
        """
        if not self.api_key:
            logger.error("OpenRouter API key not configured")
            return None
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/congress-stock-trading",
            "X-Title": "Congress Stock Trading PTR Processor"
        }
        
        payload = {
            "model": "openai/gpt-4o-mini",  # Cost-effective model
            "messages": [
                {
                    "role": "system",
                    "content": "You are a financial document analyzer specializing in extracting stock transactions from congressional disclosure forms."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,  # Low temperature for consistent extraction
            "max_tokens": 4000
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    OPENROUTER_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    logger.info(f"Successfully received LLM response")
                    return content
                    
                elif response.status_code == 429:  # Rate limit
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    
                else:
                    logger.error(f"API error: {response.status_code} - {response.text}")
                    
            except requests.exceptions.Timeout:
                logger.error(f"API request timeout on attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"Error calling OpenRouter API: {e}")
                
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                
        return None
        
    def parse_csv_response(self, csv_text: str, member_info: Dict) -> List[Dict]:
        """
        Parse CSV response from LLM into transaction dictionaries
        
        Args:
            csv_text: CSV formatted text from LLM
            member_info: Member information dictionary
            
        Returns:
            List of transaction dictionaries
        """
        transactions = []
        
        if not csv_text or csv_text.strip() == "NO_TRANSACTIONS_FOUND":
            logger.info("No transactions found in document")
            return transactions
            
        try:
            # Parse CSV
            csv_reader = csv.DictReader(StringIO(csv_text))
            
            for row in csv_reader:
                # Parse amount range
                amount_str = row.get('Amount', '')
                amount_low, amount_high = self.parse_amount_range(amount_str)
                
                # Parse transaction date
                trans_date = self.parse_date(row.get('Transaction Date', ''))
                
                transaction = {
                    'doc_id': member_info.get('doc_id'),
                    'member_name': member_info.get('member_name'),
                    'office': member_info.get('office'),
                    'transaction_date': trans_date,
                    'ticker': row.get('Ticker', '').upper(),
                    'asset_name': row.get('Asset Name', ''),
                    'transaction_type': row.get('Transaction Type', ''),
                    'amount_low': amount_low,
                    'amount_high': amount_high,
                    'owner': row.get('Owner', ''),
                    'comment': row.get('Comment', ''),
                    'pdf_url': member_info.get('pdf_url'),
                    'processed_at': datetime.now().isoformat()
                }
                
                # Validate transaction
                if transaction['ticker'] and transaction['transaction_type']:
                    transactions.append(transaction)
                    
        except Exception as e:
            logger.error(f"Error parsing CSV response: {e}")
            
        logger.info(f"Parsed {len(transactions)} transactions")
        return transactions
        
    def parse_amount_range(self, amount_str: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Parse amount range string into low and high values
        
        Args:
            amount_str: Amount range string like "$1,001 - $15,000"
            
        Returns:
            Tuple of (low_amount, high_amount)
        """
        if not amount_str:
            return None, None
            
        # Remove $ and commas
        amount_str = amount_str.replace('$', '').replace(',', '')
        
        # Check for range
        if '-' in amount_str:
            parts = amount_str.split('-')
            try:
                low = int(parts[0].strip())
                high = int(parts[1].strip())
                return low, high
            except (ValueError, IndexError):
                pass
                
        # Check for "Over" pattern
        if 'over' in amount_str.lower():
            match = re.search(r'over\s*(\d+)', amount_str.lower())
            if match:
                try:
                    return int(match.group(1)), None
                except ValueError:
                    pass
                    
        # Try single value
        try:
            value = int(amount_str.strip())
            return value, value
        except ValueError:
            pass
            
        return None, None
        
    def parse_date(self, date_str: str) -> Optional[str]:
        """
        Parse and standardize date string
        
        Args:
            date_str: Date string in various formats
            
        Returns:
            Standardized date string (YYYY-MM-DD) or None
        """
        if not date_str:
            return None
            
        # Try common date formats
        formats = [
            '%m/%d/%Y',
            '%m-%d-%Y',
            '%Y-%m-%d',
            '%B %d, %Y',
            '%b %d, %Y',
            '%m/%d/%y',
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
                
        return date_str  # Return original if can't parse
        
    def process_filing(self, filing: Dict) -> List[Dict]:
        """
        Process a single PTR filing
        
        Args:
            filing: Filing dictionary with doc_id, pdf_url, member_name, etc.
            
        Returns:
            List of extracted transactions
        """
        doc_id = filing.get('doc_id')
        pdf_url = filing.get('pdf_url')
        
        if not doc_id or not pdf_url:
            logger.warning(f"Missing doc_id or pdf_url for filing")
            return []
            
        logger.info(f"Processing filing {doc_id} for {filing.get('member_name')}")
        
        try:
            # Download PDF
            pdf_content = self.download_pdf(pdf_url)
            if not pdf_content:
                self.failed_docs.add(doc_id)
                return []
                
            # Extract text
            pdf_text = self.extract_text_from_pdf(pdf_content)
            if not pdf_text:
                logger.warning(f"No text extracted from PDF {doc_id}")
                self.failed_docs.add(doc_id)
                return []
                
            # Create prompt and call LLM
            prompt = self.create_llm_prompt(pdf_text, filing)
            llm_response = self.call_openrouter_api(prompt)
            
            if not llm_response:
                logger.error(f"No LLM response for {doc_id}")
                self.failed_docs.add(doc_id)
                return []
                
            # Parse transactions
            transactions = self.parse_csv_response(llm_response, filing)
            
            self.processed_docs.add(doc_id)
            logger.info(f"Successfully processed {doc_id}: {len(transactions)} transactions")
            
            return transactions
            
        except Exception as e:
            logger.error(f"Error processing filing {doc_id}: {e}")
            self.failed_docs.add(doc_id)
            return []
            
    def process_filings_batch(self, filings: List[Dict]) -> List[Dict]:
        """
        Process a batch of filings
        
        Args:
            filings: List of filing dictionaries
            
        Returns:
            List of all extracted transactions
        """
        all_transactions = []
        
        for i, filing in enumerate(filings):
            logger.info(f"Processing filing {i+1}/{len(filings)}")
            transactions = self.process_filing(filing)
            all_transactions.extend(transactions)
            
            # Rate limiting - pause between requests
            if i < len(filings) - 1:
                time.sleep(2)  # 2 second delay between API calls
                
        logger.info(f"Processed {len(filings)} filings, extracted {len(all_transactions)} total transactions")
        return all_transactions
        
    def save_transactions(self, transactions: List[Dict], filepath: str = None):
        """
        Save transactions to JSON file
        
        Args:
            transactions: List of transaction dictionaries
            filepath: Path to save file
        """
        if not filepath:
            filepath = os.path.join(os.path.dirname(__file__), 'extracted_transactions.json')
            
        try:
            with open(filepath, 'w') as f:
                json.dump({
                    'extraction_timestamp': datetime.now().isoformat(),
                    'total_transactions': len(transactions),
                    'transactions': transactions
                }, f, indent=2)
                
            logger.info(f"Saved {len(transactions)} transactions to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving transactions: {e}")

if __name__ == "__main__":
    # Test the processor
    processor = PTRPDFProcessor()
    
    # Test with a sample filing
    test_filing = {
        'doc_id': '20026537',
        'member_name': 'Test Member',
        'pdf_url': 'https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2025/20026537.pdf',
        'office': 'House',
        'filing_year': '2025'
    }
    
    transactions = processor.process_filing(test_filing)
    print(f"Extracted {len(transactions)} transactions")
    
    if transactions:
        print("Sample transaction:", json.dumps(transactions[0], indent=2))