"""Dynamic plugin loading - uses importlib (not statically resolvable)."""

import importlib


def load_plugin(name: str):
    """Load a plugin dynamically - cannot be resolved statically."""
    module = importlib.import_module(f"plugins.{name}")
    return module


def call_dynamic_target():
    """Call a function via dynamic import."""
    module = importlib.import_module("plugins.external_plugin")
    return module.dynamic_target()


def call_static():
    """Call a statically imported function."""
    from plugins.external_plugin import static_func
    return static_func()