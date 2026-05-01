import os
import tempfile
import threading
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler

from schema import (
    Item,
    Transaction,
    JobStatus,
    JobResponse,
    ManualTransactionRequest,
    ManualTransactionResponse,
)
from task_handler import (
    create_job,
    get_job,
    process_pdf_upload,
    categorize_and_upload_transaction,
)

app = FastAPI(
    title="DNA Money API",
    description="API for expense tracking and analysis",
    version="1.0.0",
    debug=True
)

# Background scheduler for async tasks
scheduler = BackgroundScheduler()


@app.on_event("startup")
def start_scheduler():
    """Start background scheduler on app startup"""
    if not scheduler.running:
        scheduler.start()


@app.on_event("shutdown")
def shutdown_scheduler():
    """Shutdown scheduler on app shutdown"""
    if scheduler.running:
        scheduler.shutdown()



@app.get("/")
def read_root():
    """Welcome endpoint"""
    return {"message": "Welcome to DNA Money API", "version": "1.0.0"}


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload a PDF statement for processing.
    Returns immediately with a job_id for tracking progress.
    Processing happens asynchronously in the background.
    """
    # Create job
    job_id = create_job(file_name=file.filename)
    
    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    # Schedule background processing
    try:
        scheduler.add_job(
            process_pdf_upload,
            args=[job_id, tmp_path],
            id=job_id,
            replace_existing=True
        )
        
        return {
            "job_id": job_id,
            "status": "queued",
            "message": "PDF upload queued for processing. Use GET /upload/{job_id} to check status."
        }
    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=f"Error queueing job: {str(e)}")


@app.get("/upload/{job_id}")
def get_upload_status(job_id: str):
    """
    Get the status of a PDF upload job.
    Returns the current status and extracted/categorized transactions if completed.
    """
    job = get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    response = JobResponse(
        job_id=job.job_id,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        transactions_count=job.transactions_count,
        transactions=job.transactions if job.status == JobStatus.COMPLETED else None,
        llm_categorized_count = job.llm_categorized_count,
        unknowns_count = job.unknowns_count,
        embeddings_categorized_count = job.embeddings_categorized_count,
        error=job.error,
    )
    
    return response


# havent reviewed this yet
@app.post("/transaction")
def add_manual_transaction(transaction: ManualTransactionRequest):
    """
    Add a single transaction manually.
    Categorizes the transaction and returns the result.
    """
    try:
        # Convert request to dict
        trans_dict = {
            "transaction_date": transaction.transaction_date,
            "post_date": transaction.post_date,
            "name": transaction.name,
            "category": transaction.category,
            "amount": transaction.amount,
        }
        
        # Categorize if no category provided
        if not transaction.category:
            trans_dict = categorize_and_upload_transaction(trans_dict)
        else:
            trans_dict["confidence"] = 1.0  # Manual input has high confidence
            trans_dict["notion_url"] = None
        
        response = ManualTransactionResponse(
            transaction_date=trans_dict["transaction_date"],
            post_date=trans_dict["post_date"],
            name=trans_dict["name"],
            category=trans_dict["category"],
            amount=trans_dict["amount"],
            confidence=trans_dict.get("confidence"),
            notion_url=trans_dict.get("notion_url")
        )
        
        return {
            "status": "success",
            "transaction": response
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing transaction: {str(e)}")


# Run the app
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)