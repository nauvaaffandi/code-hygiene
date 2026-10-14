"""String utilities with some unused functions."""

from utils.math_helpers import add


def normalize(s: str) -> str:
    """Normalize string - used by core.services."""
    return s.strip().lower()


def validate(s: str) -> bool:
    """Validate string - used by core.services."""
    return len(s) > 0


def unused_util():
    """Genuinely unused function - should be flagged."""
    return "unused"


def helper_with_math():
    """Uses math_helpers.add - cross-module reference."""
    return add(1, 2)