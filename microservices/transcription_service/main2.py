"""
Transcription Service (Official Gemini Batch API Mode)
Port: 8001
"""

import json
import sys
import uuid
import os
import shutil
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
# Assuming these exist in your shared_config
from shared_config import (
    GEMINI_API_KEY, LLM_MODEL,
    CORS_ORIGINS, CORS_CREDENTIALS, CORS_METHODS, CORS_HEADERS
)

# --- CONFIGURATION ---
client = genai.Client(api_key=GEMINI_API_KEY)

# Temporary storage for uploaded files before sending to Google
TEMP_UPLOAD_DIR = Path("/tmp/audio_uploads")
TEMP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# --- JOB STORAGE ---
# In production, use Redis or Postgres.
# Mapping: local_job_id -> { "google_batch_name": str, "google_file_uri": str }
jobs: Dict[str, Dict[str, str]] = {}

app = FastAPI(
    title="Transcription Service (Gemini Batch)",
    version="2.0.0",
    description="Asynchronous audio transcription using Gemini Batch API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_CREDENTIALS,
    allow_methods=CORS_METHODS,
    allow_headers=CORS_HEADERS,
)

def get_domains_categories_text() -> str:
    """Returns domain-category text."""
    domains = {
        "healthcare": ["appointment_scheduling", "billing_inquiry", "prescription_refill"],
        "insurance": ["claim_inquiry", "policy_inquiry", "premium_payment"],
    }
    text = ""
    for domain, categories in domains.items():
        text += f"for {domain}: {', '.join(categories)}\n"
    return text

# --- API ENDPOINTS ---

@app.post("/transcribe")
async def submit_transcription(file: UploadFile = File(...)):
    """
    1. Uploads file to Google File API.
    2. Submits a Batch Job.
    3. Returns a Job ID immediately.
    """
    temp_file_path = TEMP_UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
    
    try:
        # STEP 1: Save to local temp disk (Required for client.files.upload)
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # STEP 2: Upload to Google File API
        # The Batch API cannot take raw bytes, it needs a File URI
        print(f"Uploading {file.filename} to Google File API...")
        google_file = client.files.upload(
            file=temp_file_path,
            config={'mime_type': file.content_type}
        )

        # STEP 3: Prepare the Prompt
        domains_categories_text = get_domains_categories_text()
        prompt_text = f"""
        You are an expert call classifier.
        TASK 1: Transcribe the audio with timestamps [HH:MM - HH:MM] Speaker: Text.
        TASK 2: Identify Domain and Category from this list:
        {domains_categories_text}
        
        Return ONLY valid JSON:
        {{ "transcription": "...", "domain": "...", "category": "..." }}
        """

        # STEP 4: Define the Request
        # Fix 1: Use 'generationConfig' (camelCase), NOT 'generation_config'
        # Fix 2: Use a plain dictionary for the config
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
            src=[batch_request], 
            config={'display_name': f"job-{local_job_id}"} # <--- FIXED: Use a simple dict
        )

        # STEP 6: Store Mapping
        jobs[local_job_id] = {
            "google_batch_name": batch_job.name,
            "google_file_name": google_file.name # Keep track to delete later
        }

        return {
            "job_id": local_job_id,
            "google_batch_id": batch_job.name,
            "status": "QUEUED",
            "message": "Batch Job Submitted successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Submission failed: {str(e)}")
    finally:
        # Cleanup local temp file
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
        # STEP 1: Get Job Status from Google
        batch_job = client.batches.get(name=google_batch_name)
        state = batch_job.state.name

        response = {
            "job_id": job_id,
            "status": state, # JOB_STATE_SUCCEEDED, JOB_STATE_ACTIVE, etc.
        }

        # STEP 2: If Succeeded, fetch results
        if state == "JOB_STATE_SUCCEEDED":
            # The batch job output is stored in batch_job.dest.inlined_responses
            # Since we submitted 1 request, we get the first response.
            for inline_response in batch_job.dest.inlined_responses:
                if inline_response.response:
                    raw_text = inline_response.response.text
                    try:
                        parsed_json = json.loads(raw_text)
                        response["result"] = parsed_json
                    except json.JSONDecodeError:
                        response["result"] = raw_text # Fallback if JSON fails
            
            # OPTIONAL: Cleanup Google File API to save storage cost
            # client.files.delete(name=job_record["google_file_name"])

        elif state == "JOB_STATE_FAILED":
             response["error"] = f"Batch job failed. Error: {batch_job.error.message}"

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "transcription-service-gemini-batch"}