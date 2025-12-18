import uuid
import os
import time
import shutil
import google.generativeai as genai
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from pathlib import Path
from dotenv import load_dotenv
import json

app = FastAPI()

env_path = Path(__file__).resolve().parent.parent / ".env"

load_dotenv(dotenv_path=env_path)

# --- CONFIGURATION ---
# Replace with your actual key or use os.getenv("GEMINI_API_KEY")
API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

# Global Job Store (In production, use a Database)
jobs = {}

def process_with_gemini(job_id: str, local_file_path: str, mime_type: str):
    """
    Background task that handles the full Gemini lifecycle:
    Upload -> Wait for Processing -> Transcribe -> Cleanup
    """
    try:
        print(f"[{job_id}] Uploading to Gemini...")
        
        # 1. Upload file to Gemini
        # Gemini stores the file temporarily on their servers
        gemini_file = genai.upload_file(local_file_path, mime_type=mime_type)
        
        print(f"[{job_id}] Uploaded. URI: {gemini_file.uri}")

        # 2. Wait for file processing (CRITICAL STEP)
        # Large files aren't ready instantly. We must poll Google's status.
        while gemini_file.state.name == "PROCESSING":
            print(f"[{job_id}] Google is processing the audio file...")
            time.sleep(2)
            gemini_file = genai.get_file(gemini_file.name)

        if gemini_file.state.name == "FAILED":
            raise ValueError("Gemini failed to process the audio file.")

        print(f"[{job_id}] File is Active. Generative transcript...")

        # 3. Generate Transcript
        # Gemini 1.5 Flash is highly optimized for audio extraction
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(
            [gemini_file, """
You are an expert call classifier and transcription specialist.

## TASK 1: TRANSCRIPTION
Transcribe the provided audio file accurately with timestamps and speaker labels.

Output format:
[HH:MM - HH:MM] Speaker: Text here

---

## TASK 2: DOMAIN AND CATEGORY DETECTION

After transcribing, identify:
1. **Domain**: The industry/business domain
2. **Category**: The specific category within that domain

Known domain and category combinations:
"healthcare": ["appointment_scheduling", "billing_inquiry", "prescription_refill"],
"insurance": ["claim_inquiry", "policy_inquiry", "premium_payment"],

if domain or category is not from the given list, identify it accordingly.

Be precise in categorization. Use snake_case for both domain and category.

---

## OUTPUT FORMAT

You must return the analysis strictly in the following JSON format:

{
  "transcription": "Full transcript with timestamps here...",
  "domain": string,
  "category": string
}
"""],
            generation_config={"response_mime_type": "application/json"},
            request_options={"timeout": 600} # Allow 10 mins for generation
        )
        
        # 4. Save Success Result
        data = json.loads(response.text)

        # 2. (Optional) If you want the transcription text ITSELF to be one flat line 
        # (removing the newlines between speakers), run this cleanup:
        if "transcription" in data:
            # Replace \n (newline), \r (return), and \t (tab) with a single space
            clean_text = data["transcription"].replace("\n", " ").replace("\r", " ").replace("\t", " ")
            
            # Remove any double spaces caused by the cleanup
            data["transcription"] = " ".join(clean_text.split())

        # 3. Save the clean OBJECT, not the string
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = data
        
        # 5. Cleanup Remote File (Important!)
        # Google limits how many files you can have. Always delete after use.
        gemini_file.delete()
        print(f"[{job_id}] Remote file deleted.")

    except Exception as e:
        print(f"[{job_id}] Error: {e}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["result"] = str(e)

    finally:
        # 6. Cleanup Local File
        if os.path.exists(local_file_path):
            os.remove(local_file_path)
            print(f"[{job_id}] Local temp file deleted.")


@app.post("/upload-audio/")
async def upload_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    # 1. Create Job ID
    job_id = str(uuid.uuid4())
    
    # 2. Save locally first (Gemini upload needs a path, not a stream)
    # Note: Preserve extension so Gemini knows it's audio (mp3/wav)
    file_ext = os.path.splitext(file.filename)[1]
    temp_path = f"temp_{job_id}{file_ext}"
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 3. Initialize Job Status
    jobs[job_id] = {"status": "processing", "result": None}

    # 4. Start Background Task
    # Pass mime_type so Gemini knows what it is (e.g., "audio/mp3")
    background_tasks.add_task(
        process_with_gemini, 
        job_id, 
        temp_path, 
        file.content_type
    )

    return {
        "job_id": job_id, 
        "message": "File uploaded. Processing started in background."
    }


@app.get("/job-status/{job_id}")
async def get_job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return {"error": "Job not found"}
    return job