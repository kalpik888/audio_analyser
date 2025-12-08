"""
Domain Service - Domain and category management
"""
from config import DEFAULT_DOMAINS_CATEGORIES
from services.supabase_service import load_all_domain_categories

# Global data structure to track discovered domains and categories
VALID_DOMAINS_CATEGORIES = dict(DEFAULT_DOMAINS_CATEGORIES)


def initialize_domains_from_db():
    """
    Load domains and categories from Supabase on app startup.
    Merges with default domains.
    """
    global VALID_DOMAINS_CATEGORIES
    db_domains = load_all_domain_categories()
    
    # Merge with defaults
    for domain, categories in db_domains.items():
        if domain not in VALID_DOMAINS_CATEGORIES:
            VALID_DOMAINS_CATEGORIES[domain] = []
        
        for category in categories:
            if category not in VALID_DOMAINS_CATEGORIES[domain]:
                VALID_DOMAINS_CATEGORIES[domain].append(category)
    
    print(f"📊 Final VALID_DOMAINS_CATEGORIES: {VALID_DOMAINS_CATEGORIES}")


def get_domains_categories_text() -> str:
    """
    Convert the data structure to human-readable text for use in prompts.
    
    Returns:
        Formatted string of domains and categories
    """
    text = ""
    for domain, categories in VALID_DOMAINS_CATEGORIES.items():
        text += f"for {domain}: {', '.join(categories)}\n"
    return text


def is_valid_domain_category(domain: str, category: str) -> bool:
    """
    Check if domain-category combination is valid.
    
    Args:
        domain: Business domain
        category: Category within domain
        
    Returns:
        True if valid, False otherwise
    """
    return domain in VALID_DOMAINS_CATEGORIES and category in VALID_DOMAINS_CATEGORIES[domain]


def add_discovered_domain_category(domain: str, category: str):
    """
    Dynamically add new domain or category to the data structure if it doesn't exist.
    
    Args:
        domain: Business domain
        category: Category within domain
    """
    global VALID_DOMAINS_CATEGORIES
    
    if domain not in VALID_DOMAINS_CATEGORIES:
        print(f"✅ New domain discovered: '{domain}'. Adding to data structure...")
        VALID_DOMAINS_CATEGORIES[domain] = [category]
    elif category not in VALID_DOMAINS_CATEGORIES[domain]:
        print(f"✅ New category discovered: '{category}' for domain '{domain}'. Adding to data structure...")
        VALID_DOMAINS_CATEGORIES[domain].append(category)


def get_all_domains_categories() -> dict:
    """
    Get the current domains and categories dictionary.
    
    Returns:
        Dictionary of all domains and their categories
    """
    return VALID_DOMAINS_CATEGORIES
