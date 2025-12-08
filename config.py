"""
Configuration and Environment Variables
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ==================== API KEYS ====================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LLM_MODEL = os.getenv("llm_model", "gemini-2.0-flash")

# ==================== SUPABASE ====================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# ==================== APP SETTINGS ====================
APP_TITLE = "Gemini Audio Transcriber"
APP_VERSION = "1.0.0"

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
