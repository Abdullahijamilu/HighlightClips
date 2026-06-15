import asyncio
import uuid
import os
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict

from clipper_core import run_pipeline

app = FastAPI(title="Highlight Clipper API")

# Allow frontend to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job storage
# Format: { "job_id": { "status": "processing|completed|error", "progress": int, "stage": str, "message": str, "results": list } }
jobs: Dict[str, dict] = {}

# Ensure output directories exist
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "highlights")
os.makedirs(OUTPUT_DIR, exist_ok=True)

class ClipRequest(BaseModel):
    url: str
    num_clips: int = 5
    format: str = "vertical"
    style: str = "cinematic"
    whisper_model: str = "tiny"
    min_gap: int = 40

def process_video_task(job_id: str, req: ClipRequest):
    def progress_callback(msg: str, progress: int, stage: str):
        if job_id in jobs:
            jobs[job_id]["message"] = msg
            if progress is not None:
                jobs[job_id]["progress"] = progress
            if stage is not None:
                jobs[job_id]["stage"] = stage

    try:
        results = run_pipeline(
            source_url=req.url,
            output_dir=OUTPUT_DIR,
            format_name=req.format,
            style_name=req.style,
            whisper_model_size=req.whisper_model,
            num_clips=req.num_clips,
            min_gap=req.min_gap,
            progress_callback=progress_callback
        )
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["stage"] = "done"
        jobs[job_id]["results"] = results
        jobs[job_id]["message"] = "Processing complete!"
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["message"] = str(e)
        jobs[job_id]["stage"] = "error"

@app.post("/api/clip")
async def start_clipping(req: ClipRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "processing",
        "progress": 0,
        "stage": "starting",
        "message": "Initializing...",
        "results": []
    }
    
    # Run the processing in the background
    background_tasks.add_task(process_video_task, job_id, req)
    
    return {"job_id": job_id}

UPLOAD_DIR = os.path.join(OUTPUT_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/api/upload_clip")
async def upload_and_clip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    num_clips: int = Form(5),
    format: str = Form("vertical"),
    style: str = Form("cinematic"),
    whisper_model: str = Form("tiny"),
    min_gap: int = Form(40)
):
    import shutil
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "processing",
        "progress": 0,
        "stage": "starting",
        "message": "Saving uploaded file...",
        "results": []
    }
    
    file_extension = os.path.splitext(file.filename)[1]
    safe_filename = f"{job_id}{file_extension}"
    local_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    with open(local_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    req = ClipRequest(
        url=local_path,
        num_clips=num_clips,
        format=format,
        style=style,
        whisper_model=whisper_model,
        min_gap=min_gap
    )
    
    jobs[job_id]["message"] = "Upload complete! Initializing AI..."
    background_tasks.add_task(process_video_task, job_id, req)
    
    return {"job_id": job_id}

@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/api/download/{filename}")
async def download_clip(filename: str):
    # Security: prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
        
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(file_path, media_type="video/mp4", filename=filename)

if __name__ == "__main__":
    import uvicorn
    # Start the server
    uvicorn.run(app, host="127.0.0.1", port=8000)
