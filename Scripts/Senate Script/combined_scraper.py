from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import Select
import senate_db_processor as db
from datetime import datetime
import logging
import scanToTextLLM as llm
import os
import json
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from io import BytesIO
import pickle
import sys

# Add parent directory to path to allow importing from 'common'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common import ocr_utils

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s')

# Global variables for thread coordination
link_queue = queue.Queue()
result_queue = queue.Queue()
processing_complete = threading.Event()
COOKIES_FILE = 'verified_session.pkl'
LINKS_FILE = 'senate_scraped_links.json'

def get_thread_count() -> int:
    """
    Get the number of threads to use from user input.
    Returns a validated thread count between 1 and 20.
    """
    default_threads = 5  # Conservative default for Senate with auth
    while True:
        try:
            user_input = input(f"Enter number of threads to use (1-20) [default={default_threads}]: ").strip()
            
            if not user_input:
                return default_threads
            
            thread_count = int(user_input)
            
            if 1 <= thread_count <= 20:
                return thread_count
            else:
                print(f"Please enter a number between 1 and 20.")
        except ValueError:
            print("Please enter a valid number.")

def get_processing_limit() -> int:
    """
    Get the maximum number of documents to process from user input.
    Returns a validated limit or 0 for no limit.
    """
    while True:
        try:
            user_input = input("Enter max documents to process (0 for no limit) [default=0]: ").strip()
            
            if not user_input:
                return 0
            
            limit = int(user_input)
            
            if limit >= 0:
                return limit
            else:
                print("Please enter a number >= 0.")
        except ValueError:
            print("Please enter a valid number.")

def save_scraped_links(links_data):
    """Save scraped links to a JSON file with metadata."""
    try:
        filepath = os.path.join(os.path.dirname(__file__), LINKS_FILE)
        save_data = {
            'scrape_timestamp': datetime.now().isoformat(),
            'total_links': len(links_data),
            'links': links_data
        }
        with open(filepath, 'w') as f:
            json.dump(save_data, f, indent=2)
        logging.info(f"Saved {len(links_data)} scraped links to {filepath}")
    except Exception as e:
        logging.error(f"Error saving scraped links: {e}")

def load_scraped_links():
    """Load scraped links from JSON file."""
    try:
        filepath = os.path.join(os.path.dirname(__file__), LINKS_FILE)
        with open(filepath, 'r') as f:
            data = json.load(f)
        links = data.get('links', [])
        scrape_time = data.get('scrape_timestamp', 'unknown')
        logging.info(f"Loaded {len(links)} scraped links from {scrape_time}")
        return links
    except FileNotFoundError:
        logging.info("No existing scraped links file found")
        return []
    except Exception as e:
        logging.error(f"Error loading scraped links: {e}")
        return []

def parse_filing_date(date_str):
    """Parse filing date string to datetime for sorting."""
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

def determine_document_type(url):
    """Determine if document is table-based or PDF-based from URL."""
    if '/view/ptr/' in url:
        return 'table'
    elif '/view/paper/' in url:
        return 'pdf'
    else:
        return 'unknown'

def save_cookies(driver):
    """Save the verified session cookies."""
    try:
        cookies = driver.get_cookies()
        with open(COOKIES_FILE, 'wb') as f:
            pickle.dump(cookies, f)
        logging.info("Saved verified session cookies")
    except Exception as e:
        logging.error(f"Error saving cookies: {e}")

def load_cookies(driver):
    """Load the verified session cookies."""
    try:
        with open(COOKIES_FILE, 'rb') as f:
            cookies = pickle.load(f)
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except:
                pass  # Some cookies might not be valid for current domain
        logging.info("Loaded verified session cookies")
        return True
    except FileNotFoundError:
        logging.info("No saved cookies found")
        return False
    except Exception as e:
        logging.error(f"Error loading cookies: {e}")
        return False

