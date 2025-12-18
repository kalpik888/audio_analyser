"""
API Gateway
Port: 8000

Main entry point that orchestrates all microservices:
- Receives audio file uploads
- Coordinates calls between services
- Aggregates results
- Returns unified response
"""

import json
import sys
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import asyncio

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared_config import (
    API_GATEWAY_PORT, SERVICE_TIMEOUT,
    TRANSCRIPTION_SERVICE_URL, TONAL_SERVICE_URL,
    EXTRACTION_SERVICE_URL,
    CORS_ORIGINS, CORS_CREDENTIALS, CORS_METHODS, CORS_HEADERS
)

app = FastAPI(
    title="Audio Magic Hub - API Gateway",
    version="2.0.0",
    description="Orchestrates microservices for audio analysis"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_CREDENTIALS,
    allow_methods=CORS_METHODS,
    allow_headers=CORS_HEADERS,
)


async def call_service(service_url: str, endpoint: str, data: dict = None, files: dict = None, params: dict = None) -> dict:
    """
    Call a microservice with retry logic.
    
    Args:
        service_url: Base URL of service
        endpoint: API endpoint path
        data: JSON payload (mutually exclusive with files)
        files: Files for multipart/form-data upload
        params: Query parameters
    """
    url = f"{service_url}{endpoint}"
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=SERVICE_TIMEOUT) as client:
                if files:
                    # Send as multipart/form-data
                    response = await client.post(url, files=files, params=params)
                else:
                    # Send as JSON
                    response = await client.post(url, json=data, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            print(f"⚠️  Service call failed (attempt {attempt + 1}/{max_retries}): {url}")
            print(f"   Status: {e.response.status_code}")
            print(f"   Response: {e.response.text}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)
        except Exception as e:
            print(f"⚠️  Service call failed (attempt {attempt + 1}/{max_retries}): {url}")
            print(f"   Error: {str(e)}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)


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
            "agent_name": "Not Available",
            "customer_name": "Not Available",
            "call_direction": "Not Available",
            "interaction_type": "Not Available",
            "sentiment": "Not Available",
            "intent": "Not Available",
        }


@app.on_event("startup")
async def startup():
    """Verify all microservices are healthy on startup"""
    print("🚀 API Gateway starting up...")
    print(f"   Transcription Service: {TRANSCRIPTION_SERVICE_URL}")
    print(f"   Tonal Service: {TONAL_SERVICE_URL}")
    print(f"   Extraction Service: {EXTRACTION_SERVICE_URL}")
    
    services = {
        "Transcription": TRANSCRIPTION_SERVICE_URL,
        "Tonal": TONAL_SERVICE_URL,
        "Extraction": EXTRACTION_SERVICE_URL,
    }
    
    async with httpx.AsyncClient(timeout=5) as client:
        for name, url in services.items():
            try:
                response = await client.get(f"{url}/health")
                print(f"   ✅ {name} Service: OK")
            except Exception as e:
                print(f"   ⚠️  {name} Service: OFFLINE ({e})")


@app.post("/api/transcribe/")
async def transcribe_endpoint(file: UploadFile = File(...)):
    """
    Main endpoint: Orchestrates all microservices.
    
    Flow:
    1. Transcription Service: Transcribe + detect domain/category
    2. Tonal Service: Analyze tonal aspects
    3. Extraction Service: Extract data and analyze
    
    Args:
        file: Audio file to process
        
    Returns:
        JSON response with transcription, analysis, and token breakdown
    """
    import asyncio
    
    print(f"📂 Received file: {file.filename} | Type: {file.content_type}")
    
    try:
        # Normalize MIME type
        mime_type = file.content_type
        if mime_type == "application/octet-stream":
            ext = file.filename.split(".")[-1].lower()
            mime_type_map = {
                "mp3": "audio/mpeg",
                "wav": "audio/wav",
                "m4a": "audio/mp4",
            }
            mime_type = mime_type_map.get(ext, mime_type)
        
        # Read file
        file_bytes = await file.read()

        #print(file_bytes.hex())
        # print(mime_type)
        
        # ============ STAGE 1: Transcription Service ============
        print("🎙️  Calling Transcription Service...")
        stage1_result = await call_service(
            TRANSCRIPTION_SERVICE_URL,
            "/transcribe",
            files={"file": ("audio.bin", file_bytes, mime_type)}
        )
        #print(stage1_result)
        
        transcription = stage1_result.get("transcription", "")
        domain = stage1_result.get("domain", "unknown")
        category = stage1_result.get("category", "unknown")
        tokens_stage1 = stage1_result.get("tokens_stage1", [0, 0])
        
        print(f"✅ Domain: {domain} | Category: {category}")

        # ============ TONAL ANALYSIS SERVICE ============
        print("🎙️  Calling Tonal Analysis Service...")

        tonal_result = await call_service(
            TONAL_SERVICE_URL,
            "/analyze_tonal",
            files={"file": ("audio.bin", file_bytes, mime_type)}
        )

        #print(tonal_result)
        
        
        # ============ STAGE 2: Extraction Service ============
        print("🔍 Calling Extraction Service...")
        try:
            extraction_result = await call_service(
                EXTRACTION_SERVICE_URL,
                "/extract",
                data={
                    "transcription": transcription,
                    "domain": domain,
                    "category": category
                }
            )
        except Exception as e:
            print(f"❌ Extraction Service Error: {e}")
            extraction_result = {
                "domain_specific_data": {},
                "general_metrics": {},
                "tokens_combined": [0, 0]
            }
        
        domain_specific_data = extraction_result.get("domain_specific_data", {})
        general_metrics = extraction_result.get("general_metrics", {})
        tokens_combined = extraction_result.get("tokens_combined", [0, 0])
        
        # ============ Extract and prepare data ============
        print("📊 Processing metrics...")
        extracted_metrics = extract_general_metrics(general_metrics)
        print(f"   Extracted metrics: {extracted_metrics}")
        print(f"   tokens_stage1: {tokens_stage1}")
        print(f"   tokens_combined: {tokens_combined}")
        
        total_tokens_input = tokens_stage1[0] + tokens_combined[0]
        total_tokens_output = tokens_stage1[1] + tokens_combined[1]
        total_tokens = total_tokens_input + total_tokens_output
        
        
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
            "total_tokens": total_tokens,
        }

        import supabase
        from shared_config import SUPABASE_URL, SUPABASE_SERVICE_KEY
        supabase_client: supabase.Client = supabase.create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

        saved_data = supabase_client.table("general").insert(general_data).execute()

        call_id = saved_data.data[0].get("id", None)

        data_to_domain_specific = {
            "call_id": call_id,
            "data": json.dumps(domain_specific_data, indent=2)
        }

        supabase_client.table("domain_specific").insert(data_to_domain_specific).execute()

        data_to_tonal_analysis = {
            "call_id": call_id,
            "data": json.dumps(tonal_result, indent=2)
        }

        supabase_client.table("tonal_analysis").insert(data_to_tonal_analysis).execute()


        
        
        # ============ Return unified response ============
        return JSONResponse(content={
            "filename": file.filename,
            "transcription": transcription,
            "domain": domain,
            "category": category,
            "domain_specific_data": domain_specific_data,
            "general_metrics": general_metrics,
            "tonal_analysis": tonal_result,
            "token_usage": {
                "stage1_transcription_and_detection": {
                    "input": tokens_stage1[0],
                    "output": tokens_stage1[1],
                    "total": sum(tokens_stage1)
                },
                "stage2_combined_analysis": {
                    "input": tokens_combined[0],
                    "output": tokens_combined[1],
                    "total": sum(tokens_combined)
                },
                "total": {
                    "input": total_tokens_input,
                    "output": total_tokens_output,
                    "total": total_tokens
                }
            }
        })
    
    except Exception as e:
        import traceback
        print(f"❌ Request failed: {e}")
        print(f"   Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.get("/health")
async def health():
    """API Gateway health check"""
    return {
        "status": "healthy",
        "service": "api-gateway",
        "services": {
            "transcription": f"{TRANSCRIPTION_SERVICE_URL}/health",
            "extraction": f"{EXTRACTION_SERVICE_URL}/health",
            "tonal_analysis": f"{TONAL_SERVICE_URL}/health",
        }
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Audio Magic Hub - Microservices API Gateway",
        "version": "2.0.0",
        "docs": "/docs",
        "endpoints": {
            "transcribe": "POST /api/transcribe/",
            "health": "GET /health"
        }
    }


if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Starting API Gateway on port {API_GATEWAY_PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=API_GATEWAY_PORT)
