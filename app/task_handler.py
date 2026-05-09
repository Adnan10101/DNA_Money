import re
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Optional, List
from schema import JobStatus, JobRequest
from text_extractor import transaction_extractor
from embedding_utils import categorize_transaction, categorize_transaction2
from schema import Transaction, CategoryResult
from rules import PROVINCES
from notion import NotionManager
from supabase_client import SupabaseManager

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
        transactions=[],
        
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
        category_analysis = []
        embeddings_cnt, llm_cnt, unknown_cnt = 0, 0, 0
        
        for trans in extracted_transactions:
            try:
                
                category_result = categorize_transaction(trans.name, trans.bank_category)
                final_category = category_result.get("category", "Uncategorized")
                source = category_result.get("source","unknown")
                confidence_score = category_result.get("confidence",0.0)
                top_matches = category_result.get("top_matches",[])
                
                trans_dict = Transaction(
                    transaction_date = trans.transaction_date,
                    post_date = trans.post_date,
                    name = trans.name,
                    bank_category = trans.bank_category,
                    actual_category = final_category,
                    amount = trans.amount,
                    source = source,
                )
                
                cat_dict = CategoryResult(
                    name = trans.name,
                    bank_category = trans.bank_category,
                    actual_category = final_category,
                    source = source,
                    confidence_score = confidence_score,
                    top_matches = top_matches
                )
                 
                categorized_transactions.append(trans_dict)
                category_analysis.append(cat_dict)
                
                if source == "embeddings":
                    embeddings_cnt += 1
                elif source == "llm":
                    llm_cnt += 1
            except Exception as e:
                print(f"[Job {job_id}] Error categorizing transaction {trans.name}: {e}")
                trans_dict = Transaction(
                    transaction_date = trans.transaction_date,
                    post_date = trans.post_date,
                    name = trans.name,
                    bank_category = trans.bank_category,
                    actual_category = "Uncategorized",
                    amount =  0.0,
                    source = "Unknown"
                )
                categorized_transactions.append(trans_dict)
                unknown_cnt += 1
        
        # Step 3: Update job with results
        total_transaction_count = len(categorized_transactions)
        
        print(f"[Job {job_id}] Successfully processed {total_transaction_count} transactions")
        
        JOBS[job_id].transactions = categorized_transactions
        JOBS[job_id].transactions_count = total_transaction_count
        JOBS[job_id].llm_categorized_count = llm_cnt
        JOBS[job_id].embeddings_categorized_count = embeddings_cnt
        JOBS[job_id].unknowns_count = unknown_cnt
        
        # Step 4.1: upload to DB
        upload_category_analysis_to_supabase(job_id, category_analysis)
        
        # Step 4.2: Upload to Notion
        try:
            print(f"[Job {job_id}] Uploading {total_transaction_count} transactions to Notion...")
            notion_manager = NotionManager()
            successful, failed = notion_manager.add_transactions_batch(categorized_transactions)
            print(f"[Job {job_id}] Notion upload complete: {successful} successful out of {total_transaction_count}, {len(failed)} failed")
        except Exception as e:
            print(f"[Job {job_id}] Warning: Notion upload failed - {str(e)}. Continuing without Notion sync.")
        
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


def clean_merchant(name: str) -> str:
    name = re.sub(PROVINCES + r".*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name).strip()
    return name


# ============================================================================
# ASYNC SUPABASE UPLOAD FUNCTIONS
# ============================================================================

async def upload_category_analysis_to_supabase(
    job_id: str,
    category_analysis: List[CategoryResult],
    use_batch_with_retry: bool = True
) -> Dict:
    """
    Async function to upload category analysis to Supabase
    
    Args:
        job_id: Job ID for tracking
        category_analysis: List of CategoryResult objects
        use_batch_with_retry: If True, uses batch upload with retry logic
        
    Returns:
        Dictionary with upload status
    """
    try:
        supabase_manager = SupabaseManager()
        
        if use_batch_with_retry:
            result = await supabase_manager.upload_batch_with_retry(
                category_analysis=category_analysis,
                job_id=job_id,
                table_name="category_analysis",
                max_retries=3,
                batch_size=100
            )
        else:
            result = await supabase_manager.upload_category_analysis(
                category_analysis=category_analysis,
                job_id=job_id,
                table_name="category_analysis"
            )
        
        print(f"[Job {job_id}] Supabase upload result: {result}")
        return result
        
    except Exception as e:
        error_msg = f"Error uploading to Supabase: {str(e)}"
        print(f"[Job {job_id}] {error_msg}")
        return {
            "success": False,
            "message": error_msg,
            "job_id": job_id
        }