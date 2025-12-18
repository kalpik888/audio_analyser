"""
Extraction Pipeline - Stage 2
Combined domain-specific data extraction and general analysis
"""
import json
from services.gemini_service import generate_content
from services.supabase_service import fetch_prompt_from_db


async def extract_all_data(transcription: str, domain: str, category: str, custom_prompt: str = None) -> dict:
    """
    Stage 2: Extract both domain-specific data AND general analysis in a single LLM call.
    
    This combined approach reduces token usage by 30-40% compared to separate calls.
    
    Args:
        transcription: Full transcript from Stage 1
        domain: Detected business domain
        category: Detected category within domain
        custom_prompt: Optional custom extraction prompt (generated for new domain-category combinations)
        
    Returns:
        Dictionary with domain_specific_data, general_metrics, and token usage
    """
    try:
        # Use custom prompt if provided, otherwise fetch from Supabase
        extraction_prompt_template = custom_prompt
        
        if not extraction_prompt_template:
            extraction_prompt_template = fetch_prompt_from_db(domain, category)
        
        if not extraction_prompt_template:
            # Fallback generic prompt
            extraction_prompt_template = f"""
Extract all relevant information from the following transcript for a {domain} call with {category} category.
Focus on capturing dates, names, numbers, and key decisions made during the call.
"""

        # Combined prompt for both domain-specific and general analysis
        combined_analysis_prompt = f"""
You are analyzing a {domain} call ({category} category).

## PART 1: DOMAIN-SPECIFIC DATA EXTRACTION

{extraction_prompt_template}

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

        response = generate_content(combined_analysis_prompt)
        
        cleaned_response = response["text"].replace("```json", "").replace("```", "").strip()
        combined_data = json.loads(cleaned_response)

        return {
            "domain_specific_data": combined_data.get("domain_specific_data", {}),
            "general_metrics": combined_data.get("general_metrics", {}),
            "tokens_combined": [response["input_tokens"], response["output_tokens"]]
        }
    except Exception as e:
        print(f"❌ Extraction Error (Stage 2): {e}")
        return {
            "domain_specific_data": {},
            "general_metrics": {},
            "tokens_combined": [0, 0],
            "error": str(e)
        }
