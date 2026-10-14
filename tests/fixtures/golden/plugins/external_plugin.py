"""External plugin - has both static and dynamic targets."""

def static_func():
    """Statically imported and used - should NOT be flagged."""
    return "static"


def dynamic_target():
    """Called via importlib - may be flagged as SUSPECTED."""
    return "dynamic"


def truly_unused():
    """Genuinely unused - should be flagged."""
    return "unused"