def verify_session(driver, url):
    """Verify the session by agreeing to terms and setting up search."""
    try:
        driver.get(url)
        
        # Check if we need to agree to terms
        try:
            agreement_form = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "agreement_form"))
            )
            agree_checkbox = agreement_form.find_element(By.ID, "agree_statement")
            agree_checkbox.click()
            logging.info("Agreement checkbox clicked.")
        except TimeoutException:
            logging.info("No agreement form found, proceeding...")
        
        # Click PTR button
        try:
            toggle_ptr = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "reportTypeLabelPtr"))
            )
            toggle_ptr.click()
            logging.info("PTR button clicked.")
        except TimeoutException:
            logging.warning("PTR button not found")
        
        # Click search button
        try:
            search_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.btn-primary"))
            )
            search_button.click()
            logging.info("Search button clicked.")
        except TimeoutException:
            logging.warning("Search button not found")
        
        # Sort by date (descending)
        try:
            date_header = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//th[contains(text(), 'Date Received/Filed')]"))
            )
            date_header.click()
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//th[@aria-sort='ascending']"))
            )
            date_header.click()  # Click again for descending
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//th[@aria-sort='descending']"))
            )
            logging.info("Sorted by date descending")
        except TimeoutException:
            logging.warning("Could not sort by date")
        
        # Set max entries per page
        try:
            dropdown = driver.find_element(By.XPATH, "/html/body/div[1]/main/div/div/div[6]/div/div/div/div[3]/div[1]/div/label/select")
            select = Select(dropdown)
            select.select_by_index(3)  # Select maximum entries
            logging.info("Set maximum entries per page")
        except:
            logging.warning("Could not set max entries")
        
        # Save cookies after successful verification
        save_cookies(driver)
        return True
        
    except Exception as e:
        logging.error(f"Error during verification: {e}")
        return False

def extract_text_from_images(driver, doc_id):
    """Extract text from image-based documents with pagination support."""
    all_text = ""
    page_count = 0
    image_urls = []

    try:
        while True:
            page_count += 1
            logging.info(f"[{doc_id}] Looking for image on page {page_count}")
            
            # Look for filing image
            try:
                img_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "filingImage"))
                )
                img_url = img_element.get_attribute('src')
                image_urls.append(img_url)
                logging.info(f"[{doc_id}] Found image on page {page_count}: {img_url}")
                
            except TimeoutException:
                logging.info(f"[{doc_id}] No more images found after page {page_count - 1}")
                break

            # Look for next page button
            try:
                pagination_nav = driver.find_element(By.XPATH, "//nav[@aria-label='Page Navigation']")
                current_page_element = pagination_nav.find_element(By.XPATH, ".//li[@class='page-item active']/a[@class='page-link']")
                current_page_href = current_page_element.get_attribute('href')
                current_page_num = int(current_page_href.split('#')[-1]) if '#' in current_page_href else 1
                
                next_page_num = current_page_num + 1
                next_page_link = pagination_nav.find_element(By.XPATH, f".//a[@class='page-link' and contains(@href, '#{next_page_num}')]")
                
                driver.execute_script("arguments[0].click();", next_page_link)
                time.sleep(3)  # Wait for page to load
                logging.info(f"[{doc_id}] Moved to page {next_page_num}")
                
            except NoSuchElementException:
                logging.info(f"[{doc_id}] No more pagination found. End of document.")
                break
            except Exception as e:
                logging.error(f"[{doc_id}] Error navigating pagination: {e}")
                break
    
    except Exception as e:
        logging.error(f"[{doc_id}] Error during image URL gathering: {e}")
    
    if image_urls:
        logging.info(f"[{doc_id}] Found {len(image_urls)} images to process with OCR.")
        all_text = ocr_utils.extract_text_from_image_list(image_urls, doc_id)

    logging.info(f"[{doc_id}] Completed image text extraction from {len(image_urls)} pages, total chars: {len(all_text)}")
    return all_text

def extract_text_from_page(driver, doc_id):
    """Extract text content from the current page."""
    try:
        # Check if it's an image-based document
        try:
            img_element = driver.find_element(By.CLASS_NAME, "filingImage")
            logging.info(f"[{doc_id}] Detected image-based document")
            return extract_text_from_images(driver, doc_id)
        except NoSuchElementException:
            pass
        
        # Try to extract from table or general page content
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Look for table content first
        table = soup.find('table', class_='table')
        if table:
            logging.info(f"[{doc_id}] Found table-based content")
            # Extract table data as text
            text_content = ""
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                row_text = ' | '.join(cell.get_text(strip=True) for cell in cells)
                text_content += row_text + '\n'
            return text_content
        
        # Fallback: extract all visible text
        logging.info(f"[{doc_id}] Extracting general page text")
        text_content = soup.get_text(separator=' ', strip=True)
        return text_content
        
    except Exception as e:
        logging.error(f"[{doc_id}] Error extracting text from page: {e}")
        return ""

