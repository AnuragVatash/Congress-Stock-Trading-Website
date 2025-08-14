import logging

def process_ptr_pdf(pdf_url, doc_id):
    """
    This is a placeholder function for processing a PTR PDF.
    In a real implementation, this function would download the PDF,
    extract the text, and use an LLM to extract the transactions.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Processing PDF for doc_id: {doc_id}")
    
    # This is a mock response that simulates the output of the LLM.
    # In a real implementation, this would be the result of the LLM call.
    mock_transactions = [
        {
            "transaction_date": "2024-07-26",
            "ticker": "AAPL",
            "asset_name": "Apple Inc.",
            "transaction_type": "Purchase",
            "amount_low": 1001,
            "amount_high": 15000,
            "owner": "Self",
            "comment": "Initial purchase",
        }
    ]
    
    return {"transactions": mock_transactions}
