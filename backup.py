#its just the backup of main.py file
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

# --- HELPER FUNCTION: Transcribe with Gemini ---
async def transcribe_audio(file_bytes: bytes, mime_type: str) -> str:
    try:
        # Gemini expects 'inlineData' for smaller files (under 20MB)
        # For larger files, you'd use the File API (genai.upload_file)
        
        model = genai.GenerativeModel("gemini-2.0-flash")

        # Custom Prompt for better accuracy
        prompt = """
You are an expert transcription and call analysis assistant.

Your task is to transcribe the provided audio file accurately, including:

1. All spoken words, exactly as heard (with speaker labels if possible, e.g., Agent, Caller).
2. Every section of music hold or silence longer than 3 seconds, labeled as:
   [HOLD MUSIC - duration: X seconds]
3. Duration Calculation: When calculating the duration for hold music or silence, the time must be the **difference between the start and end timestamps**. **DO NOT** output durations that exceed the total length of the audio file.
4. Provide timestamps for each major section or speaker change.
5. Ensure formatting is clean and chronological.

Output format example:

[00:00 - 00:12] Agent: Thank you for calling Azul Vision How can I help you today?  
[00:12 - 02:45] [HOLD MUSIC - duration: 2 minutes 33 seconds]  
[02:45 - 02:49] Agent: Thank you for holding. Are you still there?  
[02:49 - 03:02] Caller: Yes, I’m here.  
        """

        response = model.generate_content([
            prompt,
            {
                "mime_type": mime_type,
                "data": file_bytes
            }
        ])

    #     try:
    # # 3. Parse string -> Dictionary
    #         data = json.loads(response.text)

    #         # 4. Access the keys correctly
    #         file_name = data["filename"]
            
    #         # Note: Your JSON key is "transcription", not "transcript"
    #         transcript = data["transcription"] 

    #         print(f"File: {file_name}")
    #         print(f"Transcript Length: {len(transcript)}")

    #     except json.JSONDecodeError as e:
    #         print(f"Failed to parse JSON: {e}")

        token1_input=0
        token1_output=0
        if response.usage_metadata:
            token1_input = response.usage_metadata.prompt_token_count
            token1_output = response.usage_metadata.candidates_token_count

        prompt_2 = """
You are analyzing a call center conversation.
Calls may involve customers, agents, or internal staff.

Your task is to:
1. Extract the **agentName** and **customer_name**.
2. Identify **call_direction** and **interaction_type**. 
3. Analyze the overall **sentiment** of the call.
4. Summarize the primary **intent** of the call in 3-5 words.
5. summarize the overall conversation in brief.
6. agent improvement metrics.
7. pci/pii data detection.

Return only valid JSON strictly matching the schema below. No comments, no explanations.

---

## 🔹 Section 1 — Name Extraction
- **agent_name**: Organization representative or agent (e.g., “I’m Sarah from Azul Vision”). If agent_name is not available, return "Not Available".  
- **customer_name**: Patient/member discussed; if missing, check for caller name or representative. If both are missing, return "Not Available".

---

## 🔹 Section 2 — Call Direction & Interaction Type
- **call_direction**: "Inbound" | "Outbound"  
- **interaction_type**: "Conversation" | "Voicemail left by member" | "Voicemail left by agent"

---

### 🔹 Section 3 - sentiment and intent ditection
- **sentiment**: "Positive" | "Neutral" | "Negative"
- **intent**: Briefly summarize the primary intent of the call in 3-5 words.

---

### 🔹 Section 4 - summary of conversation in brief.

---

### 🔹 Section 5 - agent improvement metrics
Analyze the agent’s behavior and communication quality. Provide: 
- empathy_score (0 to 10): Did the agent acknowledge the customer’s emotions? 
- professionalism_score (0 to 10): Politeness, respectful language, positive tone. 
- knowledge_gap_detection: List specific instances where the agent was unsure, gave incomplete/incorrect information, or displayed low product/process knowledge. 

---

### 🔹 Section 6 - PCI/PII data detection
-return a list
Identify any PCI or PII data present in the transcript.  

Include only date of birth

---

Return the response in the following JSON format:{
  "section_1_name_extraction": {
    "agent_name": string,
    "customer_name": string
  },
    "section_2_call_direction_interaction_type": {
    "call_direction": string,
    "interaction_type": string
    },
    "section_3_sentiment_and_intent_detection": {
    "sentiment": string,
    "intent": string
    },
    "section_4_summary_of_conversation_in_brief": string,
    "section_5_agent_improvement_metrics": {
    "empathy_score": number,
    "professionalism_score": number,
    "knowledge_gap_detection": [string]
    },
    "section_6_pci_pii_data_detection": [string]
    
}

"""
        response2 = model.generate_content([
            prompt_2,
            response.text
        ])
        
        token2_input=0
        token2_output=0
        if response2.usage_metadata:
            token2_input = response2.usage_metadata.prompt_token_count
            token2_output = response2.usage_metadata.candidates_token_count

        cleaned_response2 = response2.text.replace("```json", "").replace("```", "").strip()
        #print(cleaned_response2)
        combine_data={
            "transcription": response.text,
            "metrics": json.loads(cleaned_response2),
            "tokens": [token1_input,token1_output,token2_input,token2_output]
        }

        #print(combine_data["tokens"])

        return combine_data
    except Exception as e:
        print(f"Gemini Error: {e}")
        raise HTTPException(status_code=500, detail=f"AI Transcription failed: {str(e)}")
    

