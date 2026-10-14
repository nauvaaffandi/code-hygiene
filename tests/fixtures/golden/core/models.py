"""Models with explicit __all__ exports."""

__all__ = ["public_func", "PublicClass"]


def public_func():
    """This function is exported via __all__."""
    return "public"


def private_func():
    """This function is NOT exported - should be flagged as unreachable if not used."""
    return "private"


class PublicClass:
    """This class is exported via __all__."""
    pass


class PrivateClass:
    """This class is NOT exported - should be flagged as unreachable if not used."""
    pass