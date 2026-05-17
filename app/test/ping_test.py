import asyncio
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import uvicorn

app = FastAPI()
scheduler = AsyncIOScheduler()

async def slow_job(job_id: str):
    print(f"[{job_id}] starting...")
    await asyncio.sleep(10)
    print(f"[{job_id}] done!")

@app.on_event("startup")
def start():
    scheduler.start()

@app.get("/start")
async def start_job():
    scheduler.add_job(slow_job, args=["test123"])
    return {"status": "queued"}

@app.get("/ping")
async def ping():
    return {"status": "alive"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)