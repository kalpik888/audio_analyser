"""
Transcription Pipeline - Stage 1
Transcribe audio and detect domain/category
"""
import json
from fastapi import HTTPException
from services.gemini_service import generate_content
from services.domain_service import get_domains_categories_text, add_discovered_domain_category


async def transcribe_and_detect_domain(file_bytes: bytes, mime_type: str) -> dict:
    """
    Stage 1: Transcribe audio file and detect business domain and category.
    
    Args:
        file_bytes: Binary audio file data
        mime_type: MIME type of the audio file
        
    Returns:
        Dictionary with transcription, domain, category, and token usage
        
    Raises:
        HTTPException: If transcription fails
    """
    try:
        # Build dynamic domain-category list
        domains_categories_text = get_domains_categories_text()

        detection_prompt = f"""
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
{domains_categories_text}

if domain or category is not from the given list, identify it accordingly.

Be precise in categorization. Use snake_case for both domain and category.

---

## OUTPUT FORMAT

Return ONLY valid JSON:

{{
  "transcription": "Full transcript with timestamps here...",
  "domain": string,
  "category": string
}}
"""

        response = generate_content(detection_prompt, {
            "mime_type": mime_type,
            "data": file_bytes
        })

        cleaned_response = response["text"].replace("```json", "").replace("```", "").strip()
        parsed_response = json.loads(cleaned_response)

        domain = parsed_response.get("domain", "unknown")
        category = parsed_response.get("category", "unknown")
        
        # Add to tracking structure if new
        add_discovered_domain_category(domain, category)

        return {
            "transcription": parsed_response.get("transcription", ""),
            "domain": domain,
            "category": category,
            "tokens_stage1": [response["input_tokens"], response["output_tokens"]]
        }
    except Exception as e:
        print(f"❌ Transcription Error (Stage 1): {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
