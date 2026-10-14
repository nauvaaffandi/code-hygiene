"""Math utilities with some unused functions."""

from utils.string_helpers import normalize


def add(a, b):
    """Add two numbers - used by utils.string_helpers.helper_with_math."""
    return a + b


def multiply(a, b):
    """Multiply two numbers - used by core.services via utils.math_helpers."""
    return a * b


def unused_func():
    """Genuinely unused function - should be flagged."""
    return "unused"


def helper_with_string():
    """Uses string_helpers.normalize - cross-module reference."""
    return normalize("  test  ")