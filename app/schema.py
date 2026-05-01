from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
from datetime import datetime


class Item(BaseModel):
    name: str
    price: float
    description: str = None


class Transaction(BaseModel):
    transaction_date: str
    post_date: str
    name: str
    bank_category: str
    actual_category: str = None
    amount: float
    source: str = "unknown"


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobRequest(BaseModel):
    """Model for job requests"""
    job_id: str
    file_name: Optional[str] = None
    status: JobStatus = JobStatus.PENDING
    created_at: datetime
    updated_at: datetime
    error: Optional[str] = None
    transactions_count: int = 0
    transactions: List[Transaction] = []
    llm_categorized_count: int = 0
    embeddings_categorized_count: int = 0
    unknowns_count: int = 0


class JobResponse(BaseModel):
    """Model for job status response"""
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    transactions_count: int
    transactions: Optional[List[Transaction]] = None
    error: Optional[str] = None
    llm_categorized_count: int = 0
    embeddings_categorized_count: int = 0
    unknowns_count: int = 0


class ManualTransactionRequest(BaseModel):
    """Model for manual transaction entry"""
    transaction_date: str
    post_date: str
    name: str
    category: Optional[str] = None
    amount: float


class ManualTransactionResponse(BaseModel):
    """Model for manual transaction response"""
    transaction_date: str
    post_date: str
    name: str
    category: str
    amount: float
    confidence: Optional[float] = None
    notion_url: Optional[str] = None