"""
Persistence Service
Port: 8004

Microservice responsible for:
- Saving call metadata to database
- Saving domain-specific extracted data
- Managing database operations
"""

import json
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase import Client, create_client

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared_config import (
    PERSISTENCE_SERVICE_PORT,
    SUPABASE_URL, SUPABASE_SERVICE_KEY,
    CORS_ORIGINS, CORS_CREDENTIALS, CORS_METHODS, CORS_HEADERS
)

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

app = FastAPI(
    title="Persistence Service",
    version="1.0.0",
    description="Handles all database persistence operations"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_CREDENTIALS,
    allow_methods=CORS_METHODS,
    allow_headers=CORS_HEADERS,
)


@app.post("/save")
async def save_call_data(request_data: dict):
    """
    Save call metadata and domain-specific data to database.
    
    Input:
        {
            "general_data": {
                "file_name": "...",
                "domain": "...",
                "category": "...",
                "agent_name": "...",
                ...
            },
            "domain_specific_data": "{JSON string}"
        }
    
    Output:
        {
            "success": true,
            "call_id": 42,
            "domain_specific_id": 156
        }
    """
    try:
        general_data = request_data.get("general_data", {})
        domain_specific_text = request_data.get("domain_specific_data", "{}")
        
        # Insert to general table
        general_response = supabase.table("general").insert(general_data).execute()
        
        if not general_response.data:
            return {
                "success": False,
                "error": "Failed to insert general data"
            }
        
        call_id = general_response.data[0].get("id")
        print(f"✅ Saved to general table with call_id: {call_id}")
        
        # Insert to domain_specific table with call_id
        domain_specific_data = {
            "data": domain_specific_text,
            "call_id": call_id
        }
        
        domain_response = supabase.table("domain_specific").insert(domain_specific_data).execute()
        
        if not domain_response.data:
            print(f"⚠️  Domain-specific data save failed, but general data saved with call_id: {call_id}")
            return {
                "success": True,
                "call_id": call_id,
                "domain_specific_id": None,
                "warning": "Domain-specific save failed"
            }
        
        domain_specific_id = domain_response.data[0].get("id")
        print(f"✅ Saved to domain_specific table with id: {domain_specific_id}")
        
        return {
            "success": True,
            "call_id": call_id,
            "domain_specific_id": domain_specific_id
        }
    
    except Exception as e:
        print(f"❌ Database persistence error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/call/{call_id}")
async def get_call_data(call_id: int):
    """Retrieve call data by ID"""
    try:
        general_response = supabase.table("general").select("*").eq("id", call_id).execute()
        
        if not general_response.data:
            return {"error": "Call not found"}
        
        general_data = general_response.data[0]
        
        domain_response = supabase.table("domain_specific").select("*").eq("call_id", call_id).execute()
        domain_data = domain_response.data[0] if domain_response.data else None
        
        return {
            "general": general_data,
            "domain_specific": domain_data
        }
    except Exception as e:
        print(f"❌ Retrieval error: {e}")
        return {"error": str(e)}


@app.get("/stats")
async def get_stats():
    """Get database statistics"""
    try:
        general_count = supabase.table("general").select("id", count="exact").execute()
        domain_count = supabase.table("domain_specific").select("id", count="exact").execute()
        prompt_count = supabase.table("prompts").select("id", count="exact").execute()
        
        return {
            "total_calls": general_count.count or 0,
            "domain_specific_records": domain_count.count or 0,
            "stored_prompts": prompt_count.count or 0
        }
    except Exception as e:
        print(f"⚠️  Error fetching stats: {e}")
        return {"error": str(e)}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "persistence-service"}


if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Starting Persistence Service on port {PERSISTENCE_SERVICE_PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=PERSISTENCE_SERVICE_PORT)
