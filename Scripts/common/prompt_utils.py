"""
Shared prompt utilities for congressional trading document processing.
Uses Jinja2 templates for maintainable and configurable LLM prompts.
"""
import os
import logging
from typing import Optional, Dict, Any

try:
    from jinja2 import Environment, FileSystemLoader, Template
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False
    logging.warning("Jinja2 not available. Install with: pip install jinja2")

class PromptGenerator:
    """
    Generator for LLM prompts using Jinja2 templates.
    """
    
    def __init__(self, template_dir: str = None):
        """
        Initialize prompt generator.
        
        Args:
            template_dir: Directory containing Jinja2 templates
        """
        if template_dir is None:
            template_dir = os.path.join(os.path.dirname(__file__), 'prompts')
        
        self.template_dir = template_dir
        self.env = None
        
        if JINJA2_AVAILABLE:
            try:
                self.env = Environment(loader=FileSystemLoader(template_dir))
                logging.info(f"Initialized Jinja2 environment with template dir: {template_dir}")
            except Exception as e:
                logging.warning(f"Failed to initialize Jinja2 environment: {e}")
                self.env = None
        
        # Fallback prompt for when Jinja2 is not available
        self.fallback_prompt = self._get_fallback_prompt()
    
    def _get_fallback_prompt(self) -> str:
        """Get fallback prompt when Jinja2 is not available."""
        return """**Task Objective:**
Identify and extract all financial transactions from the provided text. Format each transaction as a single line in a CSV (Comma Separated Values) structure.

**CSV Output Format (Strict Order - 6 Columns):**
1.  **Owner Code:** (e.g., SP, DC, JT, or leave blank if not specified for the filer themselves). This code indicates the owner of the asset.
2.  **Asset Description:** The full name of the asset, including any ticker symbol found in parentheses (e.g., Microsoft Corporation (MSFT), Some Bond Fund). If a ticker is present, include it.
3.  **Transaction Type Code:** A single letter: 'P' for Purchase, 'S' for Sale, or 'E' for Exchange.
4.  **Transaction Date:** The date the transaction occurred, formatted as MM/DD/YYYY.
5.  **Notification Date:** The date the transaction was reported or notified, formatted as MM/DD/YYYY. If no notification date is visible, use the same date as the transaction date.
6.  **Amount Range:** The transaction value range (e.g., $1,001 - $15,000, $50,000, Over $1,000,000).

**Critical Processing Rules - Adhere Strictly:**
*   **Rule 1: Literal Extraction:** Only extract transaction data that is explicitly and clearly visible in the text. Do NOT infer, guess, or create data not present.
*   **Rule 2: Column Integrity:** Ensure each CSV row has exactly 6 comma-separated values corresponding to the columns above.
*   **Rule 3: Ticker Inclusion:** If a ticker symbol (e.g., MSFT, AAPL) is part of the asset description in the text, include it within parentheses at the end of the Asset Description field.
*   **Rule 4: Date Format:** All dates MUST be in MM/DD/YYYY format. If a date is in a different format in the text, attempt to convert it. If conversion is not possible or the date is unclear, you may have to omit the transaction.
*   **Rule 4a: Missing Notification Date:** If no separate notification date is visible in the document, use the transaction date for both the transaction date and notification date fields.
*   **Rule 5: Blank Owner Code:** If the owner is the filer and no specific code (SP, DC, JT) is shown for a transaction, leave the 'Owner Code' field blank (i.e., ``,Asset Description,...`).
*   **Rule 6: Handling Commas within Fields:** If an 'Asset Description' or 'Amount Range' naturally contains a comma, enclose that entire field in double quotes. For example: `SP,"Big Company, LLC (BCLLC)",P,01/01/2024,01/05/2024,"$1,001,000 - $5,000,000"`
*   **Rule 7: No Transactions Found:** If, after careful analysis of the text, you find NO discernible financial transactions, your entire output should be the single line: `NO_TRANSACTIONS_FOUND`
*   **Rule 8: Unclear/Corrupted Data:** If the text is too unclear or appears corrupted, output the single line: `DOCUMENT_UNREADABLE`
*   **Rule 9: No Extra Text:** Your final output should ONLY be the CSV data lines, or one of the special strings (`NO_TRANSACTIONS_FOUND`, `DOCUMENT_UNREADABLE`). Do not include any headers, explanations, introductions, or summaries.

Text to process:
{document_text}"""
    
    def generate_financial_csv_prompt(self, 
                                    document_text: str, 
                                    document_type: Optional[str] = None,
                                    has_notification_date: bool = True,
                                    **kwargs) -> str:
        """
        Generate a prompt for financial CSV extraction.
        
        Args:
            document_text: The text content to process
            document_type: Type of document (senate_table, house_pdf, image_scan)
            has_notification_date: Whether the document type typically has notification dates
            **kwargs: Additional template variables
            
        Returns:
            Generated prompt string
        """
        if self.env is None:
            # Use fallback prompt
            return self.fallback_prompt.format(document_text=document_text)
        
        try:
            template = self.env.get_template('financial_csv.j2')
            
            # Prepare template variables
            template_vars = {
                'document_text': document_text,
                'document_type': document_type,
                'has_notification_date': has_notification_date,
                **kwargs
            }
            
            return template.render(**template_vars)
            
        except Exception as e:
            logging.warning(f"Failed to render template, using fallback: {e}")
            return self.fallback_prompt.format(document_text=document_text)
    
    def get_system_instruction(self, specialized: bool = False) -> str:
        """
        Get system instruction for LLM.
        
        Args:
            specialized: Whether to use specialized instruction for congressional documents
            
        Returns:
            System instruction string
        """
        if specialized:
            return """You are an expert data extraction assistant specializing in congressional financial disclosure documents. Your task is to meticulously analyze financial disclosure document text and extract specific transaction details. You have extensive experience with House and Senate filing formats, understand various document types (PDFs, tables, scanned images), and can handle data quality issues common in government documents. Adhere strictly to the formatting and rules provided."""
        else:
            return """You are an expert data extraction assistant. Your task is to meticulously analyze financial disclosure document text and extract specific transaction details. Adhere strictly to the formatting and rules provided."""