def parse_amount_range(amount_str):
    """Parse amount range string into low and high values."""
    try:
        clean_str = amount_str.replace('$', '').replace(',', '')
        if '-' in clean_str:
            low_str, high_str = clean_str.split('-')
            return int(low_str.strip()), int(high_str.strip())
        else:
            value = int(clean_str.strip())
            return value, value
    except (ValueError, AttributeError):
        logging.warning(f"Could not parse amount range: {amount_str}")
        return None, None

def process_document_worker(db_path=None):
    """Worker function that processes documents from the queue."""
    thread_name = threading.current_thread().name
    documents_processed = 0
    
    # Create a driver for this thread
    driver = webdriver.Chrome()
    
    try:
        # Verify session for this thread
        url = 'https://efdsearch.senate.gov/search/'
        
        # Try to load cookies first
        driver.get(url)
        if load_cookies(driver):
            logging.info(f"{thread_name}: Cookies loaded, verifying session")
            # Verify the session is still valid
            try:
                verify_session(driver, url)
            except:
                logging.warning(f"{thread_name}: Session verification failed, continuing anyway")
        else:
            logging.info(f"{thread_name}: No cookies found, performing full verification")
            if not verify_session(driver, url):
                logging.error(f"{thread_name}: Failed to verify session")
                return
        
        logging.info(f"{thread_name}: Session verified, starting document processing")
        
        while True:
            try:
                # Get document from queue
                doc_data = link_queue.get(timeout=5)
                if doc_data is None:  # Shutdown signal
                    logging.info(f"{thread_name}: Received shutdown signal")
                    break
                
                doc_id, doc_url, member_name = doc_data
                documents_processed += 1
                
                logging.info(f"{thread_name}: Processing document {documents_processed}: {doc_id} - {member_name}")
                
                # Navigate to the document
                driver.get(doc_url)
                time.sleep(2)  # Wait for page to load
                
                # Extract text from the document
                extracted_text = extract_text_from_page(driver, doc_id)
                
                if extracted_text.strip():
                    logging.info(f"{thread_name}: Extracted {len(extracted_text)} characters from {doc_id}")
                    
                    # Process with LLM
                    member_data = {
                        'DocID': doc_id,
                        'Name': member_name,
                        'URL': doc_url
                    }
                    
                    # Send to LLM for processing
                    try:
                        # For table-based documents and OCR'd PDFs, call LLM API directly with text
                        document_type = determine_document_type(doc_url)
                        
                        if document_type == 'table' or document_type == 'pdf':
                            # Call LLM API directly with extracted table text or OCR'd text
                            llm_response = llm.call_llm_api_with_text(extracted_text, member_data)
                        else:
                            # This case should ideally not be hit with current logic, but as a fallback:
                            logging.warning(f"{thread_name}: Unknown document type '{document_type}' for {doc_id}, processing as text.")
                            text_bytes = extracted_text.encode('utf-8')
                            text_buffer = BytesIO(text_bytes)
                            llm_response = llm.scan_with_openrouter(text_buffer, member_data)
                        
                        transactions = llm.parse_llm_transactions(llm_response, member_data)
                        
                        if transactions:
                            num_inserted = db.process_and_store_scraped_data(
                                member_name=member_name,
                                doc_id=doc_id,
                                url=doc_url,
                                llm_transactions=transactions,
                                db_path=db_path
                            )
                            logging.info(f"{thread_name}: Successfully processed {doc_id} - {num_inserted} transactions inserted")
                            
                            # Add to results
                            result_queue.put({
                                'doc_id': doc_id,
                                'member_name': member_name,
                                'status': 'success',
                                'transactions': len(transactions),
                                'inserted': num_inserted
                            })
                        else:
                            logging.warning(f"{thread_name}: No transactions found in {doc_id}")
                            result_queue.put({
                                'doc_id': doc_id,
                                'member_name': member_name,
                                'status': 'empty',
                                'transactions': 0,
                                'inserted': 0
                            })
                    
                    except Exception as e:
                        logging.error(f"{thread_name}: Error processing {doc_id} with LLM: {e}")
                        result_queue.put({
                            'doc_id': doc_id,
                            'member_name': member_name,
                            'status': 'error',
                            'error': str(e)
                        })
                else:
                    logging.warning(f"{thread_name}: No text extracted from {doc_id}")
                    result_queue.put({
                        'doc_id': doc_id,
                        'member_name': member_name,
                        'status': 'no_text',
                        'transactions': 0,
                        'inserted': 0
                    })
                
                link_queue.task_done()
                
            except queue.Empty:
                # Check if processing is complete
                if processing_complete.is_set():
                    logging.info(f"{thread_name}: Processing complete signal received")
                    break
                continue
                
            except Exception as e:
                logging.error(f"{thread_name}: Error processing document: {e}")
                link_queue.task_done()
    
    except Exception as e:
        logging.error(f"{thread_name}: Fatal error in worker thread: {e}")
    
    finally:
        driver.quit()
        logging.info(f"{thread_name}: Finished processing {documents_processed} documents")

