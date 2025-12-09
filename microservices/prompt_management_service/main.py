"""
Prompt Management Service
Port: 8002

Microservice responsible for:
- Managing domain-category combinations
- Validating domain/category pairs
- Generating custom prompts for unknown domains
- Storing and retrieving prompts from database
"""

import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from supabase import Client, create_client
import asyncio

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared_config import (
    PROMPT_SERVICE_PORT, GEMINI_API_KEY, LLM_MODEL,
    SUPABASE_URL, SUPABASE_SERVICE_KEY,
    CORS_ORIGINS, CORS_CREDENTIALS, CORS_METHODS, CORS_HEADERS,
    DEFAULT_DOMAINS_CATEGORIES
)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(LLM_MODEL)

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# In-memory domain tracking
VALID_DOMAINS_CATEGORIES = dict(DEFAULT_DOMAINS_CATEGORIES)

app = FastAPI(
    title="Prompt Management Service",
    version="1.0.0",
    description="Manages prompts, domains, and categories"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_CREDENTIALS,
    allow_methods=CORS_METHODS,
    allow_headers=CORS_HEADERS,
)


@app.on_event("startup")
async def startup():
    """Load domains and categories from database on startup"""
    print("🚀 Loading domains from Supabase...")
    await load_domains_from_db()
    print(f"✅ Loaded domains: {VALID_DOMAINS_CATEGORIES}")


async def load_domains_from_db():
    """Load all discovered domains from database"""
    global VALID_DOMAINS_CATEGORIES
    try:
        response = supabase.table("prompts").select("domain, category").execute()
        
        if response.data:
            for record in response.data:
                domain = record.get("domain")
                category = record.get("category")
                
                if domain and category:
                    if domain not in VALID_DOMAINS_CATEGORIES:
                        VALID_DOMAINS_CATEGORIES[domain] = []
                    if category not in VALID_DOMAINS_CATEGORIES[domain]:
                        VALID_DOMAINS_CATEGORIES[domain].append(category)
    except Exception as e:
        print(f"⚠️  Error loading domains: {e}")


def is_valid_domain_category(domain: str, category: str) -> bool:
    """Check if domain-category combination is valid"""
    return domain in VALID_DOMAINS_CATEGORIES and category in VALID_DOMAINS_CATEGORIES[domain]


async def fetch_example_prompts(prompt_ids: list) -> dict:
    """Fetch example prompts from database"""
    try:
        prompts = {}
        for prompt_id in prompt_ids:
            response = supabase.table("prompts").select("prompt").eq("id", prompt_id).execute()
            if response.data:
                prompts[prompt_id] = response.data[0].get("prompt", "")
        return prompts
    except Exception as e:
        print(f"⚠️  Error fetching example prompts: {e}")
        return {}


async def generate_custom_prompt(domain: str, category: str, example_prompts: dict) -> str:
    """Generate custom prompt using Gemini"""
    try:
        examples_text = ""
        for idx, (prompt_id, prompt_text) in enumerate(example_prompts.items(), 1):
            examples_text += f"\nEXAMPLE {idx}:\n{prompt_text}\n"
        
        generation_prompt = f"""
You are an expert prompt engineer for call center analysis.

Given a call transcript from the domain '{domain}' with category '{category}', 
you need to create an extraction prompt that captures the most relevant information.

Here are example prompts for reference:
{examples_text}

Generate a JSON extraction prompt that specifies what fields should be extracted for this specific domain and category.
The prompt should:
1. Ask to extract key fields relevant to {domain} - {category}
2. Include specific field names and descriptions
3. Ask to return the result as JSON
4. Be concise but comprehensive

Generate ONLY a valid extraction prompt (no JSON wrapper, just the prompt text):
"""
        
        response = model.generate_content(generation_prompt)
        return response.text.strip()
    except Exception as e:
        print(f"⚠️  Error generating prompt: {e}")
        return f"Extract all relevant information from this {domain} call with {category} category. Return as JSON."


async def save_prompt_to_db(domain: str, category: str, prompt: str) -> bool:
    """Save prompt to database"""
    try:
        existing = supabase.table("prompts").select("*").eq("domain", domain).eq("category", category).execute()
        
        if not existing.data:
            supabase.table("prompts").insert({
                "domain": domain,
                "category": category,
                "prompt": prompt
            }).execute()
            print(f"✅ Saved new prompt: {domain}/{category}")
            return True
    except Exception as e:
        print(f"⚠️  Error saving prompt: {e}")
    return False


@app.post("/validate-and-generate")
async def validate_and_generate(request_data: dict):
    """
    Validate domain-category combination and generate prompt if needed.
    
    Input:
        {
            "domain": "healthcare",
            "category": "appointment_scheduling",
            "example_ids": [1, 2]
        }
    
    Output:
        {
            "is_valid": true,
            "custom_prompt": null or "..."
        }
    """
    domain = request_data.get("domain", "")
    category = request_data.get("category", "")
    example_ids = request_data.get("example_ids", [1, 2])
    
    is_valid = is_valid_domain_category(domain, category)
    
    if is_valid:
        return {
            "is_valid": True,
            "custom_prompt": None
        }
    
    # Invalid - generate custom prompt
    print(f"⚠️  New domain-category: {domain}/{category}. Generating custom prompt...")
    
    # Add to tracking
    if domain not in VALID_DOMAINS_CATEGORIES:
        VALID_DOMAINS_CATEGORIES[domain] = []
    VALID_DOMAINS_CATEGORIES[domain].append(category)
    
    # Fetch examples and generate
    example_prompts = await fetch_example_prompts(example_ids)
    custom_prompt = await generate_custom_prompt(domain, category, example_prompts)
    
    # Save asynchronously
    asyncio.create_task(save_prompt_to_db(domain, category, custom_prompt))
    
    return {
        "is_valid": False,
        "custom_prompt": custom_prompt
    }


@app.get("/domains")
async def get_domains():
    """Get all known domains and categories"""
    return {"domains": VALID_DOMAINS_CATEGORIES}


@app.get("/fetch-prompt")
async def fetch_prompt(domain: str, category: str):
    """Fetch prompt from database for given domain-category"""
    try:
        response = supabase.table("prompts").select("prompt").eq("domain", domain).eq("category", category).execute()
        
        if response.data:
            return {"prompt": response.data[0].get("prompt", "")}
    except Exception as e:
        print(f"⚠️  Error fetching prompt: {e}")
    
    return {"prompt": None}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "prompt-management-service"}


if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Starting Prompt Management Service on port {PROMPT_SERVICE_PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=PROMPT_SERVICE_PORT)
