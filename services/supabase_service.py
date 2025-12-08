"""
Supabase Service - All database operations
"""
import json
from supabase import Client, create_client
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

# Initialize Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def fetch_prompt_from_db(domain: str, category: str) -> str:
    """
    Fetch extraction prompt from Supabase for a given domain-category combination.
    
    Args:
        domain: Business domain
        category: Category within domain
        
    Returns:
        Prompt string or None if not found
    """
    try:
        response = supabase.table("prompts").select("*").eq("domain", domain).eq("category", category).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0].get("prompt", "")
    except Exception as e:
        print(f"⚠️  Error fetching prompt from Supabase: {e}")
    
    return None


async def save_new_prompt_to_db(domain: str, category: str, prompt: str) -> bool:
    """
    Save newly generated prompt to the prompts table in Supabase.
    
    Args:
        domain: Business domain
        category: Category within domain
        prompt: The extraction prompt text
        
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        # Check if this domain-category combination already exists
        existing = supabase.table("prompts").select("*").eq("domain", domain).eq("category", category).execute()
        
        if not existing.data or len(existing.data) == 0:
            # Insert new prompt record
            supabase.table("prompts").insert({
                "domain": domain,
                "category": category,
                "prompt": prompt
            }).execute()
            print(f"✅ Saved new prompt to database: {domain}/{category}")
            return True
        else:
            print(f"ℹ️  Prompt already exists in database for {domain}/{category}")
            return False
    except Exception as e:
        print(f"⚠️  Error saving prompt to database: {e}")
        return False


def save_call_to_general_table(data: dict) -> int | None:
    """
    Save call metadata to general table.
    
    Args:
        data: Dictionary containing call metadata
        
    Returns:
        call_id if successful, None otherwise
    """
    try:
        response = supabase.table("general").insert(data).execute()
        print(f"✅ Data saved to general table")
        
        if response.data and len(response.data) > 0:
            return response.data[0].get("id")
    except Exception as e:
        print(f"⚠️  DB Insertion Error (general table): {e}")
    
    return None


def save_domain_specific_data(call_id: int, data: dict) -> bool:
    """
    Save domain-specific extracted data to domain_specific table.
    
    Args:
        call_id: Foreign key reference to general table
        data: Dictionary containing domain-specific data
        
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        data["call_id"] = call_id
        supabase.table("domain_specific").insert(data).execute()
        print(f"✅ Domain-specific data saved to DB with call_id: {call_id}")
        return True
    except Exception as e:
        print(f"⚠️  Domain-Specific DB Insertion Error: {e}")
        return False


def fetch_example_prompts(prompt_ids: list[int]) -> dict:
    """
    Fetch example prompts from Supabase by IDs.
    
    Args:
        prompt_ids: List of prompt IDs to fetch
        
    Returns:
        Dictionary mapping ID to prompt text
    """
    example_prompts = {}
    try:
        for prompt_id in prompt_ids:
            response = supabase.table("prompts").select("prompt").eq("id", prompt_id).execute()
            if response.data and len(response.data) > 0:
                example_prompts[prompt_id] = response.data[0].get("prompt", "")
    except Exception as e:
        print(f"⚠️  Error fetching example prompts: {e}")
    
    return example_prompts


def load_all_domain_categories() -> dict:
    """
    Load all discovered domains and categories from the prompts table.
    
    Returns:
        Dictionary with domain as key and list of categories as value
    """
    domains_categories = {}
    try:
        response = supabase.table("prompts").select("domain, category").execute()
        
        if response.data and len(response.data) > 0:
            for record in response.data:
                domain = record.get("domain")
                category = record.get("category")
                
                if domain and category:
                    if domain not in domains_categories:
                        domains_categories[domain] = []
                    
                    if category not in domains_categories[domain]:
                        domains_categories[domain].append(category)
            
            print(f"✅ Loaded {len(domains_categories)} domains from prompts table")
    except Exception as e:
        print(f"⚠️  Error loading domains from prompts table: {e}")
    
    return domains_categories