def scrape_all_ptr_links(force_rescrape=False, db_path=None):
    """
    Scrape all PTR links from the Senate filing website.
    This function handles pagination and session verification.
    """
    logging.info("Starting to scrape all PTR links...")
    
    # Check if links file exists and is recent
    if not force_rescrape and os.path.exists(LINKS_FILE):
        file_mod_time = datetime.fromtimestamp(os.path.getmtime(LINKS_FILE))
        if (datetime.now() - file_mod_time).days < 1:
            logging.info("Scraped links file is recent, loading from cache")
            with open(LINKS_FILE, 'r') as f:
                all_links = json.load(f)
            
            # Filter out already processed links
            existing_doc_ids = db.get_existing_doc_ids(db_path)
            new_links = [link for link in all_links if link['doc_id'] not in existing_doc_ids]
            
            logging.info(f"Found {len(all_links)} total links in cache, {len(new_links)} are new")
            return new_links
            
    # Scrape fresh links from the website
    driver = webdriver.Chrome()
    all_links = []
    
    try:
        url = 'https://efdsearch.senate.gov/search/'
        
        # Verify session
        if not verify_session(driver, url):
            logging.error("Failed to verify session for link scraping")
            return []
        
        page_count = 0
        next_disabled = False
        
        while not next_disabled:
            page_count += 1
            logging.info(f"Scraping page {page_count}...")
            
            # Wait for table to be present
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "table"))
                )
            except TimeoutException:
                logging.error(f"Timeout waiting for table on page {page_count}")
                break
            
            # Parse the current page
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            table = soup.find('table')
            if not table:
                logging.error(f"No table found on page {page_count}")
                break
            
            rows = table.find('tbody').find_all('tr')
            
            for i, row in enumerate(rows):
                try:
                    cols = row.find_all('td')
                    if len(cols) >= 4:
                        # Debug: Log the actual column contents for first few rows to understand table structure
                        if i < 3:  # Only log first 3 rows to avoid spam
                            col_texts = [col.text.strip() for col in cols[:6]]  # First 6 columns
                            logging.info(f"Row {i+1} columns: [FirstName: '{col_texts[0] if len(col_texts) > 0 else ''}', LastName: '{col_texts[1] if len(col_texts) > 1 else ''}', Office: '{col_texts[2] if len(col_texts) > 2 else ''}', ReportType: '{col_texts[3] if len(col_texts) > 3 else ''}', Date: '{col_texts[4] if len(col_texts) > 4 else ''}']")
                        
                        link_element = cols[3].find('a')
                        if link_element:
                            relative_url = link_element['href']
                            doc_id = relative_url.rstrip('/').split('/')[-1]
                            full_url = f"https://efdsearch.senate.gov{relative_url}"
                            
                            # Correct Senate table structure:
                            # Col 0: First Name, Col 1: Last Name, Col 2: Office/Filer Type, Col 3: Report Type (with link), Col 4: Date Received/Filed
                            first_name = cols[0].text.strip() if len(cols) > 0 else ""
                            last_name = cols[1].text.strip() if len(cols) > 1 else ""
                            member_name = f"{first_name} {last_name}".strip()
                            
                            # Fallback if name is empty - use office/filer type
                            if not member_name and len(cols) > 2:
                                member_name = cols[2].text.strip()
                            
                            filing_date = cols[4].text.strip() if len(cols) > 4 else ""  # Date is in column 4
                            document_type = determine_document_type(full_url)
                            
                            # Create detailed link record
                            link_record = {
                                'doc_id': doc_id,
                                'url': full_url,
                                'member_name': member_name,
                                'filing_date': filing_date,
                                'filing_date_parsed': parse_filing_date(filing_date).isoformat() if filing_date else "",
                                'document_type': document_type,
                                'page_scraped': page_count
                            }
                            all_links.append(link_record)
                            logging.debug(f"Added link: {doc_id} - {member_name} ({document_type})")
                
                except Exception as e:
                    logging.error(f"Error parsing row {i} on page {page_count}: {e}")
                    continue
            
            logging.info(f"Page {page_count}: Found {len(rows)} rows, total links: {len(all_links)}")
            
            # Try to go to next page
            try:
                next_button = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[@id='filedReports_next']"))
                )
                
                if 'disabled' in next_button.get_attribute('class'):
                    logging.info("Next button is disabled, reached last page")
                    next_disabled = True
                else:
                    # Get current info text to detect page change
                    current_info = driver.find_element(By.ID, "filedReports_info").text
                    next_button.click()
                    
                    # Wait for page to change
                    WebDriverWait(driver, 10).until(
                        lambda d: d.find_element(By.ID, "filedReports_info").text != current_info
                    )
                    time.sleep(1)  # Additional wait
                    logging.info("Moved to next page")
            
            except TimeoutException:
                logging.info("Next button not found or timeout, assuming last page")
                next_disabled = True
            except Exception as e:
                logging.error(f"Error navigating to next page: {e}")
                next_disabled = True
    
    except Exception as e:
        logging.error(f"Error during link scraping: {e}")
    
    finally:
        driver.quit()
    
    # Sort links by filing date (newest first)
    all_links.sort(key=lambda x: parse_filing_date(x['filing_date']), reverse=True)
    
    # Save all scraped links
    save_scraped_links(all_links)
    
    # After scraping, filter out already processed links before returning
    existing_doc_ids = db.get_existing_doc_ids(db_path)
    new_links = [link for link in all_links if link['doc_id'] not in existing_doc_ids]
    
    logging.info(f"Scraped {len(all_links)} total links, {len(new_links)} are new")
    
    # Save all links to file for caching
    with open(LINKS_FILE, 'w') as f:
        json.dump(all_links, f, indent=2)
        
    return new_links

