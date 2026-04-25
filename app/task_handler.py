import uuid
from datetime import datetime
from typing import Dict, Optional
from schema import JobStatus, JobRequest
from text_extractor import transaction_extractor
from embedding_utils import categorize_transaction
import tempfile
import os

# In-memory job storage (could be replaced with database later)
JOBS: Dict[str, JobRequest] = {}


def create_job(file_name: Optional[str] = None) -> str:
    """Create a new job and return job_id"""
    job_id = str(uuid.uuid4())
    job = JobRequest(
        job_id=job_id,
        file_name=file_name,
        status=JobStatus.PENDING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        transactions_count=0,
        transactions=[]
    )
    JOBS[job_id] = job
    return job_id


def get_job(job_id: str) -> Optional[JobRequest]:
    """Retrieve job status"""
    return JOBS.get(job_id)


def update_job_status(job_id: str, status: JobStatus, error: Optional[str] = None):
    """Update job status"""
    if job_id in JOBS:
        JOBS[job_id].status = status
        JOBS[job_id].updated_at = datetime.now()
        if error:
            JOBS[job_id].error = error


def process_pdf_upload(job_id: str, file_path: str):
    """
    Background task: Extract transactions from PDF, categorize, and prepare for Notion upload
    """
    try:
        update_job_status(job_id, JobStatus.PROCESSING)
        
        # Step 1: Extract transactions from PDF
        print(f"[Job {job_id}] Extracting transactions from PDF...")
        extracted_transactions = transaction_extractor(file_path)
        
        if not extracted_transactions:
            update_job_status(job_id, JobStatus.FAILED, "No transactions found in PDF")
            return
        
        # Step 2: Categorize each transaction
        print(f"[Job {job_id}] Categorizing {len(extracted_transactions)} transactions...")
        categorized_transactions = []
        
        # this should be updated, poor logic
        for trans in extracted_transactions:
            try:
                category_result = categorize_transaction(trans.name)
                trans_dict = {
                    "transaction_date": trans.transaction_date,
                    "post_date": trans.post_date,
                    "name": trans.name,
                    "category": category_result.get("category") or "Uncategorized",
                    "amount": trans.amount,
                    "confidence": category_result.get("confidence"),
                    "notion_url": None  # Will be set after Notion upload
                }
                categorized_transactions.append(trans_dict)
            except Exception as e:
                print(f"[Job {job_id}] Error categorizing transaction {trans.name}: {e}")
                trans_dict = {
                    "transaction_date": trans.transaction_date,
                    "post_date": trans.post_date,
                    "name": trans.name,
                    "category": "Uncategorized",
                    "amount": trans.amount,
                    "confidence": 0.0,
                    "notion_url": None
                }
                categorized_transactions.append(trans_dict)
        
        # Step 3: Update job with results (Notion upload would happen here)
        print(f"[Job {job_id}] Successfully processed {len(categorized_transactions)} transactions")
        
        JOBS[job_id].transactions = categorized_transactions
        JOBS[job_id].transactions_count = len(categorized_transactions)
        update_job_status(job_id, JobStatus.COMPLETED)
        
    except Exception as e:
        error_msg = f"Error processing PDF: {str(e)}"
        print(f"[Job {job_id}] {error_msg}")
        update_job_status(job_id, JobStatus.FAILED, error_msg)


def categorize_and_upload_transaction(transaction_dict: dict) -> dict:
    """
    Categorize a single transaction and prepare for Notion upload
    """
    try:
        category_result = categorize_transaction(transaction_dict["name"])
        transaction_dict["category"] = category_result.get("category") or "Uncategorized"
        transaction_dict["confidence"] = category_result.get("confidence")
        transaction_dict["notion_url"] = None  # Will be set after Notion upload
        return transaction_dict
    except Exception as e:
        print(f"Error categorizing transaction: {e}")
        transaction_dict["category"] = "Uncategorized"
        transaction_dict["confidence"] = 0.0
        transaction_dict["notion_url"] = None
        return transaction_dict
