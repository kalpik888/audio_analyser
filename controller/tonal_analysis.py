import json
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from fastapi import UploadFile, File
from supabase import Client, create_client
from fastapi import UploadFile, File

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY,GEMINI_API_KEY, LLM_MODEL

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(LLM_MODEL)




MIME_TYPE_MAPPING = {
    "application/octet-stream": {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "m4a": "audio/mp4",
    }
}

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


async def analyze_tonal(file_bytes,mime_type: str,file_name:str):
    """
    listen to the audio file and provide a detailed analysis of the tone and sentiment of the speakers in the call.
    """
    try:

        tonal_prompt = """
You are an expert tonal and sentiment analysis specialist.
Listen to the provided audio file and give a detailed analysis of the tone and sentiment of the speakers in the call.
Provide insights on emotions, attitudes, and overall mood conveyed by the speakers.
also provide timestamps for key tonal shifts.

You must return the analysis strictly in the following JSON format:

{
  "overall_analysis": {
    "summary": "A brief paragraph summarizing the call context and outcome.",
    "overall_sentiment": "Positive | Neutral | Negative | Mixed",
    "overall_tone": "e.g., Professional, Polite, Urgent"
  },

  "key_tonal_shifts": [
    {
      "timestamp": "MM:SS",
      "trigger_event": "The specific topic or reason causing the shift (e.g., Policy Announcement)",
      "description": "Description of how the tone changed."
    }
  ]
}
"""
        

        response = model.generate_content([tonal_prompt, {
            "mime_type": mime_type,
            "data": file_bytes
        }])

        token_input = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        token_output = response.usage_metadata.candidates_token_count if response.usage_metadata else 0

        cleaned_response = response.text.replace("```json", "").replace("```", "").strip()
        parsed_response = json.loads(cleaned_response)

        data_to_db={
            "data":parsed_response,
            "file_name": file_name,
            "input_token": token_input,
            "output_token": token_output
        }

        supabase.table("tonal_analysis").insert(data_to_db).execute()

        return {
            "file_name": file_name,
            "tonal_sentiment_analysis": parsed_response,
            "tokens_usage": {
                "input_tokens": token_input,
                "output_tokens": token_output
            }
        }
    except Exception as e:
        return {"error": str(e)}
    
