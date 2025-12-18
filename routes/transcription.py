"""
Routes - API Endpoints
"""
import json
from fastapi import UploadFile, File, APIRouter
from fastapi.responses import JSONResponse
from utils.constants import MIME_TYPE_MAPPING
from controller.transcription_pipeline import transcribe_and_detect_domain
from controller.extraction_pipeline import extract_all_data
from services.prompt_service import validate_and_generate_prompt
from services.supabase_service import save_call_to_general_table, save_domain_specific_data
from controller.tonal_analysis import analyze_tonal

router = APIRouter()


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


def extract_general_metrics(general_metrics: dict) -> dict:
    """
    Extract and flatten general metrics from nested structure.
    
    Args:
        general_metrics: Nested general metrics dictionary
        
    Returns:
        Flattened dictionary with extracted values
    """
    sec1 = general_metrics.get("section_1_name_extraction", {})
    sec2 = general_metrics.get("section_2_call_direction_interaction_type", {})
    sec3 = general_metrics.get("section_3_sentiment_and_intent_detection", {})

    return {
        "agent_name": sec1.get("agent_name", "Not Available"),
        "customer_name": sec1.get("customer_name", "Not Available"),
        "call_direction": sec2.get("call_direction", "Not Available"),
        "interaction_type": sec2.get("interaction_type", "Not Available"),
        "sentiment": sec3.get("sentiment", "Not Available"),
        "intent": sec3.get("intent", "Not Available"),
    }


@router.post("/transcribe/")
async def transcribe_endpoint(file: UploadFile = File(...)):
    """
    Multi-stage audio transcription and analysis endpoint.
    
    Pipeline:
    - Stage 1: Transcription + Domain/Category Detection
    - Validation: Check domain/category and generate prompt if needed
    - Stage 2: Combined Domain-Specific + General Analysis
    - Database: Save results to Supabase
    
    Args:
        file: Audio file to process
        
    Returns:
        JSON response with transcription, analysis results, and token usage
    """
    print(f"📂 Received file: {file.filename} | Type: {file.content_type}")

    
    
    # Normalize mime type
    mime_type = normalize_mime_type(file)
    
    # Read file
    file_bytes = await file.read()

    tonal_res= await analyze_tonal(file_bytes,mime_type,file.filename)

    # ============ STAGE 1: Transcription + Domain/Category Detection ============
    print("🎙️  Stage 1: Transcribing and detecting domain/category...")
    stage1_result = await transcribe_and_detect_domain(file_bytes, mime_type)
    
    transcription = stage1_result.get("transcription", "")
    domain = stage1_result.get("domain", "unknown")
    category = stage1_result.get("category", "unknown")
    tokens_stage1 = stage1_result.get("tokens_stage1", [0, 0])

    print(f"✅ Domain: {domain} | Category: {category}")

    # ============ VALIDATION: Check domain/category and generate prompt if needed ============
    print("🔍 Validating domain/category combination...")
    custom_prompt = await validate_and_generate_prompt(domain, category)

    if custom_prompt:
        print(f"✅ Generated custom prompt")
    else:
        print("✅ Using Supabase prompt for extraction")

    # ============ STAGE 2: Combined Extraction (Domain-specific + General Analysis) ============
    print("🔍 Stage 2: Extracting domain-specific data and general metrics...")
    
    combined_result = await extract_all_data(transcription, domain, category, custom_prompt)

    domain_specific_data = combined_result.get("domain_specific_data", {})
    general_metrics = combined_result.get("general_metrics", {})
    tokens_combined = combined_result.get("tokens_combined", [0, 0])

    # ============ Extract and prepare data for database ============
    extracted_metrics = extract_general_metrics(general_metrics)
    
    # Calculate total tokens
    total_tokens_input = tokens_stage1[0] + tokens_combined[0]
    total_tokens_output = tokens_stage1[1] + tokens_combined[1]
    total_tokens = total_tokens_input + total_tokens_output

    # ============ Save to database ============
    data_to_general = {
        "file_name": file.filename,
        "domain": domain,
        "category": category,
        "agent_name": extracted_metrics["agent_name"],
        "customer_name": extracted_metrics["customer_name"],
        "call_direction": extracted_metrics["call_direction"],
        "interaction_type": extracted_metrics["interaction_type"],
        "sentiment": extracted_metrics["sentiment"],
        "intent": extracted_metrics["intent"],
        "tokens_input": total_tokens_input,
        "tokens_output": total_tokens_output,
        "total_tokens": total_tokens,
    }

    # Save to general table and get call_id
    call_id = save_call_to_general_table(data_to_general)

    # Save domain-specific data with call_id
    if call_id:
        domain_specific_text = json.dumps(domain_specific_data, indent=2)
        data_to_domain_specific = {"data": domain_specific_text}
        save_domain_specific_data(call_id, data_to_domain_specific)

    # ============ Return response ============
    return JSONResponse(content={
        "filename": file.filename,
        "tonal_analysis": tonal_res,
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
            "stage2_combined_analysis": {
                "input": tokens_combined[0],
                "output": tokens_combined[1],
                "total": sum(tokens_combined)
            },
            "total": {
                "input": total_tokens_input,
                "output": total_tokens_output,
                "total": total_tokens
            }
        }
    })
