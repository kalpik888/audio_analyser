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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=True
    )
