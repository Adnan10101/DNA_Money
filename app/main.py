import os
import tempfile
import asyncio
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Depends
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from authlib.integrations.starlette_client import OAuth
from jose import jwt, JWTError
from datetime import datetime, timedelta

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

load_dotenv()

# GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
# GITHUB_CLIENT_SECRET = os.getenv("GITHUB_SECRET")
# JWT_SECRET = os.getenv("JWT_SECRET")
# JWT_ALGORITHM = "HS256"
# ALLOWED_GITHUB_USERS = set(os.getenv("ALLOWED_USERS", "").split(","))
# PUBLIC_ROUTES = {
#     "/login",
#     "/auth/github/callback",
#     "/docs",
#     "/openapi.json",
#     "/redoc",
# }

# def create_token(user: dict):
#     payload = {
#         "sub": user["login"],
#         "github_id": user["id"],
#         "exp": datetime.utcnow() + timedelta(hours=1)
#     }

#     return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

app = FastAPI(
    title="DNA Money API",
    description="API for expense tracking and analysis",
    version="1.0.0",
)

# app.add_middleware(
#     SessionMiddleware,
#     secret_key=os.getenv("JWT_SECRET")
# )

# oauth = OAuth()
# oauth.register(
#     name="github",

#     client_id=GITHUB_CLIENT_ID,
#     client_secret=GITHUB_CLIENT_SECRET,

#     access_token_url="https://github.com/login/oauth/access_token",

#     authorize_url="https://github.com/login/oauth/authorize",

#     api_base_url="https://api.github.com/",

#     client_kwargs={
#         "scope": "read:user user:email"
#     }
# )


# Background scheduler for async tasks
# Initialize with get_event_loop to ensure proper event loop binding
scheduler = AsyncIOScheduler()

#################
# Login
# @app.get("/login")
# async def login(request: Request):
#     redirect_uri = request.url_for("auth_callback")
#     return await oauth.github.authorize_redirect(
#         request,
#         redirect_uri
#     )
    
###############
# Callback
# @app.get("/auth/github/callback")
# async def auth_callback(request: Request):

#     token = await oauth.github.authorize_access_token(request)

#     response = await oauth.github.get("user", token=token)

#     github_user = response.json()

#     if github_user["login"] not in ALLOWED_GITHUB_USERS:
#         raise HTTPException(status_code=403, detail="Not authorized")
    
#     # ✅ CREATE YOUR OWN TOKEN
#     app_token = create_token(github_user)

#     # ✅ STORE IN COOKIE
#     res = JSONResponse({
#         "message": "Login successful",
#         "github_user": github_user
#     })

#     res.set_cookie(
#         key="access_token",
#         value=app_token,
#         httponly=True
#     )

#     return res

# async def get_current_user(request: Request):

#     token = request.cookies.get("access_token")

#     if not token:
#         raise HTTPException(
#             status_code=401,
#             detail="Not authenticated"
#         )

#     try:
#         payload = jwt.decode(
#             token,
#             JWT_SECRET,
#             algorithms=[JWT_ALGORITHM]
#         )
#         return payload

#     except JWTError:
#         raise HTTPException(
#             status_code=401,
#             detail="Invalid token"
#         )

@app.on_event("startup")
async def start_scheduler():
    """Start background scheduler on app startup"""
    if not scheduler.running:
        # Ensure scheduler uses the current event loop
        scheduler.configure(event_loop=asyncio.get_event_loop())
        scheduler.start()


@app.on_event("shutdown")
async def shutdown_scheduler():
    """Shutdown scheduler on app shutdown"""
    if scheduler.running:
        scheduler.shutdown(wait=False)



@app.get("/")
async def read_root():
    """Welcome endpoint"""
    return {"message": "Welcome to DNA Money API", "version": "1.0.0"}


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
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
async def get_upload_status(job_id: str):
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
async def add_manual_transaction(transaction: ManualTransactionRequest):
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