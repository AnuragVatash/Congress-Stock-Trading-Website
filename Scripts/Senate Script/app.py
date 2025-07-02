from flask import Flask, render_template, jsonify, request
import os
import json
from datetime import datetime
import logging
import threading
from queue import Queue
import time

# Create a dedicated module for shared variables to avoid circular imports
# Define the deleted_doc_ids set here as a global
deleted_doc_ids = set()

# File to store deleted document IDs for breakpoint purposes
DELETED_DOCS_FILE = os.path.join(os.path.dirname(__file__), 'senate_deleted_docs.json')

# Import remaining modules after declaring global variables
from scanToTextLLM import scan_with_openrouter, parse_llm_transactions
from senate_db_processor import get_db_connection, create_tables

app = Flask(__name__)

# Stats variables for tracking verification and deletion counts
verification_count = 0
deletion_count = 0

# Background task queue
verification_queue = Queue()

def background_verification_worker():
    """Background worker to process verification tasks."""
    global verification_count
    
    while True:
        try:
            # Get task from queue
            task = verification_queue.get()
            if task is None:
                break
                
            doc_id, url, member_name, filing_id = task
            
            try:
                # Process the document
                member_data = {'DocID': doc_id, 'Name': member_name}
                llm_output = scan_with_openrouter(url, member_data)
                
                # Parse the transactions
                parsed_transactions = parse_llm_transactions(llm_output, member_data)
                
                # Mark the document as verified
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE Filings SET verified = 1 WHERE filing_id = ?', (filing_id,))
                conn.commit()
                conn.close()
                
                # Increment verification count
                verification_count += 1
                
                logging.info(f"Background verification completed for doc_id: {doc_id}")
            except Exception as e:
                logging.error(f"Error in background verification for doc_id {doc_id}: {e}", exc_info=True)
        except Exception as e:
            logging.error(f"Error in background worker: {e}", exc_info=True)
        finally:
            verification_queue.task_done()

# Start background worker
worker_thread = threading.Thread(target=background_verification_worker, daemon=True)
worker_thread.start()

# Load any previously deleted doc_ids from file
def load_deleted_doc_ids():
    global deleted_doc_ids
    try:
        if os.path.exists(DELETED_DOCS_FILE):
            with open(DELETED_DOCS_FILE, 'r') as f:
                deleted_doc_ids = set(json.load(f))
            logging.info(f"Loaded {len(deleted_doc_ids)} tracked document IDs for breakpoints")
    except Exception as e:
        logging.error(f"Error loading deleted doc IDs: {e}")

# Save the current set of deleted doc_ids to file
def save_deleted_doc_ids():
    try:
        with open(DELETED_DOCS_FILE, 'w') as f:
            json.dump(list(deleted_doc_ids), f)
        logging.info(f"Saved {len(deleted_doc_ids)} tracked document IDs")
    except Exception as e:
        logging.error(f"Error saving deleted doc IDs: {e}")

# Load on startup
load_deleted_doc_ids()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# Initialize database tables
try:
    create_tables()
    logging.info("Database tables initialized successfully")
except Exception as e:
    logging.error(f"Error initializing database tables: {e}", exc_info=True)

def get_owner_description(code):
    """Convert owner code to full description."""
    owner_map = {
        '': 'Self',
        'SP': 'Spouse',
        'DC': 'Dependent Child',
        'JT': 'Joint Account'
    }
    return owner_map.get(code, code)

# Register the function as a Jinja2 filter
app.jinja_env.filters['get_owner_description'] = get_owner_description

