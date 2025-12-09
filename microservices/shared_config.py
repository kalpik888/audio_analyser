"""
Shared configuration for all microservices
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ==================== SERVICE PORTS ====================
TRANSCRIPTION_SERVICE_PORT = int(os.getenv("TRANSCRIPTION_SERVICE_PORT", "8001"))
PROMPT_SERVICE_PORT = int(os.getenv("PROMPT_SERVICE_PORT", "8002"))
EXTRACTION_SERVICE_PORT = int(os.getenv("EXTRACTION_SERVICE_PORT", "8003"))
PERSISTENCE_SERVICE_PORT = int(os.getenv("PERSISTENCE_SERVICE_PORT", "8004"))
API_GATEWAY_PORT = int(os.getenv("API_GATEWAY_PORT", "8000"))

# ==================== SERVICE URLS ====================
TRANSCRIPTION_SERVICE_URL = os.getenv("TRANSCRIPTION_SERVICE_URL", f"http://localhost:{TRANSCRIPTION_SERVICE_PORT}")
PROMPT_SERVICE_URL = os.getenv("PROMPT_SERVICE_URL", f"http://localhost:{PROMPT_SERVICE_PORT}")
EXTRACTION_SERVICE_URL = os.getenv("EXTRACTION_SERVICE_URL", f"http://localhost:{EXTRACTION_SERVICE_PORT}")
PERSISTENCE_SERVICE_URL = os.getenv("PERSISTENCE_SERVICE_URL", f"http://localhost:{PERSISTENCE_SERVICE_PORT}")

# ==================== API KEYS ====================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LLM_MODEL = os.getenv("llm_model", "gemini-2.0-flash")

# ==================== SUPABASE ====================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# ==================== APP SETTINGS ====================
APP_TITLE = "Audio Magic Hub - Microservices"
APP_VERSION = "2.0.0"

# ==================== CORS ====================
CORS_ORIGINS = ["*"]
CORS_CREDENTIALS = True
CORS_METHODS = ["*"]
CORS_HEADERS = ["*"]

# ==================== DEFAULT DOMAINS ====================
DEFAULT_DOMAINS_CATEGORIES = {
    "healthcare": ["appointment_scheduling", "billing_inquiry", "prescription_refill"],
    "insurance": ["claim_inquiry", "policy_inquiry", "premium_payment"],
}

# ==================== SERVICE TIMEOUTS ====================
SERVICE_TIMEOUT = int(os.getenv("SERVICE_TIMEOUT", "30"))
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "60"))
