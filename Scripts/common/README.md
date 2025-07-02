# Common Utilities for Congressional Trading Document Processing

This directory contains shared utilities and improvements implemented based on lessons learned from the congressional trading document processing project.

## 🎯 Key Improvements Implemented

### 1. **Shared Date Utilities** (`date_utils.py`)

- **Problem Solved**: Senate documents had empty notification dates causing transaction failures
- **Solution**: Centralized date handling with automatic fallback to transaction dates
- **Key Functions**:
  - `default_notification_date()` - Fixes the Senate notification date issue
  - `parse_filing_date()` - Robust date parsing for sorting
  - `validate_date_format()` - Date validation with logging

### 2. **Database Schema Consistency** (`db_schema.py`)

- **Problem Solved**: Potential schema inconsistencies between HOR and Senate scripts
- **Solution**: Shared schema creation and validation functions
- **Key Functions**:
  - `create_tables()` - Ensures identical database structure
  - `verify_schema_consistency()` - Validates database schema
  - `get_or_create_member()`, `get_or_create_asset()` - Shared database operations

### 3. **Flexible Rate Limiting** (`rate_limiter.py`)

- **Problem Solved**: Duplicated rate limiting code between scripts
- **Solution**: Parameterized rate limiter supporting different APIs and use cases
- **Key Features**:
  - Pre-configured limiters: `OPENROUTER_LIMITER`, `SENATE_WEB_LIMITER`, `HOR_WEB_LIMITER`
  - Custom rate limiter creation
  - Decorator support: `@rate_limit(calls=50, period=10)`

### 4. **OCR Integration** (`ocr_utils.py`)

- **Problem Solved**: Image-based documents (`/paper/` links) couldn't be processed
- **Solution**: Multi-engine OCR with caching and fallback strategies
- **Key Features**:
  - Supports both EasyOCR and Tesseract
  - Automatic caching to `Scripts/common/ocr_cache/`
  - Confidence filtering and preprocessing
  - Batch processing for multi-page documents

### 5. **Template-Based Prompts** (`prompt_utils.py`, `prompts/financial_csv.j2`)

- **Problem Solved**: Hard-coded LLM prompts were difficult to maintain and customize
- **Solution**: Jinja2 templates with dynamic configuration
- **Key Features**:
  - Document-type specific instructions
  - Automatic notification date handling
  - Fallback support when Jinja2 is unavailable
  - Specialized system instructions for congressional documents

### 6. **Observability & Metrics** (`observability.py`)

- **Problem Solved**: No visibility into system performance and bottlenecks
- **Solution**: Comprehensive metrics collection and monitoring
- **Key Features**:
  - Performance tracking: `@timer`, `track_operation()`
  - Rate monitoring and error tracking
  - Metrics export to JSON
  - Thread-safe operation

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
cd Scripts/common
pip install -r requirements.txt

# Optional: Install OCR engines
# For Tesseract (requires system installation)
sudo apt-get install tesseract-ocr  # Ubuntu/Debian
brew install tesseract              # macOS

# EasyOCR installs automatically with pip
```

### Basic Usage Examples

#### 1. Date Utilities

```python
from Scripts.common.date_utils import default_notification_date, parse_filing_date

# Fix missing notification dates (Senate issue)
notification_date = default_notification_date(
    transaction_date_str="04/22/2025",
    notification_date_str="",  # Empty!
    doc_id="52c9fa8c-a4fa-4f74-9013-0e1076574cfa"
)
# Returns: "04/22/2025"

# Parse dates for sorting
filing_datetime = parse_filing_date("04/22/2025")
```

#### 2. Rate Limiting

```python
from Scripts.common.rate_limiter import rate_limited_api_call, OPENROUTER_LIMITER

# Use pre-configured rate limiter
response = rate_limited_api_call(
    "https://openrouter.ai/api/v1/chat/completions",
    headers=headers,
    json=payload
)

# Or use as decorator
from Scripts.common.rate_limiter import rate_limit

@rate_limit(calls=10, period=60)  # 10 calls per minute
def my_api_function():
    # Your API call here
    pass
```

#### 3. OCR Processing

```python
from Scripts.common.ocr_utils import extract_text_from_image_url

# Process a single image
text = extract_text_from_image_url(
    "https://example.com/image.jpg",
    doc_id="document_123",
    page_num=1
)

# Check OCR availability
from Scripts.common.ocr_utils import check_ocr_availability
availability = check_ocr_availability()
# Returns: {'tesseract': True, 'easyocr': True, 'any_available': True}
```

#### 4. Template-Based Prompts

```python
from Scripts.common.prompt_utils import generate_financial_prompt

