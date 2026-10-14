# Legacy module with identical implementation to utils.string_helpers
# but different function names - should be detected as duplicate

def legacy_normalize(s: str) -> str:
    """Normalize string - identical to utils.string_helpers.normalize."""
    return s.strip().lower()


def legacy_validate(s: str) -> bool:
    """Validate string - identical to utils.string_helpers.validate."""
    return len(s) > 0


def legacy_unused():
    """Unused function."""
    return "unused"