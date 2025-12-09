"""
Transcription Service
Port: 8001

Microservice responsible for:
- Transcribing audio files
- Detecting business domain and category
- Using Gemini API processing
"""

import json
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from fastapi import UploadFile, File

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared_config import (
    TRANSCRIPTION_SERVICE_PORT, GEMINI_API_KEY, LLM_MODEL,
    CORS_ORIGINS, CORS_CREDENTIALS, CORS_METHODS, CORS_HEADERS
)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(LLM_MODEL)

app = FastAPI(
    title="Transcription Service",
    version="1.0.0",
    description="Handles audio transcription and domain/category detection"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_CREDENTIALS,
    allow_methods=CORS_METHODS,
    allow_headers=CORS_HEADERS,
)

MIME_TYPE_MAPPING = {
    "application/octet-stream": {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "m4a": "audio/mp4",
    }
}


def get_domains_categories_text() -> str:
    """
    Returns domain-category text from config.
    In microservices, this should be fetched from Prompt Service.
    For now, using a simple in-memory version.
    """
    domains = {
        "healthcare": ["appointment_scheduling", "billing_inquiry", "prescription_refill"],
        "insurance": ["claim_inquiry", "policy_inquiry", "premium_payment"],
    }
    text = ""
    for domain, categories in domains.items():
        text += f"for {domain}: {', '.join(categories)}\n"
    return text

def normalize_mime_type(file: UploadFile) -> str:
    """
    Normalize the MIME type of uploaded file.
    
    Args:
        file: Uploaded file
        
    Returns:
        Normalized MIME type
    """
    mime_type = file.content_type
    
    if mime_type == "application/octet-stream":
        ext = file.filename.split(".")[-1].lower()
        mime_type = MIME_TYPE_MAPPING["application/octet-stream"].get(ext, mime_type)
    
    return mime_type

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """
    Transcribe audio and detect domain/category.
    
    Input:
        {
            "file_bytes": hex string of audio file,
            "mime_type": "audio/mpeg" etc
        }
    
    Output:
        {
            "transcription": "...",
            "domain": "healthcare",
            "category": "appointment_scheduling",
            "tokens_stage1": [input, output]
        }
    """
    try:
        # Decode file bytes from hex
        file_bytes = await file.read()
        mime_type = normalize_mime_type(file)
        
        domains_categories_text = get_domains_categories_text()
        
        detection_prompt = f"""
You are an expert call classifier and transcription specialist.

## TASK 1: TRANSCRIPTION
Transcribe the provided audio file accurately with timestamps and speaker labels.

Output format:
[HH:MM - HH:MM] Speaker: Text here

---

## TASK 2: DOMAIN AND CATEGORY DETECTION

After transcribing, identify:
1. **Domain**: The industry/business domain
2. **Category**: The specific category within that domain

Known domain and category combinations:
{domains_categories_text}

if domain or category is not from the given list, identify it accordingly.

Be precise in categorization. Use snake_case for both domain and category.

---

## OUTPUT FORMAT

Return ONLY valid JSON:

{{
  "transcription": "Full transcript with timestamps here...",
  "domain": string,
  "category": string
}}
"""

        response = model.generate_content([
            detection_prompt,
            {
                "mime_type": mime_type,
                "data": file_bytes
            }
        ])

        token_input = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        token_output = response.usage_metadata.candidates_token_count if response.usage_metadata else 0

        cleaned_response = response.text.replace("```json", "").replace("```", "").strip()
        parsed_response = json.loads(cleaned_response)

        return {
            "transcription": parsed_response.get("transcription", ""),
            "domain": parsed_response.get("domain", "unknown"),
            "category": parsed_response.get("category", "unknown"),
            "tokens_usage": {
                 "input_tokens":token_input,
                 'output_token': token_output
            }
        }
    
    except Exception as e:
        print(f"❌ Transcription Error: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "transcription-service"}


if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Starting Transcription Service on port {TRANSCRIPTION_SERVICE_PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=TRANSCRIPTION_SERVICE_PORT)
