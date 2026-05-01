# DNA Money 💰

A intelligent expense tracking system that automatically extracts and categorizes financial transactions from bank statements using a hybrid embedding + LLM approach.

## Overview

DNA Money is a FastAPI-based API that processes PDF bank statements to extract transactions and intelligently categorize them. It uses a two-stage categorization pipeline:

1. **Semantic Embeddings** (Fast & Free): Compares merchant names against historical transaction embeddings to quickly categorize expenses
2. **LLM Fallback** (Accurate & Smart): Uses OpenAI-compatible LLMs via OpenRouter when embedding confidence is low

The system processes PDFs asynchronously in the background, allowing you to upload statements and poll for results without blocking requests.

## Key Features

✨ **Categorization**
- Dual-stage categorization with embedding + LLM fallback
- Tracks confidence scores and categorization source (embeddings vs LLM)
- Learns from historical transactions to minimize LLM calls

📄 **PDF Processing**
- Automatic extraction of transactions from bank statements
- Intelligent handling of multi-line transaction formatting
- Support for province identifiers (Canadian banks)
- Configurable PDF markers for different bank statement formats

⚡ **Async Job Processing**
- Non-blocking PDF uploads with background processing
- Job status tracking with unique job IDs
- Real-time progress updates

🏗️ **RESTful API**
- Simple endpoints for PDF uploads and manual transaction entry
- Comprehensive job status tracking
- Automatic error handling and reporting

**Note**
The categorization goal is to maximize embedding results while minizing LLM calls (not a fan of LLM honestly). But as an early test, it will help me build enough data points for the embedding model to perform better. (The constraint is that my 'manual' data entry differs from the way the data is present in the estatements, hence 'stupid' LLMs are used).

## Project Structure

```
app/
├── main.py                 # FastAPI application & endpoints
├── schema.py              # Pydantic models for data validation
├── task_handler.py        # Background job processing logic
├── embedding_utils.py     # Semantic embedding & LLM categorization
├── text_extractor.py      # PDF parsing and transaction extraction
└── rules.py               # PDF patterns, regex rules, and prompts

data/
├── expenses_2023_2024_2025.csv    # Historical expense data
├── expenses_2026.csv              # Additional expense records
├── expenses_embeddings.csv        # Pre-computed embeddings for historical transactions
└── extracted_transactions.csv     # Sample of extracted transactions

model/
└── embedding_model.ipynb  # Jupyter notebook for training embeddings
```

## Installation

### Prerequisites
- Python 3.8+
- Virtual environment (recommended)

### Setup

1. **Clone the repository and navigate to the project:**
   ```bash
   cd DNA_Money
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv env
   source env/Scripts/activate  # On Windows
   # or
   source env/bin/activate      # On macOS/Linux
   ```

3. **Install dependencies:**
   ```bash
   pip install fastapi uvicorn pydantic apscheduler
   pip install pymupdf pandas numpy scikit-learn sentence-transformers
   pip install openai python-dotenv
   ```

4. **Configure environment variables:**
   Create a `.env` file in the `app/` directory:
   ```env
   OPENROUTER_API_KEY=your_openrouter_api_key
   EMBEDDING_MODEL_PATH=../model/embedding_model.pkl
   EXPENSES_EMBEDDING_DATA_PATH=../data/expenses_embeddings.csv
   ```

## API Reference

### Endpoints

#### 1. **Upload PDF Statement**
```http
POST /upload
```
Upload a bank statement PDF for transaction extraction and categorization.

**Request:**
- **Content-Type:** `multipart/form-data`
- **Body:** `file` (PDF file)

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "PDF upload queued for processing. Use GET /upload/{job_id} to check status."
}
```

---

#### 2. **Get Upload Status**
```http
GET /upload/{job_id}
```
Retrieve the status and results of a PDF processing job.

**Response (Pending/Processing):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "created_at": "2026-04-30T10:15:00",
  "updated_at": "2026-04-30T10:15:05",
  "transactions_count": 0,
  "transactions": null,
  "error": null,
  "llm_categorized_count": 0,
  "embeddings_categorized_count": 0,
  "unknowns_count": 0
}
```

**Response (Completed):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "created_at": "2026-04-30T10:15:00",
  "updated_at": "2026-04-30T10:15:30",
  "transactions_count": 42,
  "transactions": [
    {
      "transaction_date": "Apr 01",
      "post_date": "Apr 02",
      "name": "UBER EATS TORONTO ON",
      "bank_category": "Restaurants",
      "actual_category": "Food",
      "amount": 50,
      "source": "embeddings"
    },
    ...
  ],
  "error": null,
  "llm_categorized_count": 8,
  "embeddings_categorized_count": 32,
  "unknowns_count": 2
}
```

---
## WIP
#### 3. **Add Manual Transaction**
```http
POST /transaction
```
Manually add a single transaction or categorize it without a category.

**Request:**
```json
{
  "transaction_date": "Apr 15",
  "post_date": "Apr 16",
  "name": "WHOLE FOODS MARKET #10234",
  "category": null,
  "amount": 87.43
}
```

**Response:**
```json
{
  "status": "success",
  "transaction": {
    "transaction_date": "Apr 15",
    "post_date": "Apr 16",
    "name": "WHOLE FOODS MARKET #10234",
    "category": "Groceries",
    "amount": 87.43,
    "confidence": 0.78,
    "notion_url": null
  }
}
```

---
## Nobody cares about this (actually nobody cares about the entire project)
#### 4. **Welcome Endpoint**
```http
GET /
```
Health check and API information.

**Response:**
```json
{
  "message": "Welcome to DNA Money API",
  "version": "1.0.0"
}
```
# Yeah I will get out of local soon (Need to turn up my server)
## Running the Application

### Start the server:
```bash
cd app
python main.py
```

The API will be available at `http://localhost:8000`