# Global prompt generator instance
_prompt_generator = None

def get_prompt_generator() -> PromptGenerator:
    """Get global prompt generator instance."""
    global _prompt_generator
    if _prompt_generator is None:
        _prompt_generator = PromptGenerator()
    return _prompt_generator

def generate_financial_prompt(document_text: str, 
                            document_source: str = "unknown",
                            **kwargs) -> tuple[str, str]:
    """
    Generate a complete prompt for financial document processing.
    
    Args:
        document_text: The document text to process
        document_source: Source of the document (house, senate, etc.)
        **kwargs: Additional prompt parameters
        
    Returns:
        Tuple of (system_instruction, user_prompt)
    """
    generator = get_prompt_generator()
    
    # Determine document type and notification date handling
    document_type = None
    has_notification_date = True
    
    if document_source.lower() == "senate":
        document_type = "senate_table"
        has_notification_date = False  # Senate documents often lack notification dates
    elif document_source.lower() == "house":
        document_type = "house_pdf"
        has_notification_date = True
    elif "image" in document_source.lower() or "scan" in document_source.lower():
        document_type = "image_scan"
        has_notification_date = True
    
    # Generate system instruction
    system_instruction = generator.get_system_instruction(specialized=True)
    
    # Generate user prompt
    user_prompt = generator.generate_financial_csv_prompt(
        document_text=document_text,
        document_type=document_type,
        has_notification_date=has_notification_date,
        **kwargs
    )
    
    return system_instruction, user_prompt

def check_template_availability() -> dict:
    """
    Check template system availability.
    
    Returns:
        Dictionary with availability status
    """
    generator = get_prompt_generator()
    template_dir = generator.template_dir
    
    templates_available = False
    if os.path.exists(template_dir):
        template_files = [f for f in os.listdir(template_dir) if f.endswith('.j2')]
        templates_available = len(template_files) > 0
    
    return {
        'jinja2': JINJA2_AVAILABLE,
        'template_dir_exists': os.path.exists(template_dir),
        'templates_available': templates_available,
        'template_dir': template_dir
    } 