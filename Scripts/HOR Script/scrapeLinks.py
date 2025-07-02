from bs4 import BeautifulSoup
import os
import logging
from scanToTextLLM import text_extraction_failures

def typeP(working_dir, existing_doc_ids=None):
    """
    Scrapes PDF links from XML files, filtering out already processed documents.
    Args:
        working_dir (str): The working directory path
        existing_doc_ids (set): Set of DocIDs that have already been processed
    Returns:
        list: List of dictionaries containing PDF information
    """
    # Define the base directory and years to process.  REVERSED order.
    base_dir = os.path.join(working_dir, 'Scripts', 'HOR Script','FD')
    years = range(2025, 2015, -1)  # Process years in descending order: 2025, 2024, ..., 2020
    
    logging.info(f"Searching for XML files in base directory: {base_dir}")

    # Create a list to store all results
    all_results = []

    # Initialize existing_doc_ids if None
    if existing_doc_ids is None:
        existing_doc_ids = set()

    # Combine existing doc IDs with text extraction failures
    excluded_doc_ids = existing_doc_ids.union(text_extraction_failures)
    logging.info(f"Excluding {len(excluded_doc_ids)} documents ({len(existing_doc_ids)} from DB, {len(text_extraction_failures)} text extraction failures)")

    # Loop through each year folder
    for year in years:
        folder_name = f"{year}FD"
        file_loc = os.path.join(base_dir, folder_name, f"{folder_name}.xml")

        # Debug logging to show which files are being checked
        logging.debug(f"Checking for XML file: {file_loc}")

        # Check if the file exists before reading
        if os.path.exists(file_loc):
            logging.info(f"Found XML file: {file_loc}")
            # Read the XML file with utf-8-sig encoding
            with open(file_loc, 'r', encoding='utf-8-sig') as f:
                data = f.read()

            # Parse XML
            Bs_data = BeautifulSoup(data, "xml")
            b_ptr = Bs_data.find_all('Member')

            # Loop through each 'Member' tag
            for member in b_ptr:
                filing_type = member.find('FilingType')

                # Only process if FilingType is 'P'
                if filing_type and filing_type.text.strip() == 'P':
                    doc_id = member.find('DocID')
                    if doc_id:
                        doc_id_value = doc_id.text.strip()
                        
                        # Skip if DocID exists in database or is a text extraction failure
                        if doc_id_value in excluded_doc_ids:
                            if doc_id_value in existing_doc_ids:
                                logging.debug(f"Skipping already processed DocID: {doc_id_value}")
                            else:
                                logging.debug(f"Skipping DocID with text extraction failure: {doc_id_value}")
                            continue
                            
                        url = f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id_value}.pdf"

                        # Extract all attributes except FilingType
                        member_data = {}
                        for tag in member.find_all(recursive=False):
                            if tag.name != 'FilingType':
                                member_data[tag.name] = tag.text.strip()
                        member_data['DocID'] = doc_id_value  # CRUCIAL: Include DocID
                        # Add the extracted data and URL to results
                        all_results.append({
                            'year': year,
                            'member_data': member_data,
                            'url': url
                        })

    # Return all collected results
    return all_results

def scrape():
    """
    Main scraping function that gets PDF links and filters out already processed documents.
    Returns:
        list: List of dictionaries containing PDF information for new documents
    """
    # Set path for XML files
    current_dir = os.path.dirname(__file__)
    working_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
    
    # Import here to avoid circular imports
    from db_processor import get_existing_doc_ids
    
    try:
        # Get existing DocIDs from database
        existing_doc_ids = get_existing_doc_ids()
        logging.info(f"Found {len(existing_doc_ids)} existing DocIDs in database")
    except Exception as e:
        logging.error(f"Error fetching existing DocIDs: {e}")
        existing_doc_ids = set()
    
    # Get all Ptr links, filtering out existing DocIDs and text extraction failures
    results = typeP(working_dir, existing_doc_ids)
    logging.info(f"Found {len(results)} new PDF records to process")
    return results