def filter_new_documents(all_links):
    """Filter out documents that are already in the database."""
    if not all_links:
        return []
    
    existing_doc_ids = db.get_existing_doc_ids()
    new_links = []
    processed_count = 0
    
    # Check ALL links against the database, don't stop at first processed document
    for link in all_links:
        doc_id = link['doc_id']
        if doc_id not in existing_doc_ids:
            new_links.append(link)
        else:
            processed_count += 1
            logging.debug(f"Document {doc_id} already processed, skipping")
    
    logging.info(f"Filtered {len(all_links)} total links: {len(new_links)} new, {processed_count} already processed")
    
    # Convert link records back to simple tuples for compatibility
    return [(link['doc_id'], link['url'], link['member_name']) for link in new_links]

def result_consumer():
    """Consumer thread to process results from worker threads."""
    total_processed = 0
    total_success = 0
    total_errors = 0
    
    logging.info("Result consumer started")
    
    while True:
        try:
            result = result_queue.get(timeout=5)
            if result is None:  # Shutdown signal
                break
            
            total_processed += 1
            status = result.get('status', 'unknown')
            doc_id = result.get('doc_id', 'unknown')
            
            if status == 'success':
                total_success += 1
                logging.info(f"✓ Success {total_processed}: {doc_id} - {result.get('inserted', 0)} transactions")
            elif status == 'error':
                total_errors += 1
                logging.error(f"✗ Error {total_processed}: {doc_id} - {result.get('error', 'Unknown error')}")
            else:
                logging.info(f"○ {status.title()} {total_processed}: {doc_id}")
            
            result_queue.task_done()
            
        except queue.Empty:
            if processing_complete.is_set():
                break
            continue
        except Exception as e:
            logging.error(f"Error in result consumer: {e}")
    
    logging.info(f"Result consumer finished. Processed: {total_processed}, Success: {total_success}, Errors: {total_errors}")

