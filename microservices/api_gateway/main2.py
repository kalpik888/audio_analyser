"""
Main entry point that orchestrates all microservices (Batch Supported):
- Receives audio file uploads
- Submits Batch Jobs to Transcription & Tonal Services
- Polls for completion
- Chains Extraction Service
- Aggregates results
"""

import json
import sys
import asyncio
import httpx
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import supabase

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared_config import (
    API_GATEWAY_PORT, SERVICE_TIMEOUT,
    TRANSCRIPTION_SERVICE_URL, TONAL_SERVICE_URL,
    EXTRACTION_SERVICE_URL,
    CORS_ORIGINS, CORS_CREDENTIALS, CORS_METHODS, CORS_HEADERS,
    SUPABASE_URL, SUPABASE_SERVICE_KEY
)



app = FastAPI(
    title="Audio Magic Hub - API Gateway",
    version="2.1.0",
    description="Orchestrates microservices (Batch Aware)"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_CREDENTIALS,
    allow_methods=CORS_METHODS,
    allow_headers=CORS_HEADERS,
)

# Initialize Supabase
supabase_client: supabase.Client = supabase.create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


async def submit_job(service_url: str, endpoint: str, files: dict) -> str:
    """Submits a file to a batch service and returns the Job ID."""
    url = f"{service_url}{endpoint}"
    async with httpx.AsyncClient(timeout=SERVICE_TIMEOUT) as client:
        response = await client.post(url, files=files)
        response.raise_for_status()
        return response.json().get("job_id")

async def poll_until_complete(service_url: str, job_id: str, interval: int = 10, timeout: int = 600) -> dict:
    """
    Polls a batch service's /status/{job_id} endpoint until completion.
    """
    status_url = f"{service_url}/status/{job_id}"
    start_time = asyncio.get_event_loop().time()
    
    async with httpx.AsyncClient(timeout=30) as client: # Short timeout for the status check itself
        while True:
            # Check for global timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(f"Job {job_id} on {service_url} timed out after {timeout}s")

            try:
                response = await client.get(status_url)
                response.raise_for_status()
                data = response.json()
                status = data.get("status")

                if status == "JOB_STATE_SUCCEEDED" or status == "completed":
                    return data.get("result", {})
                elif status == "JOB_STATE_FAILED" or status == "failed":
                    raise Exception(f"Job failed: {data.get('error')}")
                
                # Still processing
                # print(f"⏳ Polling {service_url} (Job: {job_id})... Status: {status}")
                await asyncio.sleep(interval)
                
            except httpx.RequestError as e:
                print(f"⚠️ Polling connection error: {e}. Retrying...")
                await asyncio.sleep(interval)

async def call_sync_service(service_url: str, endpoint: str, data: dict) -> dict:
    """Helper for calling synchronous services (Extraction Service)."""
    url = f"{service_url}{endpoint}"
    async with httpx.AsyncClient(timeout=SERVICE_TIMEOUT) as client:
        response = await client.post(url, json=data)
        response.raise_for_status()
        return response.json()

def extract_general_metrics(general_metrics: dict) -> dict:
    """Extract and flatten general metrics from nested structure"""
    try:
        sec1 = general_metrics.get("section_1_name_extraction", {})
        sec2 = general_metrics.get("section_2_call_direction_interaction_type", {})
        sec3 = general_metrics.get("section_3_sentiment_and_intent_detection", {})

        return {
            "agent_name": sec1.get("agent_name", "Not Available"),
            "customer_name": sec1.get("customer_name", "Not Available"),
            "call_direction": sec2.get("call_direction", "Not Available"),
            "interaction_type": sec2.get("interaction_type", "Not Available"),
            "sentiment": sec3.get("sentiment", "Not Available"),
            "intent": sec3.get("intent", "Not Available"),
        }
    except Exception as e:
        print(f"❌ Error extracting metrics: {e}")
        return {
            "agent_name": "Not Available", "customer_name": "Not Available",
            "call_direction": "Not Available", "interaction_type": "Not Available",
            "sentiment": "Not Available", "intent": "Not Available",
        }

# --- MAIN ENDPOINT ---

