# main_script.py (script.py)
import time
import logging
import requests
from io import BytesIO
import concurrent.futures
import queue
import threading

# Project-specific imports
from scrapeLinks import scrape
from scanToTextLLM import scan_with_openrouter, parse_llm_transactions
from db_processor import create_tables, get_existing_doc_ids, process_and_store_scraped_data

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s'
)

# Global result queue for communication between threads
result_queue = queue.Queue()
# Event to signal when all downloading and processing is complete
processing_complete = threading.Event()

def get_thread_count() -> int:
    """
    Get the number of threads to use from user input.
    Returns a validated thread count between 1 and 50.
    """
    default_threads = 50  # Based on rate limit of 50 requests per 10 seconds
    while True:
        try:
            user_input = input(f"Enter number of threads to use (1-50) [default={default_threads}]: ").strip()
            
            # If user just presses Enter, use default
            if not user_input:
                return default_threads
            
            # Convert input to integer
            thread_count = int(user_input)
            
            # Validate thread count
            if 1 <= thread_count <= 50:
                return thread_count
            else:
                print(f"Please enter a number between 1 and 50.")
        except ValueError:
            print("Please enter a valid number.")

def get_processing_limit() -> int:
    """
    Get the maximum number of documents to process from user input.
    Returns a validated limit or 0 for no limit.
    """
    while True:
        try:
            user_input = input("Enter max documents to process (0 for no limit) [default=10]: ").strip()
            
            # If user just presses Enter, use default
            if not user_input:
                return 10
            
            # Convert input to integer
            limit = int(user_input)
            
            # Validate limit
            if limit >= 0:
                return limit
            else:
                print("Please enter a number >= 0.")
        except ValueError:
            print("Please enter a valid number.")