def get_force_rescrape_option():
    """Ask user if they want to force rescrape all links."""
    while True:
        try:
            user_input = input("Force rescrape all links? (y/n) [default=n]: ").strip().lower()
            
            if not user_input or user_input == 'n':
                return False
            elif user_input == 'y':
                return True
            else:
                print("Please enter 'y' or 'n'.")
        except ValueError:
            print("Please enter 'y' or 'n'.")

def main(db_path=None):
    """Main function coordinating the entire process."""
    start_time = time.time()
    
    print("=" * 60)
    print("SENATE CONGRESS TRADING DOCUMENT PROCESSOR")
    print("=" * 60)
    
    logging.info("Starting Senate multithreaded document processing")
    
    # Initialize database
    try:
        db.create_tables(db_path)
        logging.info("Database tables ensured/created successfully")
    except Exception as e:
        logging.error(f"Fatal error during database table creation: {e}")
        return
    
    # Get user inputs
    num_threads = get_thread_count()
    processing_limit = get_processing_limit()
    force_rescrape = get_force_rescrape_option()
    
    if processing_limit > 0:
        logging.info(f"Processing limit set to {processing_limit} documents")
    else:
        logging.info("No processing limit set - will process all available documents")
    
    logging.info(f"Using {num_threads} worker threads for document processing")
    
    if force_rescrape:
        logging.info("Force rescrape option enabled - will scrape all links fresh")
    else:
        logging.info("Using optimized scraping - will check existing links first")
    
    # Step 1: Scrape all PTR links (with optimization)
    all_links = scrape_all_ptr_links(force_rescrape=force_rescrape, db_path=db_path)
    
    if not all_links:
        logging.info("No new documents found to process. Exiting.")
        end_time = time.time()
        logging.info(f"Execution completed in {end_time - start_time:.2f} seconds")
        return
    
    # Apply processing limit if set
    if processing_limit > 0 and len(all_links) > processing_limit:
        all_links = all_links[:processing_limit]
        logging.info(f"Limited to first {processing_limit} documents for processing")
    
    logging.info(f"Found {len(all_links)} documents to process")
    
    # Show document type breakdown
    doc_types = {}
    for doc_id, url, member_name in all_links:
        doc_type = determine_document_type(url)
        doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
    
    for doc_type, count in doc_types.items():
        logging.info(f"  {doc_type.title()} documents: {count}")
    
    # Step 2: Add all links to the queue
    for link_data in all_links:
        link_queue.put(link_data)
    
    # Step 3: Start result consumer thread
    consumer_thread = threading.Thread(target=result_consumer, daemon=True)
    consumer_thread.start()
    
    # Step 4: Start worker threads
    worker_threads = []
    for i in range(num_threads):
        thread = threading.Thread(target=process_document_worker, name=f"Worker-{i+1}")
        thread.start()
        worker_threads.append(thread)
    
    logging.info(f"Started {num_threads} worker threads")
    
    try:
        # Wait for all links to be processed
        logging.info("Waiting for all documents to be processed...")
        link_queue.join()
        
        # Signal completion
        processing_complete.set()
        
        # Send shutdown signals to worker threads
        for _ in range(num_threads):
            link_queue.put(None)
        
        # Wait for all worker threads to finish
        for thread in worker_threads:
            thread.join(timeout=30)
        
        # Send shutdown signal to result consumer
        result_queue.put(None)
        consumer_thread.join(timeout=10)
        
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
        processing_complete.set()
    except Exception as e:
        logging.error(f"Error during processing: {e}")
    
    end_time = time.time()
    logging.info(f"All documents processed successfully in {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    main() 