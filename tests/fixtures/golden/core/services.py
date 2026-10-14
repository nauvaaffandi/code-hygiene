"""Core services using utils package."""

from utils import string_helpers


def process_data(text: str) -> str:
    """Process text using string helpers."""
    normalized = string_helpers.normalize(text)
    is_valid = string_helpers.validate(normalized)
    if is_valid:
        return f"VALID: {normalized}"
    return f"INVALID: {normalized}"


def internal_service():
    """Internal function not exported - may be flagged if not used."""
    return "internal"


def unused_service():
    """Genuinely unused function - should be flagged."""
    return "unused"