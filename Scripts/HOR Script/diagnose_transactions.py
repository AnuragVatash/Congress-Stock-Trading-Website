#!/usr/bin/env python3
"""
Diagnostic script to analyze database contents and identify why transactions might be missing.
"""
import os
import sys
import sqlite3
import json
from datetime import datetime

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_processor import get_db_connection
from scanToTextLLM import parse_llm_transactions

def analyze_database():
    """Analyze database contents to understand why transactions are missing."""
    print("=" * 80)
    print("CONGRESS TRADING DATABASE DIAGNOSTIC")
    print("=" * 80)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Count records in each table
    print("\n1. DATABASE RECORD COUNTS:")
    tables = ['Members', 'Filings', 'Assets', 'Transactions', 'API_Requests']
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"   {table:15}: {count:6} records")
    
    # 2. Sample API Requests to see LLM responses
    print("\n2. SAMPLE API REQUESTS:")
    cursor.execute("""
        SELECT doc_id, response_status, error_message, 
               SUBSTR(llm_response, 1, 100) as response_preview,
               LENGTH(llm_response) as response_length
        FROM API_Requests 
        ORDER BY created_at DESC 
        LIMIT 10
    """)
    
    api_requests = cursor.fetchall()
    for i, (doc_id, status, error, preview, length) in enumerate(api_requests):
        print(f"   Request {i+1}:")
        print(f"     DocID: {doc_id}")
        print(f"     Status: {status}")
        print(f"     Error: {error or 'None'}")
        print(f"     Response Length: {length}")
        print(f"     Preview: {preview}...")
        print()
    
    # 3. Analyze LLM responses for parsing issues
    print("\n3. LLM RESPONSE ANALYSIS:")
    cursor.execute("""
        SELECT doc_id, llm_response, pdf_link
        FROM API_Requests 
        WHERE response_status = 200 
        AND llm_response IS NOT NULL 
        AND llm_response != ''
        ORDER BY created_at DESC 
        LIMIT 5
    """)
    
    successful_requests = cursor.fetchall()
    print(f"   Found {len(successful_requests)} successful API requests to analyze")
    
    for i, (doc_id, llm_response, pdf_link) in enumerate(successful_requests):
        print(f"\n   Document {i+1}: {doc_id}")
        print(f"   PDF: {pdf_link}")
        print(f"   LLM Response: {llm_response[:200]}...")
        
        # Try to parse the LLM response
        try:
            member_data = {'DocID': doc_id}
            parsed_transactions = parse_llm_transactions(llm_response, member_data)
            print(f"   Parsed Transactions: {len(parsed_transactions)}")
            
            if parsed_transactions:
                # Show details of first transaction
                tx = parsed_transactions[0]
                print(f"   Sample Transaction:")
                print(f"     Company: {tx.get('company_name', 'N/A')}")
                print(f"     Type: {tx.get('transaction_type_full', 'N/A')}")
                print(f"     Date: {tx.get('transaction_date_str', 'N/A')}")
                print(f"     Owner: {tx.get('owner_code', 'N/A')}")
            else:
                print(f"   ❌ No transactions parsed from response")
                # Check for special responses
                if llm_response.strip() in ['NO_TRANSACTIONS_FOUND', 'DOCUMENT_UNREADABLE', 'NO_TEXT_FOUND']:
                    print(f"   ℹ️  LLM returned special status: {llm_response.strip()}")
        except Exception as e:
            print(f"   ❌ Error parsing LLM response: {e}")
    
    # 4. Check for filings without transactions
    print("\n4. FILINGS WITHOUT TRANSACTIONS:")
    cursor.execute("""
        SELECT f.doc_id, f.url, m.name, f.filing_date
        FROM Filings f
        JOIN Members m ON f.member_id = m.member_id
        LEFT JOIN Transactions t ON f.filing_id = t.filing_id
        WHERE t.transaction_id IS NULL
        ORDER BY f.created_at DESC
        LIMIT 10
    """)
    
    filings_without_transactions = cursor.fetchall()
    print(f"   Found {len(filings_without_transactions)} filings without transactions:")
    for doc_id, url, member_name, filing_date in filings_without_transactions:
        print(f"     {doc_id} - {member_name} ({filing_date})")
    
    # 5. Check verification status
    print("\n5. VERIFICATION STATUS:")
    cursor.execute("""
        SELECT verified, COUNT(*) 
        FROM Filings 
        GROUP BY verified
    """)
    verification_stats = cursor.fetchall()
    for verified, count in verification_stats:
        status = "Verified" if verified else "Not Verified"
        print(f"   {status}: {count} filings")
    
    conn.close()

def test_transaction_parsing():
    """Test transaction parsing with sample LLM responses."""
    print("\n" + "=" * 80)
    print("TRANSACTION PARSING TEST")
    print("=" * 80)
    
    # Test cases
    test_cases = [
        {
            "name": "Valid CSV Response",
            "response": "SP,Microsoft Corporation (MSFT),P,01/15/2024,01/20/2024,$1,001 - $15,000\nDC,Apple Inc. (AAPL),S,02/10/2024,02/15/2024,$50,001 - $100,000"
        },
        {
            "name": "No Transactions Found",
            "response": "NO_TRANSACTIONS_FOUND"
        },
        {
            "name": "Document Unreadable",
            "response": "DOCUMENT_UNREADABLE"
        },
        {
            "name": "Malformed CSV",
            "response": "SP,Microsoft,P,invalid-date,01/20/2024,invalid-amount"
        }
    ]
    
    for test in test_cases:
        print(f"\nTesting: {test['name']}")
        print(f"Input: {test['response']}")
        
        try:
            member_data = {'DocID': 'TEST_DOC'}
            parsed = parse_llm_transactions(test['response'], member_data)
            print(f"Result: {len(parsed)} transactions parsed")
            
            if parsed:
                for i, tx in enumerate(parsed[:2]):  # Show first 2
                    print(f"  Transaction {i+1}: {tx.get('company_name')} - {tx.get('transaction_type_full')}")
        except Exception as e:
            print(f"Error: {e}")

def generate_recommendations():
    """Generate recommendations based on analysis."""
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    print("\n1. To fix empty transactions table:")
    print("   • Check LLM responses in API_Requests table")
    print("   • Verify transaction parsing logic works correctly")
    print("   • Look for date format or validation issues")
    print("   • Check if LLM is returning special statuses like 'NO_TRANSACTIONS_FOUND'")
    
    print("\n2. Debugging steps:")
    print("   • Run script with processing limit of 2-3 documents")
    print("   • Enable DEBUG logging to see detailed parsing")
    print("   • Check raw LLM responses for actual transaction data")
    print("   • Verify your API key is working and getting valid responses")
    
    print("\n3. Common issues:")
    print("   • LLM returns 'NO_TEXT_FOUND' for scanned PDFs")
    print("   • Date parsing fails for non-standard date formats")
    print("   • Company names are missing from LLM responses")
    print("   • Database transaction rollbacks due to validation errors")

if __name__ == "__main__":
    analyze_database()
    test_transaction_parsing()
    generate_recommendations()
    
    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80) 