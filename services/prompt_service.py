"""
Prompt Service - Prompt validation and generation
"""
import asyncio
from services.gemini_service import generate_extraction_prompt
from services.supabase_service import save_new_prompt_to_db, fetch_example_prompts
from services.domain_service import is_valid_domain_category, add_discovered_domain_category


async def validate_and_generate_prompt(domain: str, category: str) -> str | None:
    """
    Validate if domain-category combination exists.
    If not, use LLM to generate a custom prompt.
    
    Args:
        domain: Business domain
        category: Category within domain
        
    Returns:
        Generated prompt if invalid combination, None if valid
    """
    # Check if valid combination
    if is_valid_domain_category(domain, category):
        return None
    
    # Invalid combination - generate custom prompt
    print(f"⚠️  Invalid domain-category combination. Generating custom prompt with LLM...")
    
    # Add to tracking structure
    add_discovered_domain_category(domain, category)
    
    # Fetch example prompts (IDs 1 and 2)
    example_prompts = fetch_example_prompts([1, 2])
    
    # Generate custom prompt using LLM
    generated_prompt = generate_extraction_prompt(domain, category, example_prompts)
    
    # Save to database asynchronously
    asyncio.create_task(save_new_prompt_to_db(domain, category, generated_prompt))
    
    return generated_prompt
