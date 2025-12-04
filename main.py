import os
import base64
import typing
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from dotenv import load_dotenv
import json
import supabase
from supabase import create_client, Client

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=API_KEY)

# Initialize FastAPI
app = FastAPI(title="Gemini Audio Transcriber")

# Add CORS (useful if you call this from a different frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase Client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ==================== STEP 1: TRANSCRIPTION + DOMAIN/CATEGORY DETECTION ====================

async def transcribe_and_detect_domain(file_bytes: bytes, mime_type: str) -> dict:
    """
    First call: Transcribe audio + detect domain and category
    """
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")

        detection_prompt = """
You are an expert call classifier and transcription specialist.

## TASK 1: TRANSCRIPTION
Transcribe the provided audio file accurately with timestamps and speaker labels.

Output format:
[HH:MM - HH:MM] Speaker: Text here

---

## TASK 2: DOMAIN AND CATEGORY DETECTION

After transcribing, identify:
1. **Domain**: The industry/business domain (healthcare, insurance,other)
2. **Category**: The specific category within that domain (
for healthcare: appointment_scheduling, billing_inquiry, prescription_refill
for insurance: claim_inquiry, policy_inquiry, premium_payment
)

Be precise in categorization. Use snake_case for both domain and category.

---

## OUTPUT FORMAT

Return ONLY valid JSON:

{
  "transcription": "Full transcript with timestamps here...",
  "domain": string,
  "category": string
}
"""

        response = model.generate_content([
            detection_prompt,
            {
                "mime_type": mime_type,
                "data": file_bytes
            }
        ])

        token1_input = 0
        token1_output = 0
        if response.usage_metadata:
            token1_input = response.usage_metadata.prompt_token_count
            token1_output = response.usage_metadata.candidates_token_count

        cleaned_response = response.text.replace("```json", "").replace("```", "").strip()
        parsed_response = json.loads(cleaned_response)

        return {
            "transcription": parsed_response.get("transcription", ""),
            "domain": parsed_response.get("domain", "unknown"),
            "category": parsed_response.get("category", "unknown"),
            "tokens_stage1": [token1_input, token1_output]
        }
    except Exception as e:
        print(f"Gemini Error (Stage 1): {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


# ==================== STEP 2: DOMAIN-SPECIFIC DATA EXTRACTION ====================

async def extract_domain_specific_data(transcription: str, domain: str, category: str) -> dict:
    """
    Second call: Extract domain-specific data using specialized prompt
    """
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")

        # Fetch the prompt from Supabase based on domain and category
        try:
            prompt_response = supabase.table("prompts").select("*").eq("domain", domain).eq("category", category).execute()
            
            if prompt_response.data and len(prompt_response.data) > 0:
                extraction_prompt_template = prompt_response.data[0].get("prompt", "")
            else:
                # Fallback if not found in Supabase
                extraction_prompt_template = f"""
Extract all relevant information from the following transcript for a {domain} call with {category} category.
Focus on capturing dates, names, numbers, and key decisions made during the call.
Return all extracted data as JSON.
"""
        except Exception as e:
            print(f"⚠️  Error fetching prompt from Supabase: {e}")
            
            if not extraction_prompt_template:
                extraction_prompt_template = f"""
Extract all relevant information from the following transcript for a {domain} call with {category} category.
Focus on capturing dates, names, numbers, and key decisions made during the call.
Return all extracted data as JSON.
"""
        #print(extraction_prompt_template)

        extraction_prompt = f"""
{extraction_prompt_template}

---

Transcript to analyze:
{transcription}

"""
        #print(transcription)

        response = model.generate_content(extraction_prompt)

        token2_input = 0
        token2_output = 0
        if response.usage_metadata:
            token2_input = response.usage_metadata.prompt_token_count
            token2_output = response.usage_metadata.candidates_token_count

        cleaned_response = response.text.replace("```json", "").replace("```", "").strip()
        domain_data = json.loads(cleaned_response)

        return {
            "domain_specific_data": domain_data,
            "tokens_stage2": [token2_input, token2_output]
        }
    except Exception as e:
        print(f"Gemini Error (Stage 2): {e}")
        return {
            "domain_specific_data": {},
            "tokens_stage2": [0, 0],
            "error": str(e)
        }


# ==================== STEP 3: GENERAL CALL ANALYSIS ====================

async def analyze_call_general(transcription: str, domain: str, category: str) -> dict:
    """
    Third call: General call analysis (metrics, sentiment, PII detection, etc.)
    Can be parallelized with extract_domain_specific_data if needed
    """
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")

        general_analysis_prompt = f"""
You are analyzing a {domain} call ({category} category).

Analyze the provided transcript and extract:

1. **Names**: agent_name, customer_name
2. **Call Metadata**: call_direction (Inbound/Outbound), interaction_type (Conversation/Voicemail)
3. **Sentiment & Intent**: sentiment (Positive/Neutral/Negative), intent (3-5 word summary)
4. **Summary**: Brief summary of the conversation
5. **Agent Metrics**: empathy_score (0-10), professionalism_score (0-10), knowledge_gap_detection (list)->return any topics where agent showed lack of knowledge or any feedback for improvement
6. **PII Detection**: Date of birth information if present

Transcript:
{transcription}

Return ONLY this JSON structure:
{{
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
"""

        response = model.generate_content(general_analysis_prompt)

        token3_input = 0
        token3_output = 0
        if response.usage_metadata:
            token3_input = response.usage_metadata.prompt_token_count
            token3_output = response.usage_metadata.candidates_token_count

        cleaned_response = response.text.replace("```json", "").replace("```", "").strip()
        general_metrics = json.loads(cleaned_response)

        return {
            "general_metrics": general_metrics,
            "tokens_stage3": [token3_input, token3_output]
        }
    except Exception as e:
        print(f"Gemini Error (Stage 3): {e}")
        return {
            "general_metrics": {},
            "tokens_stage3": [0, 0],
            "error": str(e)
        }


# ==================== API ENDPOINT ====================

@app.post("/transcribe/")
async def transcribe_endpoint(file: UploadFile = File(...)):
    """
    Multi-stage audio transcription and analysis:
    Stage 1: Transcription + Domain/Category Detection
    Stage 2: Domain-specific Data Extraction
    Stage 3: General Call Analysis (Sentiment, Metrics, PII)
    """
    
    print(f"📂 Received file: {file.filename} | Type: {file.content_type}")
    
    # Normalize mime type
    mime_type = file.content_type
    if mime_type == "application/octet-stream":
        ext = file.filename.split(".")[-1].lower()
        if ext == "mp3": mime_type = "audio/mpeg"
        elif ext == "wav": mime_type = "audio/wav"
        elif ext == "m4a": mime_type = "audio/mp4"
    
    # Read file
    file_bytes = await file.read()

    # ============ STAGE 1: Transcription + Domain/Category Detection ============
    print("🎙️  Stage 1: Transcribing and detecting domain/category...")
    stage1_result = await transcribe_and_detect_domain(file_bytes, mime_type)
    
    transcription = stage1_result.get("transcription", "")
    domain = stage1_result.get("domain", "unknown")
    category = stage1_result.get("category", "unknown")
    tokens_stage1 = stage1_result.get("tokens_stage1", [0, 0])

    print(f"✅ Domain: {domain} | Category: {category}")

    # ============ STAGE 2 & 3: Parallel execution (Domain-specific + General Analysis) ============
    print("🔍 Stage 2 & 3: Extracting domain-specific data and general metrics (parallel)...")
    
    import asyncio
    stage2_result, stage3_result = await asyncio.gather(
        extract_domain_specific_data(transcription, domain, category),
        analyze_call_general(transcription, domain, category)
    )

    domain_specific_data = stage2_result.get("domain_specific_data", {})
    tokens_stage2 = stage2_result.get("tokens_stage2", [0, 0])

    general_metrics = stage3_result.get("general_metrics", {})
    tokens_stage3 = stage3_result.get("tokens_stage3", [0, 0])

    # ============ Extract values for database ============
    sec1 = general_metrics.get("section_1_name_extraction", {})
    sec2 = general_metrics.get("section_2_call_direction_interaction_type", {})
    sec3 = general_metrics.get("section_3_sentiment_and_intent_detection", {})

    agent_name = sec1.get("agent_name", "Not Available")
    customer_name = sec1.get("customer_name", "Not Available")
    call_direction = sec2.get("call_direction", "Not Available")
    interaction_type = sec2.get("interaction_type", "Not Available")
    sentiment = sec3.get("sentiment", "Not Available")
    intent = sec3.get("intent", "Not Available")

    # Calculate total tokens
    total_tokens_input = tokens_stage1[0] + tokens_stage2[0] + tokens_stage3[0]
    total_tokens_output = tokens_stage1[1] + tokens_stage2[1] + tokens_stage3[1]
    total_tokens = total_tokens_input + total_tokens_output

    # ============ Save to database ============
    # Convert domain-specific data from JSON to text
    domain_specific_text = json.dumps(domain_specific_data, indent=2)
    
    data_to_db = {
        "file_name": file.filename,
        "domain": domain,
        "category": category,
        "agent_name": agent_name,
        "customer_name": customer_name,
        "call_direction": call_direction,
        "interaction_type": interaction_type,
        "sentiment": sentiment,
        "intent": intent,
        "tokens_input": total_tokens_input,
        "tokens_output": total_tokens_output,
        "total_tokens": total_tokens,
    }

    data_to_db2={
        "data": domain_specific_text,
    }

    try:
        # Insert into general table and capture the response
        general_response = supabase.table("general").insert(data_to_db).execute()
        print(f"✅ Data saved to general table | Total Tokens Used: {total_tokens}")
        
        # Extract the ID from the response
        if general_response.data and len(general_response.data) > 0:
            call_id = general_response.data[0].get("id")
            
            # Add call_id to domain_specific data
            data_to_db2["call_id"] = call_id
            
            try:
                supabase.table("domain_specific").insert(data_to_db2).execute()
                print(f"✅ Domain-specific data saved to DB with call_id: {call_id}")
            except Exception as e2:
                print(f"⚠️  Domain-Specific DB Insertion Error: {e2}")
        else:
            print("⚠️  No ID returned from general table insert")
    except Exception as e:
        print(f"⚠️  DB Insertion Error: {e}")

    # ============ Return response ============
    return JSONResponse(content={
        "filename": file.filename,
        "transcription": transcription,
        "domain": domain,
        "category": category,
        "domain_specific_data": domain_specific_data,
        "general_metrics": general_metrics,
        "token_usage": {
            "stage1_transcription_and_detection": {
                "input": tokens_stage1[0],
                "output": tokens_stage1[1],
                "total": sum(tokens_stage1)
            },
            "stage2_domain_specific_extraction": {
                "input": tokens_stage2[0],
                "output": tokens_stage2[1],
                "total": sum(tokens_stage2)
            },
            "stage3_general_analysis": {
                "input": tokens_stage3[0],
                "output": tokens_stage3[1],
                "total": sum(tokens_stage3)
            },
            "total": {
                "input": total_tokens_input,
                "output": total_tokens_output,
                "total": total_tokens
            }
        }
    })
