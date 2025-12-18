"""
Audio Magic Hub - Main Application Entry Point

A production-ready audio transcription and analysis system that:
- Transcribes audio files with timestamps and speaker labels
- Detects business domain and category automatically
- Extracts domain-specific data using specialized prompts
- Performs general call analysis (sentiment, agent metrics, PII detection)
- Saves results to Supabase for persistence and analytics

Architecture:
- FastAPI: Modern async web framework
- Google Gemini 2.0-flash: LLM for transcription and analysis
- Supabase: PostgreSQL database for persistence
- Modular services: Clean separation of concerns
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import config
from services.domain_service import initialize_domains_from_db
from routes.transcription import router as transcription_router
from fastapi import UploadFile, File
import google.generativeai as genai
from config import GEMINI_API_KEY, LLM_MODEL

# ==================== INITIALIZE FASTAPI APP ====================

app = FastAPI(
    title=config.APP_TITLE,
    version=config.APP_VERSION,
    description="Audio transcription and analysis service"
)

# ==================== ADD MIDDLEWARE ====================

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=config.CORS_CREDENTIALS,
    allow_methods=config.CORS_METHODS,
    allow_headers=config.CORS_HEADERS,
)

# ==================== STARTUP EVENT ====================

@app.on_event("startup")
async def startup_event():
    """
    Run when FastAPI app starts.
    Load all domains and categories from Supabase.
    """
    print("🚀 Starting up Audio Magic Hub...")
    initialize_domains_from_db()
    print("✅ Application startup complete!")


# ==================== SHUTDOWN EVENT ====================

@app.on_event("shutdown")
async def shutdown_event():
    """
    Run when FastAPI app shuts down.
    """
    print("🛑 Shutting down Audio Magic Hub...")


# ==================== INCLUDE ROUTERS ====================

app.include_router(transcription_router, prefix="/api", tags=["transcription"])


# ==================== HEALTH CHECK ENDPOINT ====================

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        Status and version information
    """
    return {
        "status": "healthy",
        "app": config.APP_TITLE,
        "version": config.APP_VERSION
    }
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(LLM_MODEL)


# ==================== ROOT ENDPOINT ====================

@app.get("/")
async def root():
    """
    Root endpoint with API documentation.
    
    Returns:
        Welcome message and documentation link
    """
    return {
        "message": f"Welcome to {config.APP_TITLE}",
        "docs": "/docs",
        "version": config.APP_VERSION
    }

@app.post("/tonal")
async def tonal(file: UploadFile = File(...)):
    mime_type = file.content_type

    MIME_TYPE_MAPPING = {
    "application/octet-stream": {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "m4a": "audio/mp4",
    }
}
    
    if mime_type == "application/octet-stream":
        ext = file.filename.split(".")[-1].lower()
        mime_type = MIME_TYPE_MAPPING["application/octet-stream"].get(ext, mime_type)
    
    prompt="""
You are an expert tonal analysis specialist.
Listen to this customer service call. 
Perform a tonal analysis focusing on the customer's voice.
1. Did the customer sound satisfied at the end?
2. Identify any timestamps where the pitch or speed indicated frustration.
Provide your analysis in the following JSON format:
{"tonal_sentiment_analysis": "detailed analysis of tone and sentiment here..."}

    """

    
    # Read file
    file_bytes = await file.read()

    

    response = model.generate_content([prompt, {
            "mime_type": mime_type,
            "data": file_bytes
        }])
    
    input_tokens = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
    output_tokens = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
    
    return {

        "tonal_analysis": response.text,
        "token_usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens
        }
    }
    



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=True
    )
