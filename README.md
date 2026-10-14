# Code Hygiene

An automated code hygiene and maintainability scanner for Python repositories. Designed to enforce lightweight codebase health, prevent architectural decay, and guide AI coding agents (and humans) toward clean, modular code.

## Features

- **File Size Monitoring**: Physical line count checks (Warning: 300+, Critical: 400+).
- **Directory Organization**: Flags directories exceeding 15 eligible source files.
- **Duplicate Code Detection**: Normalized and AST-based duplicate block detection (Jaccard similarity).
- **Dead Code Analysis**: Unused imports, unreachable functions/classes, entry-point aware resolution.
- **Abstraction Audit**: Flags unnecessary wrapper layers and one-function modules.
- **Change Scope & Task Analysis**: Git-aware changed files matching against task descriptions.
- **Baseline Tracking**: Persists findings to `.code-hygiene/report.json` to track added/resolved issues between runs.
- **Auto-Ignore Engine**: Intelligent `.hygieneignore` walking up from working directory, with sensible default exclusions (`node_modules`, `.git`, `build`, `dist`, `venv`, etc.).

---

## Installation & Setup

Clone the repository and run the setup script to register the skill and command for your AI agent:

```bash
git clone https://github.com/your-username/code-hygiene.git
cd code-hygiene
./setup.sh
```

---

## Usage

Run the scanner directly from any directory:

```bash
python3 start.py [target_dir]
```

### Common Options

```bash
python3 start.py --json                # Machine-readable JSON output for CI/CD
python3 start.py --concise             # Condensed summary report
python3 start.py --task "refactor auth"# Change scope analysis against a task description
python3 start.py --no-report           # Skip persistent baseline tracking
python3 start.py --no-instructions     # Suppress AI agent remediation instructions
```

---

## Thresholds & Severity

| Metric | Warning (MEDIUM) | Refactor Soon (HIGH) | Critical (CRITICAL) |
|--------|------------------|----------------------|---------------------|
| **File Size** | 300+ lines | 350+ lines | 400+ lines |
| **Directory** | — | — | >15 files |

---

## Testing

Run the test suite using Python's `unittest`:

```bash
python -m unittest discover tests -v
```

---

## License

This project is open-source software licensed under the [MIT License](LICENSE).
