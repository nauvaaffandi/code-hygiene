# Configuration schema and defaults for Code Hygiene.
#
# Merge order (lower overrides higher):
#   1. defaults
#   2. env var CODE_HYGIENE_CONFIG (file path)
#   3. repo-level code_hygiene.json in target directory
#   4. user config at ~/.config/code-hygiene/config.json


DEFAULT_FILE_SIZE = {
    "min_safe": 0,
    "warning": 200,
    "refactor_soon": 250,
    "critical": 300,
}

DEFAULT_DIRECTORY = {
    "threshold": 15,
    "count_direct_only": True,
}

DEFAULT_DUPLICATE = {
    "enabled": True,
    "min_similarity": 0.75,
    "min_block_lines": 7,
    "use_ast": True,
}

DEFAULT_DEAD_CODE = {
    "enabled": True,
    "ignore_patterns": ["test_*.py", "*_test.py", "tests/", "spec/"],
    "support": ["python", "javascript", "typescript", "go", "java"],
}

DEFAULT_GENERATION = {
    "enabled": True,
    "patterns": [
        "*.generated.*",
        "*generated*",
        "_generated",
        "build/",
        "dist/",
        "*.min.js",
        "*.min.css",
        "*.map",
        "node_modules/",
        "vendor/",
        "venv/",
        ".venv/",
        "__pycache__/",
        "*.pyc",
    ],
}

DEFAULT_ABSTRACTIONS = {
    "enabled": True,
    "max_interfaces_per_class": 10,
    "one_function_warning": True,
}

DEFAULT_AGGREGATE = {
    "threshold": 0.30,
    "strictly_greater": True,
}

DEFAULT_REPORT = {
    "dir": ".code-hygiene",
    "file": "report.json",
    "save_history": True,
}

DEFAULT_GIT = {
    "enabled": True,
}

DEFAULT_EXIT_CODES = {
    "clean": 0,
    "warnings": 1,
    "critical": 2,
    "error": 3,
}

DEFAULT_CONFIG = {
    "file_size": DEFAULT_FILE_SIZE.copy(),
    "directory": DEFAULT_DIRECTORY.copy(),
    "duplicate": DEFAULT_DUPLICATE.copy(),
    "dead_code": DEFAULT_DEAD_CODE.copy(),
    "generation": DEFAULT_GENERATION.copy(),
    "abstractions": DEFAULT_ABSTRACTIONS.copy(),
    "aggregate_warning": DEFAULT_AGGREGATE.copy(),
    "report": DEFAULT_REPORT.copy(),
    "git": DEFAULT_GIT.copy(),
    "exit_codes": DEFAULT_EXIT_CODES.copy(),
}


def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = _deep_copy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    return result


def _deep_copy(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _deep_copy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [item for item in obj]
    return obj


def load_config(repo_root: str) -> Dict[str, Any]:
    import os
    import json

    config = _deep_copy(DEFAULT_CONFIG)

    # 1. User config
    user_config = os.path.expanduser("~/.config/code-hygiene/config.json")
    if os.path.isfile(user_config):
        try:
            with open(user_config, "r", encoding="utf-8") as f:
                config = merge_configs(config, json.load(f))
        except (json.JSONDecodeError, OSError):
            pass

    # 2. Repo-level config
    repo_config = os.path.join(repo_root, "code_hygiene.json")
    if os.path.isfile(repo_config):
        try:
            with open(repo_config, "r", encoding="utf-8") as f:
                config = merge_configs(config, json.load(f))
        except (json.JSONDecodeError, OSError):
            pass

    return config
