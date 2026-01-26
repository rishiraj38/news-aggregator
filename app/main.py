from fastapi import FastAPI, BackgroundTasks, HTTPException, Header
import logging
import os
from typing import Optional
from app.daily_runner import run_daily_pipeline
from app.database.connection import engine, get_session
from app.database.models import Base, PipelineRun

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for now to support Vercel/Local
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure DB tables exist on startup
@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(engine)

@app.get("/")
def read_root():
    return {"status": "ok", "service": "News Aggregator Agent"}

@app.post("/run-digest")
async def trigger_digest(background_tasks: BackgroundTasks, x_api_key: Optional[str] = Header(None)):
    """
    Trigger the daily digest pipeline.
    Secure this with a simple API Key matching your ENV var for safety.
    """
    cron_secret = os.getenv("CRON_SECRET")
    
    # Simple security check
    if cron_secret and x_api_key != cron_secret:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    logger.info("Received trigger for daily digest pipeline")
    
    # Run in background so the request doesn't timeout
    background_tasks.add_task(run_daily_pipeline_task)
    
    return {"message": "Pipeline triggered in background"}

@app.get("/api/pipeline/status")
def get_pipeline_status():
    session = get_session()
    try:
        # Get latest run
        run = session.query(PipelineRun).order_by(PipelineRun.start_time.desc()).first()
        if not run:
            return {"status": "IDLE", "message": "No runs recorded yet."}
        
        from datetime import timezone
        
        start_time = run.start_time
        if start_time and start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
            
        end_time = run.end_time
        if end_time and end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        
        return {
            "id": run.id,
            "status": run.status,
            "start_time": start_time,
            "end_time": end_time,
            "log_summary": run.log_summary,
            "users_processed": run.users_processed
        }
    finally:
        session.close()

def run_daily_pipeline_task():
    try:
        logger.info("Starting background pipeline task...")
        result = run_daily_pipeline(hours=24, top_n=10)
        logger.info(f"Pipeline finished: {result}")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
