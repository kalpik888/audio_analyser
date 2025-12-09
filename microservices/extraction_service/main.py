"""
Extraction Service
Port: 8003

Microservice responsible for:
- Domain-specific data extraction
- General call analysis (sentiment, metrics, PII)
- Combining both analyses in single LLM call
"""

import json
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from supabase import Client, create_client

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared_config import (
    EXTRACTION_SERVICE_PORT, GEMINI_API_KEY, LLM_MODEL,
    SUPABASE_URL, SUPABASE_SERVICE_KEY,
    CORS_ORIGINS, CORS_CREDENTIALS, CORS_METHODS, CORS_HEADERS
)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(LLM_MODEL)

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

app = FastAPI(
    title="Extraction Service",
    version="1.0.0",
    description="Handles domain-specific data extraction and general call analysis"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_CREDENTIALS,
    allow_methods=CORS_METHODS,
    allow_headers=CORS_HEADERS,
)


async def fetch_prompt_from_db(domain: str, category: str) -> str:
    """Fetch extraction prompt from database"""
    try:
        response = supabase.table("prompts").select("*").eq("domain", domain).eq("category", category).execute()
        
        if response.data:
            return response.data[0].get("prompt", "")
    except Exception as e:
        print(f"⚠️  Error fetching prompt: {e}")
    
    return None

def fetch_example_prompts() -> dict:
    """
    Fetch example prompts from Supabase by IDs.
    
    Args:
        prompt_ids: List of prompt IDs to fetch
        
    Returns:
        Dictionary mapping ID to prompt text
    """
    prompt_ids = [1, 2]
    example_prompts = {}
    try:
        for prompt_id in prompt_ids:
            response = supabase.table("prompts").select("prompt").eq("id", prompt_id).execute()
            if response.data and len(response.data) > 0:
                example_prompts[prompt_id] = response.data[0].get("prompt", "")
    except Exception as e:
        print(f"⚠️  Error fetching example prompts: {e}")
    
    return example_prompts

def generate_extraction_prompt(domain: str, category: str, example_prompts: dict) -> str:
    """
    Use LLM to generate an extraction prompt for unknown domain-category combination.
    
    Args:
        domain: Business domain
        category: Category within domain
        example_prompts: Dictionary of example prompts
        
    Returns:
        Generated prompt text
    """
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
        generated_prompt = response["text"].strip()
        print(f"✅ Generated custom prompt for {domain}/{category}")
        return generated_prompt
    
    except Exception as e:
        print(f"⚠️  Error generating prompt: {e}")
        return f"Extract all relevant information from this {domain} call with {category} category. Return as JSON."



@app.post("/extract")
async def extract_data(transcription: str, domain: str, category: str):
    """
    Extract domain-specific data and general call analysis.
    
    Input:
        {
            "transcription": "...",
            "domain": "healthcare",
            "category": "appointment_scheduling",
            "custom_prompt": "..." or null
        }
    
    Output:
        {
            "domain_specific_data": {...},
            "general_metrics": {...},
            "tokens_combined": [input, output]
        }
    """
    try:
       
        extraction_prompt = await fetch_prompt_from_db(domain, category)
        
        if not extraction_prompt:
            example_prompts = fetch_example_prompts()
            extraction_prompt = generate_extraction_prompt(domain, category, example_prompts)

        # Combined analysis prompt
        combined_prompt = f"""
You are analyzing a {domain} call ({category} category).

## PART 1: DOMAIN-SPECIFIC DATA EXTRACTION

{extraction_prompt}

---

## PART 2: GENERAL CALL ANALYSIS

Analyze the transcript and extract:

1. **Names**: agent_name, customer_name
2. **Call Metadata**: call_direction (Inbound/Outbound), interaction_type (Conversation/Voicemail)
3. **Sentiment & Intent**: sentiment (Positive/Neutral/Negative), intent (3-5 word summary)
4. **Summary**: Brief summary of the conversation
5. **Agent Metrics**: empathy_score (0-10), professionalism_score (0-10), knowledge_gap_detection (list)
6. **PII Detection**: Date of birth information if present

---

## OUTPUT FORMAT

Return ONLY valid JSON with this structure (no markdown, no extra text):

{{
  "domain_specific_data": {{
    "...": "... [include all fields from domain-specific extraction]"
  }},
  "general_metrics": {{
    "section_1_name_extraction": {{
      "agent_name": string,
      "customer_name": string
    }},
    "section_2_call_direction_interaction_type": {{
      "call_direction": string,
      "interaction_type": string
    }},
    "section_3_sentiment_and_intent_detection": {{
      "sentiment": string,
      "intent": string
    }},
    "section_4_summary_of_conversation_in_brief": string,
    "section_5_agent_improvement_metrics": {{
      "empathy_score": number,
      "professionalism_score": number,
      "knowledge_gap_detection": [string]
    }},
    "section_6_pci_pii_data_detection": [string]
  }}
}}

---

Transcript to analyze:
{transcription}
"""

        response = model.generate_content(combined_prompt)
        
        token_input = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        token_output = response.usage_metadata.candidates_token_count if response.usage_metadata else 0

        cleaned_response = response.text.replace("```json", "").replace("```", "").strip()
        combined_data = json.loads(cleaned_response)

        return {
            "domain_specific_data": combined_data.get("domain_specific_data", {}),
            "general_metrics": combined_data.get("general_metrics", {}),
            "tokens_combined": [token_input, token_output]
        }
    
    except Exception as e:
        print(f"❌ Extraction Error: {e}")
        return {
            "domain_specific_data": {},
            "general_metrics": {},
            "tokens_combined": [0, 0],
            "error": str(e)
        }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "extraction-service"}


if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Starting Extraction Service on port {EXTRACTION_SERVICE_PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=EXTRACTION_SERVICE_PORT)
