"""
Gemini Service - All LLM interactions
"""
import google.generativeai as genai
from config import GEMINI_API_KEY, LLM_MODEL

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(LLM_MODEL)


def generate_content(prompt: str, file_data: dict = None) -> dict:
    """
    Generate content using Gemini API.
    
    Args:
        prompt: The prompt text
        file_data: Optional dictionary with mime_type and data for audio files
        
    Returns:
        Dictionary with generated text and token usage
    """
    try:
        content_parts = [prompt]
        if file_data:
            content_parts.append(file_data)
        
        response = model.generate_content(content_parts)
        
        token_input = 0
        token_output = 0
        if response.usage_metadata:
            token_input = response.usage_metadata.prompt_token_count
            token_output = response.usage_metadata.candidates_token_count
        
        return {
            "text": response.text,
            "input_tokens": token_input,
            "output_tokens": token_output,
            "total_tokens": token_input + token_output
        }
    except Exception as e:
        print(f"❌ Gemini Error: {e}")
        raise


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
        
        response = generate_content(generation_prompt)
        generated_prompt = response["text"].strip()
        print(f"✅ Generated custom prompt for {domain}/{category}")
        return generated_prompt
    
    except Exception as e:
        print(f"⚠️  Error generating prompt: {e}")
        return f"Extract all relevant information from this {domain} call with {category} category. Return as JSON."