def get_processed_documents(page=1, per_page=50):
    """Get processed documents from the database with pagination."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Calculate offset for pagination
    offset = (page - 1) * per_page
    
    # Get total count for pagination info
    cursor.execute('SELECT COUNT(*) FROM Filings WHERE verified = 0')
    total_count = cursor.fetchone()[0]
    
    # Get paginated filings with their member names and URLs
    cursor.execute('''
        SELECT f.filing_id, f.doc_id, f.url, f.filing_date, m.name as member_name
        FROM Filings f
        JOIN Members m ON f.member_id = m.member_id
        WHERE f.verified = 0
        ORDER BY f.filing_date DESC
        LIMIT ? OFFSET ?
    ''', (per_page, offset))
    
    filings = []
    for row in cursor.fetchall():
        filing_id, doc_id, url, filing_date, member_name = row
        
        # Get transaction count (not full transactions for performance)
        cursor.execute('SELECT COUNT(*) FROM Transactions WHERE filing_id = ?', (filing_id,))
        transaction_count = cursor.fetchone()[0]
        
        filings.append({
            'filing_id': filing_id,
            'doc_id': doc_id,
            'url': url,
            'filing_date': filing_date,
            'member_name': member_name,
            'transaction_count': transaction_count,
            'transactions': []  # Don't load full transactions for list view
        })
    
    conn.close()
    
    # Calculate pagination info
    total_pages = (total_count + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages
    
    return {
        'documents': filings,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total_count,
            'total_pages': total_pages,
            'has_prev': has_prev,
            'has_next': has_next,
            'prev_page': page - 1 if has_prev else None,
            'next_page': page + 1 if has_next else None
        }
    }

@app.route('/')
def index():
    """Main page showing unverified documents with pagination."""
    # Get page number from query parameters
    page = int(request.args.get('page', 1))
    per_page = 20  # Smaller page size for better performance
    
    # Load documents with pagination
    result = get_processed_documents(page=page, per_page=per_page)
    documents = result['documents']
    pagination = result['pagination']
    
    # Load text extraction and length limit failures for labeling
    text_extraction_failures = set()
    length_limit_failures = set()
    
    try:
        filepath = os.path.join(os.path.dirname(__file__), 'senate_text_extraction_failures.json')
        with open(filepath, 'r') as f:
            text_extraction_failures = set(json.load(f))
    except FileNotFoundError:
        pass
        
    try:
        filepath = os.path.join(os.path.dirname(__file__), 'senate_length_limit_failures.json')
        with open(filepath, 'r') as f:
            length_limit_failures = set(json.load(f))
    except FileNotFoundError:
        pass
    
    # Add failure type labels to documents that have them
    for doc in documents:
        doc_id = doc.get('doc_id')
        doc['failure_type'] = []
        
        if doc_id in text_extraction_failures:
            doc['failure_type'].append('No Text Found')
        if doc_id in length_limit_failures:
            doc['failure_type'].append('Token Limit Reached')
    
    return render_template('index.html', documents=documents, pagination=pagination)

@app.route('/api/document/<doc_id>/transactions')
def get_document_transactions(doc_id):
    """Get detailed transactions for a specific document."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get filing_id for the document
        cursor.execute('SELECT filing_id FROM Filings WHERE doc_id = ?', (doc_id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Document not found'}), 404
            
        filing_id = result[0]
        
        # Get transactions for this filing
        cursor.execute('''
            SELECT t.transaction_id, t.owner_code, t.transaction_type, 
                   t.transaction_date, t.amount_range_low, t.amount_range_high,
                   t.raw_llm_csv_line,
                   a.company_name, a.ticker
            FROM Transactions t
            JOIN Assets a ON t.asset_id = a.asset_id
            WHERE t.filing_id = ?
            ORDER BY a.company_name ASC
        ''', (filing_id,))
        
        transactions = []
        for tx in cursor.fetchall():
            transactions.append({
                'transaction_id': tx[0],
                'owner_code': tx[1],
                'transaction_type': tx[2],
                'transaction_date': tx[3],
                'amount_range_low': tx[4],
                'amount_range_high': tx[5],
                'raw_llm_line': tx[6],
                'company_name': tx[7],
                'ticker': tx[8]
            })
        
        conn.close()
        return jsonify(transactions)
        
    except Exception as e:
        logging.error(f"Error getting transactions for document {doc_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/verify/<doc_id>')
def verify_document(doc_id):
    """Start verification process for a document."""
    try:
        # Get filing info from database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT f.url, m.name, f.filing_id
            FROM Filings f
            JOIN Members m ON f.member_id = m.member_id
            WHERE f.doc_id = ?
        ''', (doc_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return jsonify({'error': 'Document not found'}), 404
            
        url, member_name, filing_id = result
        
        # Add verification task to queue
        verification_queue.put((doc_id, url, member_name, filing_id))
        
        return jsonify({
            'message': 'Verification started',
            'doc_id': doc_id
        })
        
    except Exception as e:
        logging.error(f"Error starting verification for document {doc_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """Delete a document and all its associated transactions from the database."""
    global deletion_count
    
    try:
        # Log if document was previously deleted instead of using pdb
        if doc_id in deleted_doc_ids:
            logging.warning(f"Attempting to delete previously deleted document: {doc_id}")
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First get the filing_id
        cursor.execute('SELECT filing_id FROM Filings WHERE doc_id = ?', (doc_id,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return jsonify({'error': 'Document not found'}), 404
            
        filing_id = result[0]
        
        # Delete in correct order to respect foreign key constraints
        # 1. Delete API_Requests first (references filing_id)
        cursor.execute('DELETE FROM API_Requests WHERE filing_id = ?', (filing_id,))
        api_requests_deleted = cursor.rowcount
        
        # 2. Delete all transactions for this filing
        cursor.execute('DELETE FROM Transactions WHERE filing_id = ?', (filing_id,))
        transactions_deleted = cursor.rowcount
        
        # 3. Delete the filing last
        cursor.execute('DELETE FROM Filings WHERE doc_id = ?', (doc_id,))
        
        logging.info(f"Deleted document {doc_id}: {api_requests_deleted} API requests, {transactions_deleted} transactions")
        
        conn.commit()
        conn.close()
        
        # Increment deletion count
        deletion_count += 1
        
        # Add this doc_id to our tracking set
        deleted_doc_ids.add(doc_id)
        logging.info(f"Document {doc_id} deleted and added to breakpoint tracking")
        
        # Save updated list of doc_ids
        save_deleted_doc_ids()
        
        return jsonify({'message': 'Document deleted successfully'})
        
    except Exception as e:
        logging.error(f"Error deleting document {doc_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/tracked-docs')
def get_tracked_docs():
    """Return the list of tracked document IDs for breakpoints."""
    return jsonify({
        'tracked_docs': list(deleted_doc_ids)
    })

@app.route('/api/stats')
def get_stats():
    """Return the current verification stats."""
    # Calculate error rate if there are verifications
    error_rate = 0
    if verification_count > 0:
        error_rate = (deletion_count / (verification_count + deletion_count)) * 100
        
    return jsonify({
        'verification_count': verification_count,
        'deletion_count': deletion_count,
        'error_rate': round(error_rate, 2)  # Round to 2 decimal places
    })

@app.route('/api/verified-docs')
def get_verified_documents():
    """Get all verified documents from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all verified filings with their member names and URLs
    cursor.execute('''
        SELECT f.filing_id, f.doc_id, f.url, f.filing_date, m.name as member_name
        FROM Filings f
        JOIN Members m ON f.member_id = m.member_id
        WHERE f.verified = 1
        ORDER BY f.filing_date DESC
    ''')
    
    filings = []
    for row in cursor.fetchall():
        filing_id, doc_id, url, filing_date, member_name = row
        
        # Get transactions for this filing
        cursor.execute('''
            SELECT t.transaction_id, t.owner_code, t.transaction_type, 
                   t.transaction_date, t.amount_range_low, t.amount_range_high,
                   t.raw_llm_csv_line,
                   a.company_name, a.ticker
            FROM Transactions t
            JOIN Assets a ON t.asset_id = a.asset_id
            WHERE t.filing_id = ?
            ORDER BY a.company_name ASC
        ''', (filing_id,))
        
        transactions = []
        for tx in cursor.fetchall():
            transactions.append({
                'transaction_id': tx[0],
                'owner_code': tx[1],
                'transaction_type': tx[2],
                'transaction_date': tx[3],
                'amount_range_low': tx[4],
                'amount_range_high': tx[5],
                'raw_llm_line': tx[6],
                'company_name': tx[7],
                'ticker': tx[8]
            })
        
        filings.append({
            'filing_id': filing_id,
            'doc_id': doc_id,
            'url': url,
            'filing_date': filing_date,
            'member_name': member_name,
            'transactions': transactions
        })
    
    conn.close()
    return jsonify(filings)

@app.route('/api/longest-transactions')
def get_longest_transactions():
    """Analyze the longest transactions and check if they were cut off by token limits."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # First, load the length limit failures from the JSON file
    length_limit_failures = set()
    try:
        filepath = os.path.join(os.path.dirname(__file__), 'senate_length_limit_failures.json')
        with open(filepath, 'r') as f:
            length_limit_failures = set(json.load(f))
    except FileNotFoundError:
        logging.warning("senate_length_limit_failures.json not found")
    except json.JSONDecodeError:
        logging.warning("Error decoding senate_length_limit_failures.json")
    
    # Get filings with their transaction counts
    cursor.execute('''
        SELECT 
            f.filing_id,
            f.doc_id,
            f.filing_date,
            m.name as member_name,
            COUNT(t.transaction_id) as transaction_count,
            GROUP_CONCAT(t.raw_llm_csv_line) as all_transactions
        FROM Filings f
        JOIN Members m ON f.member_id = m.member_id
        LEFT JOIN Transactions t ON f.filing_id = t.filing_id
        GROUP BY f.filing_id
        ORDER BY transaction_count DESC
        LIMIT 20
    ''')
    
    results = []
    for row in cursor.fetchall():
        filing_id, doc_id, filing_date, member_name, transaction_count, all_transactions = row
        
        # Calculate approximate character count from raw transactions
        char_count = len(all_transactions) if all_transactions else 0
        approx_tokens = char_count // 4  # Rough estimate of tokens
        
        # Check if this doc_id hit the token limit
        hit_token_limit = doc_id in length_limit_failures
        
        results.append({
            'filing_id': filing_id,
            'doc_id': doc_id,
            'filing_date': filing_date,
            'member_name': member_name,
            'transaction_count': transaction_count,
            'char_count': char_count,
            'approx_tokens': approx_tokens,
            'hit_token_limit': hit_token_limit
        })
    
    conn.close()
    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True, port=5001, threaded=False)  # Use different port for Senate 