def download_pdf_content(url: str, doc_id: str) -> BytesIO | None:
    """Downloads PDF content from a URL."""
    try:
        logging.info(f"[{doc_id}] Downloading PDF from: {url}")
        response = requests.get(url, timeout=60) # Increased timeout for potentially slow servers
        response.raise_for_status()
        return BytesIO(response.content)
    except requests.exceptions.Timeout:
        logging.error(f"[{doc_id}] Timeout while downloading PDF from {url}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"[{doc_id}] Failed to download PDF from {url}: {e}")
        return None

def process_pdf_with_llm(pdf_info_item: dict) -> dict:
    """
    Downloads and processes a PDF with LLM.
    Returns a result dictionary with processing results or error info.
    """
    member_data = pdf_info_item.get('member_data', {})
    pdf_url = pdf_info_item.get('url')
    doc_id = member_data.get('DocID')
    
    # Prepare result dictionary
    result = {
        'doc_id': doc_id,
        'pdf_url': pdf_url,
        'member_data': member_data,
        'status': 'pending',
        'transactions': [],
        'error': None
    }
    
    # Construct member_name
    first_name = member_data.get('First', '')
    last_name = member_data.get('Last', '')
    if first_name or last_name:
        member_name = f"{first_name} {last_name}".strip()
    else:
        member_name = member_data.get('Officename', '').strip()
    
    if not member_name:
        member_name = "Unknown Member"
        logging.warning(f"[{doc_id}] Member name could not be determined. Using '{member_name}'.")
    
    result['member_name'] = member_name
    
    if not all([doc_id, pdf_url]):
        result['status'] = 'error'
        result['error'] = "Missing critical data (DocID or URL)"
        logging.warning(f"Skipping entry due to missing critical data: DocID={doc_id}, URL={pdf_url}")
        return result
    
    logging.info(f"[{doc_id}] Processing in thread: {member_name}, URL: {pdf_url}")
    
    # Process with LLM
    try:
        # Get raw LLM output
        llm_raw_output = scan_with_openrouter(pdf_url, member_data)
        logging.info(f"[{doc_id}] Raw LLM output: {llm_raw_output[:200]}..." if llm_raw_output else f"[{doc_id}] No LLM output received")
        
        # Parse the raw output into transactions
        parsed_transactions = parse_llm_transactions(llm_raw_output, member_data)
        logging.info(f"[{doc_id}] Parsed {len(parsed_transactions)} transactions from LLM output")
        
        # Debug: Log first few transactions if any
        if parsed_transactions:
            for i, tx in enumerate(parsed_transactions[:3]):  # Log first 3 transactions
                logging.info(f"[{doc_id}] Transaction {i+1}: {tx.get('company_name', 'No company')} - {tx.get('transaction_type_full', 'No type')}")
        
        if parsed_transactions:
            result['status'] = 'success'
            result['transactions'] = parsed_transactions
            result['raw_output'] = llm_raw_output
            logging.info(f"[{doc_id}] LLM processing yielded {len(parsed_transactions)} potential transactions.")
        else:
            result['status'] = 'empty'
            result['raw_output'] = llm_raw_output
            logging.warning(f"[{doc_id}] No transactions extracted by LLM or parsing failed. Raw output: {llm_raw_output}")
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        logging.error(f"[{doc_id}] Error during LLM processing: {e}", exc_info=True)
    
    return result

def db_consumer_thread():
    """
    Consumer thread that takes processed results from the queue
    and saves them to the database sequentially.
    """
    total_inserted = 0
    docs_processed = 0
    
    while True:
        try:
            # Get result from queue with 5 second timeout to check if processing is complete
            try:
                result = result_queue.get(timeout=5)
            except queue.Empty:
                # If queue is empty and processing is complete, exit the thread
                if processing_complete.is_set():
                    break
                continue
            
            docs_processed += 1
            doc_id = result.get('doc_id', 'unknown')
            member_name = result.get('member_name', 'Unknown Member')
            pdf_url = result.get('pdf_url', '')
            status = result.get('status', 'unknown')
            
            # Only save to DB if processing was successful
            if status == 'success':
                transactions = result.get('transactions', [])
                logging.info(f"[{doc_id}] Attempting to save {len(transactions)} transactions to DB")
                if transactions:
                    try:
                        # Debug: Log sample transaction data
                        sample_tx = transactions[0] if transactions else None
                        if sample_tx:
                            logging.info(f"[{doc_id}] Sample transaction: Company='{sample_tx.get('company_name')}', Type='{sample_tx.get('transaction_type_full')}', Date='{sample_tx.get('transaction_date_str')}'")
                        
                        num_inserted = process_and_store_scraped_data(
                            member_name=member_name,
                            doc_id=doc_id,
                            url=pdf_url,
                            llm_transactions=transactions
                        )
                        total_inserted += num_inserted
                        logging.info(f"[{doc_id}] Successfully saved to DB. {num_inserted} transactions added.")
                    except Exception as e:
                        logging.error(f"[{doc_id}] Error during database storage: {e}", exc_info=True)
                else:
                    logging.warning(f"[{doc_id}] Status is 'success' but transactions list is empty!")
            else:
                # Log the status for documents that weren't processed successfully
                error_msg = result.get('error', 'Unknown error')
                raw_output = result.get('raw_output', 'No raw output')
                if status == 'empty':
                    logging.info(f"[{doc_id}] No transactions to save. Raw LLM output: {raw_output[:100]}...")
                else:
                    logging.warning(f"[{doc_id}] Not saving to DB due to status '{status}': {error_msg}")
            
            # Mark task as complete and log progress
            result_queue.task_done()
            logging.info(f"DB Consumer: Processed {docs_processed} documents. Total transactions saved: {total_inserted}")
            
        except Exception as e:
            logging.error(f"Error in database consumer thread: {e}", exc_info=True)

def main():
    start_time = time.time()
    logging.info("Starting multithreaded script execution.")

    # Initialize the database
    try:
        create_tables()
        logging.info("Database tables ensured/created successfully.")
    except Exception as e:
        logging.error(f"Fatal error during database table creation: {e}", exc_info=True)
        return

    # Get processing limit from user
    processing_limit = get_processing_limit()
    if processing_limit > 0:
        logging.info(f"Processing limit set to {processing_limit} documents")
    else:
        logging.info("No processing limit set")

    # Get PDF data from scraper
    results_from_scraper = []
    try:
        results_from_scraper = scrape()
        logging.info(f"Found {len(results_from_scraper)} new PDF records to process.")
        
        # Apply processing limit if set
        if processing_limit > 0 and len(results_from_scraper) > processing_limit:
            results_from_scraper = results_from_scraper[:processing_limit]
            logging.info(f"Limited to first {processing_limit} documents for processing")
            
    except Exception as e:
        logging.error(f"Error during scrapeLinks.scrape(): {e}", exc_info=True)

    if not results_from_scraper:
        logging.info("No new PDF records found by scrapeLinks or scrape failed. Exiting.")
        end_time = time.time()
        logging.info(f"Execution completed in {end_time - start_time:.2f} seconds.")
        return

    # Start the database consumer thread
    db_thread = threading.Thread(target=db_consumer_thread, daemon=True)
    db_thread.start()
    logging.info("Database consumer thread started.")

    # Get thread count from user
    num_workers = get_thread_count()
    logging.info(f"Starting PDF processing with {num_workers} worker threads.")

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit all PDF processing tasks to the executor
            futures = [executor.submit(process_pdf_with_llm, pdf_info) for pdf_info in results_from_scraper]
            
            # Process results as they complete
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                try:
                    result = future.result()
                    doc_id = result.get('doc_id', 'unknown')
                    status = result.get('status', 'unknown')
                    
                    # Put the result in the queue for the DB consumer
                    result_queue.put(result)
                    
                    logging.info(f"Completed PDF {i+1} of {len(futures)} (DocID: {doc_id}, Status: {status})")
                except Exception as e:
                    logging.error(f"Error getting result from future: {e}", exc_info=True)
    except Exception as e:
        logging.error(f"Error in thread pool execution: {e}", exc_info=True)
    finally:
        # Signal that all processing is complete
        processing_complete.set()
        logging.info("All PDF processing complete. Waiting for database operations to finish...")
        
        # Wait for the database thread to finish
        db_thread.join(timeout=120)  # Wait up to 2 minutes for DB operations
        if db_thread.is_alive():
            logging.warning("Database thread did not complete within timeout period.")
    
    end_time = time.time()
    logging.info(f"Execution completed in {end_time - start_time:.2f} seconds.")

if __name__ == '__main__':
    main()