@app.post("/transcribe/")
async def transcribe_endpoint(file: UploadFile = File(...)):
    """
    API Endpoint that accepts an audio file and returns JSON transcription.
    """
    
    # 1. Validate Content Type
    # Gemini supports: wav, mp3, aiff, aac, ogg, flac
    supported_types = ["audio/wav", "audio/mp3", "audio/mpeg", "audio/x-m4a", "audio/ogg", "audio/flac"]
    
    print(f"📂 Received file: {file.filename} | Type: {file.content_type}")
    
    # Basic mime type normalization (browsers send different things)
    mime_type = file.content_type
    if mime_type == "application/octet-stream":
        # Fallback based on extension if header is generic
        ext = file.filename.split(".")[-1].lower()
        if ext == "mp3": mime_type = "audio/mpeg"
        elif ext == "wav": mime_type = "audio/wav"
        elif ext == "m4a": mime_type = "audio/mp4"
    
    # 2. Read file into memory (Note: For massive files > 20MB, consider saving to disk first)
    file_bytes = await file.read()

    # 3. Call Gemini
    transcription = await transcribe_audio(file_bytes, mime_type)

    metrics= transcription.get("metrics")
    token_list = transcription.get("tokens") or [0,0,0,0]
    total_tokens= sum(token_list)
    metrics_str = json.dumps(metrics, indent=2)
    try:

        metrics_json = json.loads(metrics_str)
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        metrics_json = {}

    #print(metrics_json)
    sec1=metrics_json.get("section_1_name_extraction") or  {}
    sec2=metrics_json.get("section_2_call_direction_interaction_type") or {}
    sec3=metrics_json.get("section_3_sentiment_and_intent_detection") or {}
    sec4=metrics_json.get("section_4_summary_of_conversation_in_brief") or {}
    sec5=metrics_json.get("section_5_agent_improvement_metrics") or {}
    sec6=metrics_json.get("section_6_pci_pii_data_detection") or {}



    #now save the metrics into db

    agent_name = sec1.get("agent_name", "Not Available")
    customer_name = sec1.get("customer_name", "Not Available")
    call_direction = sec2.get("call_direction", "Not Available")
    interaction_type = sec2.get("interaction_type", "Not Available")
    sentiment = sec3.get("sentiment", "Not Available")
    intent = sec3.get("intent", "Not Available")

    if sec1.get("agent_name") is None:
        agent_name = metrics_json.get("agent_name", "Not Available")
    if sec1.get("customer_name") is None:
        customer_name = metrics_json.get("customer_name", "Not Available")
    if sec2.get("call_direction") is None:
        call_direction = metrics_json.get("call_direction", "Not Available")
    if sec2.get("interaction_type") is None:
        interaction_type = metrics_json.get("interaction_type", "Not Available")
    if sec3.get("sentiment") is None:
        sentiment = metrics_json.get("sentiment", "Not Available")
    if sec3.get("intent") is None:
        intent = metrics_json.get("intent", "Not Available")

    data_to_db = {
        "file_name": file.filename,
        "agent_name": agent_name,
        "customer_name": customer_name,
        "call_direction": call_direction,
        "interaction_type": interaction_type,
        "sentiment": sentiment,
        "intent": intent,
        "tokens_input_transcript": token_list[0],
        "tokens_output_transcript": token_list[1],
        "tokens_input_analysis": token_list[2],
        "tokens_output_analysis": token_list[3],
    }

    try:
        supabase.table("general").insert(data_to_db).execute()
    except Exception as e:
        print(f"DB Insertion Error: {e}")


    #print(sec5["knowledge_gap_detection"])

    return JSONResponse(content={
        "filename": file.filename,
        "transcription": transcription.get("transcription"),
        "metrics": transcription.get("metrics"),
        "tokens": transcription.get("tokens")
    })