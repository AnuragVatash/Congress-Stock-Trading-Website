"""
OCR utilities for processing image-based congressional trading documents.
Handles extraction of text from scanned PDFs and image forms.
"""
import logging
import os
import hashlib
from io import BytesIO
from typing import Optional, List
import requests

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logging.warning("Tesseract OCR not available. Install with: pip install pytesseract pillow")

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    logging.warning("EasyOCR not available. Install with: pip install easyocr")

class OCRProcessor:
    """
    OCR processor that can use multiple OCR engines for text extraction.
    """
    
    def __init__(self, cache_dir: str = "Scripts/common/ocr_cache"):
        """
        Initialize OCR processor.
        
        Args:
            cache_dir: Directory to cache OCR results
        """
        self.cache_dir = cache_dir
        self.easyocr_reader = None
        
        # Create cache directory
        os.makedirs(cache_dir, exist_ok=True)
        
        # Initialize EasyOCR if available
        if EASYOCR_AVAILABLE:
            try:
                self.easyocr_reader = easyocr.Reader(['en'])
                logging.info("EasyOCR initialized successfully")
            except Exception as e:
                logging.warning(f"Failed to initialize EasyOCR: {e}")
                self.easyocr_reader = None
    
    def _get_cache_key(self, image_url: str, doc_id: str, page_num: int = 1) -> str:
        """Generate cache key for OCR results."""
        content = f"{image_url}_{doc_id}_{page_num}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> str:
        """Get full path for cache file."""
        return os.path.join(self.cache_dir, f"{cache_key}.txt")
    
    def _load_from_cache(self, cache_key: str) -> Optional[str]:
        """Load OCR result from cache."""
        cache_path = self._get_cache_path(cache_key)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logging.warning(f"Failed to load from cache: {e}")
        return None
    
    def _save_to_cache(self, cache_key: str, text: str):
        """Save OCR result to cache."""
        cache_path = self._get_cache_path(cache_key)
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                f.write(text)
        except Exception as e:
            logging.warning(f"Failed to save to cache: {e}")
    
    def extract_text_from_image_url(self, image_url: str, doc_id: str, page_num: int = 1) -> str:
        """
        Extract text from an image URL using OCR.
        
        Args:
            image_url: URL of the image to process
            doc_id: Document ID for logging and caching
            page_num: Page number for caching
            
        Returns:
            Extracted text content
        """
        # Check cache first
        cache_key = self._get_cache_key(image_url, doc_id, page_num)
        cached_text = self._load_from_cache(cache_key)
        if cached_text is not None:
            logging.info(f"[{doc_id}] Loaded OCR result from cache for page {page_num}")
            return cached_text
        
        try:
            # Download image
            logging.info(f"[{doc_id}] Downloading image for OCR: {image_url}")
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Process with OCR
            extracted_text = self._process_image_bytes(response.content, doc_id, page_num)
            
            # Cache the result
            self._save_to_cache(cache_key, extracted_text)
            
            return extracted_text
            
        except Exception as e:
            logging.error(f"[{doc_id}] Error extracting text from image {image_url}: {e}")
            return f"[OCR ERROR] Failed to process image: {str(e)}"
    
    def _process_image_bytes(self, image_bytes: bytes, doc_id: str, page_num: int) -> str:
        """
        Process image bytes using available OCR engines.
        
        Args:
            image_bytes: Raw image data
            doc_id: Document ID for logging
            page_num: Page number for logging
            
        Returns:
            Extracted text content
        """
        # Try EasyOCR first (generally more accurate)
        if self.easyocr_reader is not None:
            try:
                logging.info(f"[{doc_id}] Processing page {page_num} with EasyOCR")
                results = self.easyocr_reader.readtext(image_bytes)
                
                # Extract text from results
                text_lines = []
                for (bbox, text, confidence) in results:
                    if confidence > 0.3:  # Filter low-confidence results
                        text_lines.append(text.strip())
                
                extracted_text = '\n'.join(text_lines)
                
                if extracted_text.strip():
                    logging.info(f"[{doc_id}] EasyOCR extracted {len(extracted_text)} characters from page {page_num}")
                    return extracted_text
                    
            except Exception as e:
                logging.warning(f"[{doc_id}] EasyOCR failed for page {page_num}: {e}")
        
        # Fallback to Tesseract
        if TESSERACT_AVAILABLE:
            try:
                logging.info(f"[{doc_id}] Processing page {page_num} with Tesseract OCR")
                image = Image.open(BytesIO(image_bytes))
                
                # Apply image preprocessing for better OCR
                image = image.convert('L')  # Convert to grayscale
                
                extracted_text = pytesseract.image_to_string(image, config='--psm 6')
                
                if extracted_text.strip():
                    logging.info(f"[{doc_id}] Tesseract extracted {len(extracted_text)} characters from page {page_num}")
                    return extracted_text
                    
            except Exception as e:
                logging.warning(f"[{doc_id}] Tesseract OCR failed for page {page_num}: {e}")
        
        # If all OCR methods fail, return placeholder
        logging.warning(f"[{doc_id}] All OCR methods failed for page {page_num}")
        return f"[OCR FAILED] Unable to extract text from page {page_num}"
    
    def extract_text_from_image_list(self, image_urls: List[str], doc_id: str) -> str:
        """
        Extract text from multiple images and combine.
        
        Args:
            image_urls: List of image URLs to process
            doc_id: Document ID for logging
            
        Returns:
            Combined extracted text from all images
        """
        all_text = []
        
        for i, image_url in enumerate(image_urls, 1):
            logging.info(f"[{doc_id}] Processing image {i}/{len(image_urls)}")
            page_text = self.extract_text_from_image_url(image_url, doc_id, i)
            all_text.append(f"[PAGE {i}]\n{page_text}\n")
        
        combined_text = '\n'.join(all_text)
        logging.info(f"[{doc_id}] Combined OCR text from {len(image_urls)} images: {len(combined_text)} characters")
        
        return combined_text
    
    def clear_cache(self, doc_id: Optional[str] = None):
        """
        Clear OCR cache files.
        
        Args:
            doc_id: If specified, only clear cache for this document
        """
        if doc_id:
            # Clear cache for specific document (approximate matching)
            cache_files = os.listdir(self.cache_dir)
            for filename in cache_files:
                if doc_id in filename:
                    try:
                        os.remove(os.path.join(self.cache_dir, filename))
                        logging.info(f"Cleared cache file: {filename}")
                    except Exception as e:
                        logging.warning(f"Failed to clear cache file {filename}: {e}")
        else:
            # Clear all cache
            cache_files = os.listdir(self.cache_dir)
            for filename in cache_files:
                try:
                    os.remove(os.path.join(self.cache_dir, filename))
                except Exception as e:
                    logging.warning(f"Failed to clear cache file {filename}: {e}")
            logging.info(f"Cleared {len(cache_files)} cache files")

# Global OCR processor instance
_ocr_processor = None

def get_ocr_processor() -> OCRProcessor:
    """Get global OCR processor instance."""
    global _ocr_processor
    if _ocr_processor is None:
        _ocr_processor = OCRProcessor()
    return _ocr_processor

def extract_text_from_image_url(image_url: str, doc_id: str, page_num: int = 1) -> str:
    """
    Convenience function to extract text from an image URL.
    
    Args:
        image_url: URL of the image to process
        doc_id: Document ID for logging and caching
        page_num: Page number for caching
        
    Returns:
        Extracted text content
    """
    processor = get_ocr_processor()
    return processor.extract_text_from_image_url(image_url, doc_id, page_num)

def check_ocr_availability() -> dict:
    """
    Check which OCR engines are available.
    
    Returns:
        Dictionary with availability status
    """
    return {
        'tesseract': TESSERACT_AVAILABLE,
        'easyocr': EASYOCR_AVAILABLE,
        'any_available': TESSERACT_AVAILABLE or EASYOCR_AVAILABLE
    } 