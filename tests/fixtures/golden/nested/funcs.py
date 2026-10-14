"""Nested functions with duplicate inner helpers."""


def outer_a():
    """Outer function A with inner helper."""

    def helper():
        """Duplicate inner helper - same as in outer_b."""
        return "helper result"

    return f"outer_a: {helper()}"


def outer_b():
    """Outer function B with identical inner helper."""

    def helper():
        """Duplicate inner helper - same as in outer_a."""
        return "helper result"

    return f"outer_b: {helper()}"


def outer_c():
    """Outer function C with different inner helper."""

    def helper():
        """Different inner helper."""
        return "different helper"

    return f"outer_c: {helper()}"


def unused_outer():
    """Unused outer function."""
    return "unused"