@app.post("/api/transcribe/")
async def transcribe_endpoint(file: UploadFile = File(...)):
    print(f"📂 Received file: {file.filename} | Type: {file.content_type}")
    
    try:
        # 1. Prepare File
        file_bytes = await file.read()
        mime_type = file.content_type
        # (Add your mime_type normalization logic here if needed)

        # 2. SUBMIT JOBS (Parallel Submission)
        # We send the file to both services essentially at the same time
        print("🚀 Submitting Batch Jobs...")
        
        # We need to create separate file payloads for the requests
        files_payload = {"file": (file.filename, file_bytes, mime_type)}
        
        # Submit to Transcription
        transcript_job_id = await submit_job("http://localhost:8006", "/transcribe", files_payload)
        print(f"   -> Transcription Job ID: {transcript_job_id}")

        # Submit to Tonal (Assuming Tonal is also batch now)
        tonal_job_id = await submit_job("http://localhost:8008", "/analyze_tonal", files_payload) 
        print(f"   -> Tonal Job ID: {tonal_job_id}")

        # 3. POLL FOR COMPLETION (Parallel Polling)
        # We wait for BOTH to finish. Extraction cannot start without Transcription.
        print("⏳ Polling services for completion (this may take minutes)...")
        
        transcript_task = poll_until_complete("http://localhost:8006", transcript_job_id)
        tonal_task = poll_until_complete("http://localhost:8008", tonal_job_id)

        # asyncio.gather runs them concurrently
        results = await asyncio.gather(transcript_task, tonal_task)
        
        transcript_result = results[0]
        tonal_result = results[1]
        
        print("✅ Batch Jobs Completed!")

        # 4. PREPARE DATA FOR EXTRACTION
        transcription_text = transcript_result.get("transcription", "")
        domain = transcript_result.get("domain", "unknown")
        category = transcript_result.get("category", "unknown")
        
        # 5. CALL EXTRACTION SERVICE (Synchronous)
        # Now that we have the text, we can analyze it.
        print("🔍 Calling Extraction Service...")
        extraction_result = await call_sync_service(
            EXTRACTION_SERVICE_URL, 
            "/extract",
            data={
                "transcription": transcription_text,
                "domain": domain,
                "category": category
            }
        )

        # 6. AGGREGATE DATA
        domain_specific_data = extraction_result.get("domain_specific_data", {})
        general_metrics = extraction_result.get("general_metrics", {})
        
        # Token Aggregation
        tokens_stage1 = transcript_result.get("tokens_stage1", [0, 0]) # Input, Output
        tokens_combined = extraction_result.get("tokens_combined", [0, 0])
        
        total_tokens_input = tokens_stage1[0] + tokens_combined[0]
        total_tokens_output = tokens_stage1[1] + tokens_combined[1]
        
        # Extract Flat Metrics for DB
        extracted_metrics = extract_general_metrics(general_metrics)

        # 7. SAVE TO DATABASE
        print("💾 Saving to Supabase...")
        
        general_data = {
            "file_name": file.filename,
            "domain": domain,
            "category": category,
            "agent_name": extracted_metrics["agent_name"],
            "customer_name": extracted_metrics["customer_name"],
            "call_direction": extracted_metrics["call_direction"],
            "interaction_type": extracted_metrics["interaction_type"],
            "sentiment": extracted_metrics["sentiment"],
            "intent": extracted_metrics["intent"],
            "tokens_input": total_tokens_input,
            "tokens_output": total_tokens_output,
            "total_tokens": total_tokens_input + total_tokens_output,
        }

        saved_data = supabase_client.table("general").insert(general_data).execute()
        call_id = saved_data.data[0].get("id")

        if call_id:
            # Save Domain Specific
            supabase_client.table("domain_specific").insert({
                "call_id": call_id,
                "data": json.dumps(domain_specific_data)
            }).execute()

            # Save Tonal
            supabase_client.table("tonal_analysis").insert({
                "call_id": call_id,
                "data": json.dumps(tonal_result)
            }).execute()

        # 8. RETURN UNIFIED RESPONSE
        return JSONResponse(content={
            "filename": file.filename,
            "transcription": transcription_text,
            "domain": domain,
            "category": category,
            "domain_specific_data": domain_specific_data,
            "general_metrics": general_metrics,
            "tonal_analysis": tonal_result,
            "status": "success"
        })

    except TimeoutError as te:
        print(f"❌ Timeout: {te}")
        raise HTTPException(status_code=504, detail="Processing timed out waiting for Batch API")
    except Exception as e:
        import traceback
        print(f"❌ Error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/")
async def root():
    return {"message": "Audio Magic Hub - API Gateway is running."}