### Access interactive documentation:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Architecture

### Transaction Categorization Pipeline

```
PDF Upload
    ↓
PDF Parsing (text_extractor.py)
    ↓
Transaction Extraction (PyMuPDF + Regex)
    ↓
For Each Transaction:
    ├─→ Clean merchant name
    ├─→ Generate embedding
    ├─→ Compare against historical embeddings
    ├─→ If confidence ≥ threshold
    │   └─→ Return embedding category ✓
    └─→ Else
        └─→ Call LLM with context
            └─→ Return LLM-categorized category ✓
    ↓
Return Results with Stats
(embeddings_count, llm_count, unknowns_count)
```

### Key Components

**PDF Parsing (`text_extractor.py`)**
- Uses PyMuPDF to extract text blocks from PDFs
- Identifies transaction sections using configurable markers
- Merges text blocks that appear on the same row
- Applies regex patterns to parse individual transactions

**Embedding Categorization (`embedding_utils.py`)**
- Loads pre-trained embedding model (SentenceTransformers)
- Computes cosine similarity against historical transaction embeddings
- Returns top-3 matches with confidence scores
- **Primary Strategy:** Lower threshold (0.70) to minimize LLM calls
- **Alternative Strategy (v2):** Voting mechanism with top-10 matches for higher accuracy

**LLM Fallback (`embedding_utils.py`)**
- Uses OpenRouter API with Nemotron 3 Super 120B model (free tier)
- Provides context: merchant name, bank category, closest embedding matches
- Returns structured category from predefined list
- Only called when embedding confidence is too low

**Job Management (`task_handler.py`)**
- In-memory job storage (dict-based)
- Background processing with APScheduler
- Tracks transaction counts by categorization source
- Handles errors gracefully with detailed error messages

## Configuration

### PDF Parsing Rules

Edit `app/rules.py` to customize:

```python
PDF_MARKERS = {
    'start_marker': "Your new charges and credits\n",
    'end_marker': "Transactions are assigned...\n"
}
```

### Categorization Thresholds

Adjust embedding similarity thresholds in `embedding_utils.py`:
```python
def categorize_transaction(merchant_name: str, threshold: float = 0.70):
    # Lower threshold → more LLM calls but higher accuracy
    # Higher threshold → fewer LLM calls but more "Uncategorized"
```

### Available Categories

Modify the category list in `app/rules.py`:
```python
NOTION_CATEGORIES = [
    "Shopping", "Entertainments", "Utilities", "Education",
    "Transport", "Health & Wellness", "Rent", "Groceries",
    "Food", "Charity", "Home", "Travel", "Housing", "subscriptions"
]
```

## Data Files

- **`expenses_embeddings.csv`**: Pre-computed embeddings for all historical transactions
  - Columns: `Name_clean`, `Category_clean`, `embeddings` (list format)
  - Used for fast similarity matching

- **`expenses_2023_2024_2025.csv`**: Historical transaction data
  - Used to train and validate the embedding model

# WIP
## Performance Characteristics

| Metric | Value |
|--------|-------|
| Embedding Lookup | - per transaction |
| LLM API Call | -  per transaction |
| PDF Parsing | - per page |
| Job Processing | Async (non-blocking) |
| Average Embedding Hit Rate | - |

## Development Notes (This is actually true)

### Hybrid Strategy Evolution
The system uses `categorize_transaction()` (v1) by default because:
- Lower threshold (0.70) minimizes LLM calls
- Empirically performs better with manual Notion entries that differ from bank statements
- Reduces API costs while maintaining decent accuracy
- Alternative v2 (`categorize_transaction2()`) uses voting on top-10 matches for higher accuracy but more LLM calls


## Environment Setup Tips

### For macOS/Linux:
```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

### For Windows PowerShell:
```powershell
python -m venv env
env\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Troubleshooting

**Issue: "Embedding model not found"**
- Ensure `EMBEDDING_MODEL_PATH` points to the correct `.pkl` file
- Run the notebook in `model/embedding_model.ipynb` to regenerate the model

**Issue: "OpenRouter API key not found"**
- Create a `.env` file in `app/` directory with `OPENROUTER_API_KEY=your_key`
- Alternatively, set environment variables directly

**Issue: "PDF parsing returns no transactions"**
- Verify the PDF structure matches your bank's format
- Update `PDF_MARKERS` in `rules.py` to match your statement layout
- Check if transaction pattern regex needs adjustment

**Issue: Jobs processing very slowly**
- Likely hitting LLM rate limits (OpenRouter free tier)
- Improve embedding threshold to reduce LLM calls
- Consider using a paid tier with higher rate limits
