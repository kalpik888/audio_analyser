"""
Tonal Analysis Service (Gemini Batch API Mode)
Port: 8002
"""

import json
import sys
import uuid
import os
import shutil
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared_config import (
    TONAL_SERVICE_PORT, # Make sure this is 8002 in shared_config
    GEMINI_API_KEY, LLM_MODEL,
    CORS_ORIGINS, CORS_CREDENTIALS, CORS_METHODS, CORS_HEADERS
)

client = genai.Client(api_key=GEMINI_API_KEY)

# Temporary storage for uploaded files before sending to Google
TEMP_UPLOAD_DIR = Path("/tmp/tonal_uploads")
TEMP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# --- JOB STORAGE ---
# Mapping: local_job_id -> { "google_batch_name": str, "google_file_name": str }
jobs: Dict[str, Dict[str, str]] = {}

app = FastAPI(
    title="Tonal Service (Batch)",
    version="2.0.0",
    description="Asynchronous tonal analysis using Gemini Batch API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_CREDENTIALS,
    allow_methods=CORS_METHODS,
    allow_headers=CORS_HEADERS,
)

# --- API ENDPOINTS ---

@app.post("/analyze_tonal")
async def analyze_tonal(file: UploadFile = File(...)):
    """
    1. Uploads file to Google File API.
    2. Submits a Batch Job.
    3. Returns a Job ID immediately.
    """
    temp_file_path = TEMP_UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
    
    try:
        # STEP 1: Save to local temp disk
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # STEP 2: Upload to Google File API
        print(f"Uploading {file.filename} to Google File API...")
        google_file = client.files.upload(
            file=temp_file_path,
            config={'mime_type': file.content_type}
        )

        # STEP 3: Prepare the Prompt
        prompt_text = """
        You are an expert tonal and sentiment analysis specialist.
        Listen to the provided audio file and give a detailed analysis of the tone and sentiment.
        
        Return ONLY valid JSON:
        {
          "overall_analysis": {
            "summary": "Brief summary",
            "overall_sentiment": "Positive/Neutral/Negative",
            "overall_tone": "e.g., Urgent, Calm"
          },
          "key_tonal_shifts": [
            {
              "timestamp": "MM:SS",
              "trigger_event": "What caused the shift",
              "description": "Description of shift"
            }
          ]
        }
        """

        # STEP 4: Define the Request
        batch_request = {
            "contents": [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_uri(
                            file_uri=google_file.uri,
                            mime_type=google_file.mime_type
                        ),
                        types.Part.from_text(text=prompt_text),
                    ]
                )
            ],
            "config": {
                "response_mime_type": "application/json"
            }
        }

        # STEP 5: Submit Batch Job
        local_job_id = str(uuid.uuid4())
        
        batch_job = client.batches.create(
            model=LLM_MODEL,
            src=[batch_request], # List of requests
            config={'display_name': f"tonal-job-{local_job_id}"}
        )

        # STEP 6: Store Mapping
        jobs[local_job_id] = {
            "google_batch_name": batch_job.name,
            "google_file_name": google_file.name
        }

        # CRITICAL: Return 'job_id' so the Gateway can track it
        return {
            "job_id": local_job_id,
            "google_batch_id": batch_job.name,
            "status": "QUEUED"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tonal submission failed: {str(e)}")
    finally:
        if temp_file_path.exists():
            os.remove(temp_file_path)


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """
    Polls the Google Batch API for the status of the job.
    """
    job_record = jobs.get(job_id)
    if not job_record:
        raise HTTPException(status_code=404, detail="Job ID not found")

    google_batch_name = job_record["google_batch_name"]

    try:
        # STEP 1: Get Job Status
        batch_job = client.batches.get(name=google_batch_name)
        state = batch_job.state.name

        response = {
            "job_id": job_id,
            "status": state, # JOB_STATE_SUCCEEDED, JOB_STATE_ACTIVE
        }

        # STEP 2: If Succeeded, fetch results
        if state == "JOB_STATE_SUCCEEDED":
            for inline_response in batch_job.dest.inlined_responses:
                if inline_response.response:
                    raw_text = inline_response.response.text
                    try:
                        parsed_json = json.loads(raw_text)
                        response["result"] = parsed_json
                    except json.JSONDecodeError:
                        response["result"] = {"raw_text": raw_text}

        elif state == "JOB_STATE_FAILED":
             response["error"] = f"Job failed: {batch_job.error.message}"

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "tonal-service-batch"}

if __name__ == "__main__":
    import uvicorn
    # Make sure this port matches shared_config.py (should be 8002)
    uvicorn.run(app, host="0.0.0.0", port=8002)