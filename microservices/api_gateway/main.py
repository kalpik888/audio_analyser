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
    TRANSCRIPTION_SERVICE_URL, PROMPT_SERVICE_URL,
    EXTRACTION_SERVICE_URL, PERSISTENCE_SERVICE_URL,
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


async def call_service(service_url: str, endpoint: str, data: dict) -> dict:
    """
    Call a microservice with retry logic
    """
    url = f"{service_url}{endpoint}"
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=SERVICE_TIMEOUT) as client:
                response = await client.post(url, json=data)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"⚠️  Service call failed (attempt {attempt + 1}/{max_retries}): {url}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)


def extract_general_metrics(general_metrics: dict) -> dict:
    """Extract and flatten general metrics from nested structure"""
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


@app.on_event("startup")
async def startup():
    """Verify all microservices are healthy on startup"""
    print("🚀 API Gateway starting up...")
    print(f"   Transcription Service: {TRANSCRIPTION_SERVICE_URL}")
    print(f"   Prompt Service: {PROMPT_SERVICE_URL}")
    print(f"   Extraction Service: {EXTRACTION_SERVICE_URL}")
    print(f"   Persistence Service: {PERSISTENCE_SERVICE_URL}")
    
    services = {
        "Transcription": TRANSCRIPTION_SERVICE_URL,
        "Prompt": PROMPT_SERVICE_URL,
        "Extraction": EXTRACTION_SERVICE_URL,
        "Persistence": PERSISTENCE_SERVICE_URL
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
    1. Transcription Service: Transcribe + detect domain
    2. Prompt Service: Validate domain/category, generate if needed
    3. Extraction Service: Extract data and analyze
    4. Persistence Service: Save to database
    
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
        
        # ============ STAGE 1: Transcription Service ============
        print("🎙️  Calling Transcription Service...")
        stage1_result = await call_service(
            TRANSCRIPTION_SERVICE_URL,
            "/transcribe",
            {
                "file_bytes": file_bytes.hex(),
                "mime_type": mime_type
            }
        )
        
        transcription = stage1_result.get("transcription", "")
        domain = stage1_result.get("domain", "unknown")
        category = stage1_result.get("category", "unknown")
        tokens_stage1 = stage1_result.get("tokens_stage1", [0, 0])
        
        print(f"✅ Domain: {domain} | Category: {category}")
        
        # ============ VALIDATION: Prompt Service ============
        print("🔍 Calling Prompt Management Service...")
        prompt_result = await call_service(
            PROMPT_SERVICE_URL,
            "/validate-and-generate",
            {
                "domain": domain,
                "category": category,
                "example_ids": [1, 2]
            }
        )
        
        is_valid = prompt_result.get("is_valid", True)
        custom_prompt = prompt_result.get("custom_prompt")
        
        if is_valid:
            print("✅ Domain-category is valid")
        else:
            print("✅ Generated custom prompt for new domain-category")
        
        # ============ STAGE 2: Extraction Service ============
        print("🔍 Calling Extraction Service...")
        extraction_result = await call_service(
            EXTRACTION_SERVICE_URL,
            "/extract",
            {
                "transcription": transcription,
                "domain": domain,
                "category": category,
                "custom_prompt": custom_prompt
            }
        )
        
        domain_specific_data = extraction_result.get("domain_specific_data", {})
        general_metrics = extraction_result.get("general_metrics", {})
        tokens_combined = extraction_result.get("tokens_combined", [0, 0])
        
        # ============ Extract and prepare data ============
        extracted_metrics = extract_general_metrics(general_metrics)
        
        total_tokens_input = tokens_stage1[0] + tokens_combined[0]
        total_tokens_output = tokens_stage1[1] + tokens_combined[1]
        total_tokens = total_tokens_input + total_tokens_output
        
        # ============ PERSISTENCE: Save to Database ============
        print("💾 Calling Persistence Service...")
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
        
        persistence_result = await call_service(
            PERSISTENCE_SERVICE_URL,
            "/save",
            {
                "general_data": general_data,
                "domain_specific_data": json.dumps(domain_specific_data, indent=2)
            }
        )
        
        if persistence_result.get("success"):
            call_id = persistence_result.get("call_id")
            print(f"✅ Data saved with call_id: {call_id}")
        else:
            print(f"⚠️  Database save failed: {persistence_result.get('error')}")
        
        # ============ Return unified response ============
        return JSONResponse(content={
            "filename": file.filename,
            "transcription": transcription,
            "domain": domain,
            "category": category,
            "domain_specific_data": domain_specific_data,
            "general_metrics": general_metrics,
            "database": {
                "success": persistence_result.get("success", False),
                "call_id": persistence_result.get("call_id"),
                "message": "Data persisted successfully" if persistence_result.get("success") else "Failed to persist"
            },
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
        print(f"❌ Request failed: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.get("/health")
async def health():
    """API Gateway health check"""
    return {
        "status": "healthy",
        "service": "api-gateway",
        "services": {
            "transcription": f"{TRANSCRIPTION_SERVICE_URL}/health",
            "prompt": f"{PROMPT_SERVICE_URL}/health",
            "extraction": f"{EXTRACTION_SERVICE_URL}/health",
            "persistence": f"{PERSISTENCE_SERVICE_URL}/health"
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
