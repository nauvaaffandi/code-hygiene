#!/usr/bin/env bash
set -euo pipefail

# Code Hygiene - Setup Script
# Installs the Code Hygiene skill into the target AI coding environment.

SKILL_SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/skills/code-hygiene.md"
DEFAULT_DEST_DIRS=(
    "$HOME/.claude/skills/code-hygiene"
    "$HOME/.config/opencode/skills/code-hygiene"
    "$HOME/.local/share/opencode/skills/code-hygiene"
)

usage() {
    cat <<EOF
Usage: $0 [DESTINATION_DIR]

Installs the Code Hygiene skill for AI coding agents.

If DESTINATION_DIR is not provided, the script will attempt to install to
common AI coding agent skill directories:
  - ~/.claude/skills/code-hygiene
  - ~/.config/opencode/skills/code-hygiene
  - ~/.local/share/opencode/skills/code-hygiene

Options:
  -h, --help    Show this help message

Environment Variables:
  CODE_HYGIENE_SKILL_DIR  Explicit destination directory (overrides defaults)

Examples:
  $0                                    # Auto-detect destination
  $0 ~/.claude/skills/code-hygiene      # Explicit destination
  CODE_HYGIENE_SKILL_DIR=/custom/path $0  # Via environment variable
EOF
}

main() {
    if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
        usage
        exit 0
    fi

    local dest_dir="${1:-}"
    
    if [[ -z "$dest_dir" ]]; then
        if [[ -n "${CODE_HYGIENE_SKILL_DIR:-}" ]]; then
            dest_dir="$CODE_HYGIENE_SKILL_DIR"
        else
            # Find first existing parent directory or use first default
            for d in "${DEFAULT_DEST_DIRS[@]}"; do
                if [[ -d "$(dirname "$d")" ]]; then
                    dest_dir="$d"
                    break
                fi
            done
            # If no parent exists, use first default
            if [[ -z "$dest_dir" ]]; then
                dest_dir="${DEFAULT_DEST_DIRS[0]}"
            fi
        fi
    fi

    # Validate source
    if [[ ! -f "$SKILL_SOURCE" ]]; then
        echo "Error: Skill source not found at $SKILL_SOURCE" >&2
        exit 1
    fi

    # Create destination directory
    if [[ -e "$dest_dir" && ! -d "$dest_dir" ]]; then
        echo "Error: Destination '$dest_dir' exists but is not a directory" >&2
        exit 1
    fi

    mkdir -p "$dest_dir"

    # Install skill file
    local dest_file="$dest_dir/SKILL.md"
    if [[ -f "$dest_file" ]]; then
        echo "Note: Overwriting existing skill at $dest_file"
    fi

    cp "$SKILL_SOURCE" "$dest_file"

    echo "✓ Code Hygiene skill installed to $dest_file"
    echo ""
    echo "To use Code Hygiene in your project:"
    echo "  1. Copy start.py and .ignore to your project root (or any location)"
    echo "  2. Run: python3 start.py [target_directory]"
    echo ""
    echo "The skill instructs AI agents to run hygiene checks before/after changes."
}

main "$@"