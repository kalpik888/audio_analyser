"""
Constants and Enums
"""

# Mime type mappings
MIME_TYPE_MAPPING = {
    "application/octet-stream": {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "m4a": "audio/mp4",
    }
}

# Call direction values
CALL_DIRECTIONS = ["Inbound", "Outbound"]

# Sentiment values
SENTIMENTS = ["Positive", "Neutral", "Negative"]

# Interaction types
INTERACTION_TYPES = ["Conversation", "Voicemail"]

# Score ranges
SCORE_MIN = 0
SCORE_MAX = 10

# Database table names
TABLE_PROMPTS = "prompts"
TABLE_GENERAL = "general"
TABLE_DOMAIN_SPECIFIC = "domain_specific"
