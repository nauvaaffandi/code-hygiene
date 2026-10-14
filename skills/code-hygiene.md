# Code Hygiene Skill

Instructs AI coding agents to maintain high codebase hygiene by preventing unnecessary file proliferation, oversized source files, poor directory organization, duplicate implementations, dead code, excessive abstractions, and generated file mismatches.

## When to Run

- Run `python3 start.py` before making substantial changes and after completing modifications that affect the codebase.
- Run with `--json` for programmatic consumption in CI/CD pipelines.
- Run with `--task "description"` to enable change scope analysis against a task description.

## Detectors

| Detector | Category | Description |
|----------|----------|-------------|
| `file_size` | File size | Physical line count thresholds: SAFE (<200), WARNING (200–249), REFACTOR SOON (250–299), CRITICAL (300+) |
| `directory` | Directory org | Flags directories exceeding 15 eligible files |
| `duplicate` | Duplicate code | Normalized and AST-based duplicate block detection (Jaccard similarity) |
| `dead_code` | Dead code | Unused imports, unreachable functions/classes, entry-point aware |
| `abstraction` | Abstractions | Wrapper layers, one-function modules, excessive interfaces |
| `generation` | Generated files | Mismatched generated files, dependency auditing (stdlib vs third-party vs local) |
| `changes` | Change scope | Git-aware changed files, task description keyword matching |

## Interpreting the Report

### File Size Thresholds
- **SAFE (<200 lines)**: No action required.
- **WARNING (200–249 lines)**: Avoid adding complex logic or heavy functionality.
- **REFACTOR SOON (250–299 lines)**: Prioritize refactoring as soon as reasonably possible.
- **CRITICAL (300+ lines)**: Refactoring is mandatory.

### Directory Organization
- **Directory > 15 files**: Must distribute into meaningful subdirectories. Avoid creating additional files in over-limit directories.

### Confidence Levels
Each finding includes a confidence assessment:
- **CONFIRMED**: Direct evidence (e.g., exact line count, git status)
- **LIKELY**: Strong heuristic match (e.g., AST similarity > 0.8, unreachable code)
- **SUSPECTED**: Probable but needs verification (e.g., dead code without call graph)
- **UNSUPPORTED**: Low confidence, informational only

## Response Guidelines

1. **Prioritization**: Follow deterministic order:
   - CRITICAL file size violations
   - Over-limit directories
   - REFACTOR SOON files
   - Aggregate warning areas (if >30% of files in one category)
   - Individual WARNING files
   - SUSPECTED/UNSUPPORTED findings (manual verification first)

2. **No File Proliferation**: Do not create unnecessary files or split code into meaningless modules just to satisfy numerical thresholds.

3. **Preserve Architecture**: Preserve existing architecture, behavior, and tests while refactoring.

4. **No Auto-Modification**: The tool identifies and reports; agents must perform refactoring thoughtfully and manually.

5. **Threshold Reconsideration**: When a planned modification would push a file into a more severe category, reconsider the implementation before adding more code.

6. **AGENT INSTRUCTIONS**: When running in terminal mode, the tool outputs structured AGENT INSTRUCTIONS for each finding. Follow these precisely for consistent remediation.

7. **Baseline Tracking**: Reports are persisted to `.code-hygiene/report.json`. Subsequent runs show:
   - **Added**: New findings since last scan
   - **Removed**: Resolved findings
   - **Persistent**: Findings that remain

8. **Machine Output**: Use `--json` for structured output with full finding metadata including `first_seen`, `last_seen`, `confidence`, `detection_method`, and `related_paths`.

## Commands

```bash
python3 start.py [target_dir]          # Scan directory (default: current)
python3 start.py --json                # JSON output for CI/CD
python3 start.py --no-report           # Skip persistent report
python3 start.py --task "refactor auth" # Change scope analysis
python3 start.py --no-instructions     # Suppress AGENT INSTRUCTIONS
```

## Exit Codes

- `0`: No critical violations, no directory violations
- `1`: Critical file size violations found
- `2`: Directory count violations found
- `3`: Both critical and directory violations
- `4`: Aggregate warning triggered (>30% files in same category)

## Installation

Run `./setup.sh` to install the skill for your AI coding agent. The script creates `~/.config/opencode/skill/code-hygiene.md` and registers the `start.py` command.