system_instruction, user_prompt = generate_financial_prompt(
    document_text="[Document content here]",
    document_source="senate"  # Automatically handles Senate-specific rules
)
```

#### 5. Observability

```python
from Scripts.common.observability import timer, track_operation, get_metrics

# Use as decorator
@timer("pdf_processing")
def process_pdf(pdf_data):
    # Your processing logic
    pass

# Use as context manager
with track_operation("database_insert", {"table": "transactions"}):
    # Your database operation
    pass

# Get metrics summary
metrics = get_metrics()
summary = metrics.get_metrics_summary()
```

## 📁 Directory Structure

```
Scripts/common/
├── __init__.py              # Package initialization
├── README.md               # This file
├── requirements.txt        # Dependencies
├── date_utils.py          # Date handling and Senate fix
├── db_schema.py           # Database consistency
├── rate_limiter.py        # Flexible rate limiting
├── ocr_utils.py           # Image document processing
├── prompt_utils.py        # Template-based prompts
├── observability.py       # Metrics and monitoring
├── prompts/               # Jinja2 templates
│   └── financial_csv.j2   # LLM prompt template
└── ocr_cache/            # OCR results cache (created automatically)
```

## 🔧 Integration with Existing Scripts

### Updating HOR Script

```python
# In your HOR script
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.date_utils import default_notification_date
from common.rate_limiter import rate_limited_api_call
from common.observability import timer

# Replace existing date handling
notification_date_str = default_notification_date(
    transaction_date_str, notification_date_str, doc_id
)

# Replace existing rate limiting
@timer("llm_request")
def call_llm_api():
    return rate_limited_api_call(url, headers=headers, json=payload)
```

### Updating Senate Script

```python
# In your Senate script - the notification date fix is crucial!
from common.date_utils import default_notification_date
from common.prompt_utils import generate_financial_prompt

# This fixes the Senate double-comma issue
notification_date_str = default_notification_date(
    transaction_date_str, notification_date_str, doc_id
)

# Use Senate-optimized prompts
system_instruction, user_prompt = generate_financial_prompt(
    document_text, document_source="senate"
)
```

## 🎯 Specific Fixes Applied

### Senate Notification Date Issue

**Before** (causing transaction failures):

```
JT,Salesforce Inc (CRM),S,04/22/2025,,$1,001 - $15,000
```

**After** (using `default_notification_date()`):

```
JT,Salesforce Inc (CRM),S,04/22/2025,04/22/2025,$1,001 - $15,000
```

### Image Document Processing

**Before**: Image documents returned placeholder text
**After**: Full OCR extraction with multiple engine support

### Template-Based Prompts

**Before**: Hard-coded prompts identical for all document types
**After**: Dynamic prompts optimized for Senate tables, House PDFs, and image scans

## 📊 Monitoring and Debugging

### View Current Metrics

```python
from Scripts.common.observability import log_metrics_summary, save_metrics_to_file

# Log metrics to console
log_metrics_summary()

# Save metrics to file
save_metrics_to_file("metrics_report.json")
```

### Check System Health

```python
from Scripts.common.ocr_utils import check_ocr_availability
from Scripts.common.prompt_utils import check_template_availability

print("OCR Status:", check_ocr_availability())
print("Template Status:", check_template_availability())
```

## 🔄 Migration Guide

1. **Install Dependencies**: `pip install -r Scripts/common/requirements.txt`
2. **Update Imports**: Replace duplicated utility functions with common imports
3. **Fix Date Handling**: Use `default_notification_date()` for Senate documents
4. **Update Rate Limiting**: Replace custom rate limiters with shared implementation
5. **Add Monitoring**: Wrap key operations with `@timer` or `track_operation()`

## 🧪 Testing

Run the verification script to ensure everything works:

```python
# Test all utilities
python -m Scripts.common.test_utilities
```

## 🚨 Breaking Changes from Original Implementation

1. **Rate Limiter**: Now requires explicit limiter selection
2. **Date Functions**: Return format standardized across all utilities
3. **Database Schema**: Foreign key constraints now enforced consistently

## 💡 Future Enhancements

Based on the lessons learned, these improvements are planned for future releases:

1. **Unit Testing Framework**: Comprehensive test coverage for all utilities
2. **Configuration Management**: Environment variable support
3. **Advanced OCR**: Custom models for congressional document formats
4. **Real-time Monitoring**: Dashboard for live system monitoring
5. **Distributed Processing**: Multi-machine coordination utilities

## 📚 Related Documentation

- [Original Usage Guide](../USAGE_GUIDE.md)
- [HOR Script Documentation](../HOR%20Script/MULTITHREADING_DOCUMENTATION.md)
- [Project Lessons Learned](../../README.md)

---

These utilities implement the key lessons learned from processing thousands of congressional trading documents, with a focus on reliability, maintainability, and performance.
