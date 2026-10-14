# Implementation Plan: Code Hygiene Tool (v2)

## Repository State Assessment

**Current state:** The repository already contains a working foundation:
- `start.py` - CLI entry point with argument parsing
- `code_hygiene/ignore.py` - `.ignore` pattern engine with default exclusions
- `code_hygiene/checkers.py` - File size and directory count checkers
- `code_hygiene/policy.py` - Aggregate warning policy and prioritization
- `code_hygiene/reporter.py` - Persistent JSON report with stale-finding removal
- `skills/code-hygiene.md` - Basic skill file
- `setup.sh` - Skill installation script
- `tests/` - 27 passing unit tests

**Gap analysis (existing → required):** The current implementation covers Sections 3–5 and part of Sections 10–11 of the new requirements. Missing completely:
1. Duplicate code detection (Section 5)
2. Unused file/dead code detection (Section 6)
3. Abstraction and file proliferation checks (Section 7)
4. Generated files and dependency auditing (Section 8)
5. Git-aware change scope analysis (Section 9)
6. Dynamic AGENT INSTRUCTIONS generation — **the core product feature (Section 2)**
7. Confidence model for findings (Sections 2, 8, 11)
8. Baseline comparison showing new vs. resolved findings (Sections 9, 11)
9. Machine-readable report with documented schema (Section 15)
10. Granular exit codes (Section 15)
11. Comprehensive agent skill (Section 12)

This plan covers all missing components while preserving the existing verified foundation.

---

## 1. Requirements and Resolved Ambiguities

### 1.1 Functional Requirements
- **start.py workflow**: 12-step execution flow culminating in AGENT INSTRUCTIONS and meaningful exit codes.
- **File size**: 0–199 SAFE, 200–249 WARNING, 250–299 REFACTOR SOON, 300+ CRITICAL.
- **Directory structure**: >15 direct child eligible files = violation.
- **Duplicate detection**: normalized comparison, repeated blocks, AST-based.
- **Dead code detection**: files, functions, classes, variables, imports, modules — language-aware.
- **Abstraction checks**: wrapper layers, one-function modules, excessive interfaces.
- **Generated/dependency audit**: build artifacts, caches, logs, vendored deps, unused deps.
- **Change scope analysis**: Git-aware, task-description comparison.
- **Aggregate policy**: WARNING (200–249) > 30% of eligible files → area prioritization.
- **Persistent reports**: latest + baseline + new/resolved findings + history.
- **Dynamic AGENT INSTRUCTIONS**: generated from verified findings with full required fields.
- **Two output modes**: human-readable terminal + machine-readable report.
- **Exit codes**: distinguish clean / findings / errors.

### 1.2 Non-functional Requirements
- Generic across languages, frameworks, repositories.
- No Git required; fallback to structural checks.
- Zero destructive modifications.
- Portable relative paths; `.code-hygiene/` isolated metadata.
- Lightweight; stdlib-first with optional language tools.
- Output understandable by humans and agents.

### 1.3 Resolved Ambiguities (documented defaults)
- **Binary detection**: first 1024 bytes containing `\x00`.
- **Line counting**: physical lines including blanks/comments (`sum(1 for _ in f)`).
- **Duplicate confidence tiers**: `confirmed` (near-identical AST/text), `likely` (normalized similarity > threshold), `suspected` (name/pattern heuristic).
- **Dead code confidence**: `confirmed` (unreachable or imported-never-resolved), `suspected` (no references but possible dynamic loading), `unsupported` (language not analyzed).
- **Area grouping for aggregate warnings**: parent directory, with `.` for root.
- **Empty repo handling**: report zero findings, exit 0, no AGENT INSTRUCTIONS block (nothing actionable).
- **Baseline**: first scan creates baseline; subsequent scans compute new/resolved deltas by finding key + path + metric.
- **Default exit codes**: 0 clean, 1 findings, 2 critical, 3 execution error.
- **Unsupported language**: structural checks still run; code-quality checks marked `unsupported` rather than failing.

---

## 2. Architecture and Component Responsibilities

```
start.py                     orchestrator: workflow 1–12, CLI, exit codes
│
├─ engine/
│   ├─ __init__.py
│   ├─ ignore.py             .ignore parsing & matching (existing, preserved)
│   ├─ checkers/
│   │   ├─ __init__.py
│   │   ├─ file_size.py      line-count classification (existing→renamed)
│   │   ├─ directory.py      >15 child-files check (existing→renamed)
│   │   └─ base.py           Finding base class + detector API
│   ├─ duplicate.py          normalized/AST duplicate detection
│   ├─ dead_code.py          unused files/functions/classes/imports detection
│   ├─ abstractions.py       wrapper/one-function/excessive-interface checks
│   ├─ generation.py         generated-file & dependency audit
│   ├─ changes.py            Git-aware change scope analysis
│   ├─ policy.py             aggregate warning + deterministic prioritization
│   └─ confidence.py         severity × confidence scoring model
│
├─ report/
│   ├─ __init__.py
│   ├─ manager.py            persistent JSON + baseline delta computation
│   └─ schema.py             machine-readable schema documentation
│
├─ output/
│   ├─ __init__.py
│   ├─ agent_instructions.py dynamic AGENT INSTRUCTIONS generation
│   ├─ terminal.py           human-readable report
│   └─ machine.py            machine-readable report (JSON to file)
│
└─ config.py                 configuration schema + defaults
```

**Interaction flow:**
1. `start.py` → loads config + `.ignore`, walks target repo.
2. Each detector in `engine/checkers/` and `engine/*.py` scans, emits `Finding` objects with path, metric, evidence, confidence.
3. `report.Manager` compares current findings against baseline → computes `new`, `resolved`, `persistent` sets.
4. `engine/policy.py` evaluates aggregate policy over current findings.
5. `output/agent_instructions.py` generates AGENT INSTRUCTIONS from findings + confidence + policy.
6. `output/terminal.py` and `output/machine.py` render the report.
7. Exit code determined by: execution error → 3; critical findings → 2; any finding → 1; clean → 0.

**Design principle:** detectors are pure functions from repo state → list of Findings. No global state. This keeps each ticket independently testable.

---

## 3. Complete Proposed Repository Tree

```
code-hygiene/
├── .ignore
├── README.md
├── setup.sh
├── start.py
├── code_hygiene/
│   ├── __init__.py
│   ├── config.py                       # config schema & defaults
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── base.py                     # Finding dataclass, Detector ABC
│   │   ├── ignore.py                   # (preserved) ignore engine
│   │   ├── checkers/
│   │   │   ├── __init__.py
│   │   │   ├── file_size.py            # (preserved) line-count checker
│   │   │   └── directory.py            # (preserved) dir-count checker
│   │   ├── duplicate.py                # NEW
│   │   ├── dead_code.py                # NEW
│   │   ├── abstractions.py             # NEW
│   │   ├── generation.py               # NEW
│   │   ├── changes.py                  # NEW
│   │   ├── policy.py                   # (preserved, extended)
│   │   └── confidence.py               # NEW
│   ├── report/
│   │   ├── __init__.py
│   │   ├── manager.py                  # persistent + baseline delta
│   │   └── schema.py                   # NEW (schema docs)
│   └── output/
│       ├── __init__.py
│       ├── agent_instructions.py       # NEW (dynamic AGENT INSTRUCTIONS)
│       ├── terminal.py                 # human report
│       └── machine.py                  # NEW (machine report writer)
├── skills/
│   └── code-hygiene.md                 # (revamped) comprehensive skill
└── tests/
    ├── test_file_size.py
    ├── test_directory.py
    ├── test_duplicate.py
    ├── test_dead_code.py
    ├── test_abstractions.py
    ├── test_generation.py
    ├── test_changes.py
    ├── test_confidence.py
    ├── test_policy.py                  # (preserved, extended)
    ├── test_reporter.py                # (preserved, extended)
    ├── test_agent_instructions.py      # NEW
    ├── test_terminal.py                # NEW
    ├── test_machine.py                 # NEW
    ├── test_setup.py                   # (preserved, extended)
    └── conftest.py                     # shared fixtures (test repos)
```

---

## 4. Configuration and Report Schemas

### 4.1 Configuration (`code_hygiene/config.py`)
```python
DEFAULT_CONFIG = {
    "file_size": {"min_safe": 0, "warning": 200, "refactor_soon": 250, "critical": 300},
    "directory": {"threshold": 15, "count_direct_only": True},
    "duplicate": {"min_similarity": 0.75, "min_block_lines": 7, "use_ast": True},
    "dead_code": {"ignore_patterns": ["test_*.py", "*_test.py"], "support": ["python", "javascript", "go"]},
    "aggregate_warning": {"threshold": 0.30, "strictly_greater": True},
    "report": {"dir": ".code-hygiene", "file": "report.json"},
    "git": {"enabled": True},
    "exit_codes": {"clean": 0, "warnings": 1, "critical": 2, "error": 3},
}
```
Configuration is loadable from `~/.config/code-hygiene/config.json` or a `code_hygiene.json` in the target repo, overriding only specified values (merge, don't replace).

### 4.2 Finding Schema (per finding)
```json
{
  "id": "file_size:src/payment.py",
  "category": "file_size",
  "sub_category": "lines",
  "path": "src/payment.py",
  "severity": "CRITICAL",
  "confidence": "confirmed",
  "metric": 347,
  "threshold": ">= 300",
  "action": "Refactoring is mandatory.",
  "evidence": "Physical line count of 347, including 42 comment lines and 18 blank lines.",
  "detection_method": "physical_line_count",
  "first_seen": "2026-10-14T14:00:00Z",
  "last_seen": "2026-10-14T15:00:00Z"
}
```

### 4.3 Machine Report Schema
```json
{
  "version": "2.0",
  "scan_timestamp": "2026-10-14T15:00:00Z",
  "repo_root": "/path/to/repo",
  "config_snapshot": {...},
  "statistics": {
    "eligible_files": 312,
    "ignored_files": 45,
    "unsupported_languages": ["rust"],
    "detectors_run": ["file_size", "directory", "duplicate", "dead_code"],
    "detectors_unsupported": ["abstractions:go"]
  },
  "summary": {
    "by_severity": {"critical": 3, "high": 5, "medium": 12, "low": 8, "info": 0},
    "by_category": {"file_size": 8, "directory": 2, "duplicate": 5, "dead_code": 6, ...},
    "new_findings": 3,
    "resolved_findings": 1,
    "persistent_findings": 12,
    "total_findings": 28
  },
  "findings": [...],
  "baseline": {
    "previous_scan": "2026-10-14T14:00:00Z",
    "previous_total": 15,
    "diff": {"added": ["id:file_size:new.py", ...], "removed": ["id:file_size:old.py", ...]}
  },
  "aggregate_warning": {"triggered": true, "percentage": 40.5, "top_area": "src/core", "explanation": "..."},
  "exit_code": 2,
  "agent_instructions": {...}
}
```

### 4.4 Terminal Report
Sectioned output: `=== Scan Summary ===`, `=== Critical Findings ===`, `=== Directory Violations ===`, `=== Highest-Priority Targets ===`, `=== Aggregate Warning Status ===`, `=== Baseline: New / Resolved ===`, `=== AGENT INSTRUCTIONS ===`, `=== Verification Recommendations ===`.

---

## 5. Core Algorithms

### 5.1 Physical Line Counting
Identical to existing: binary check (null byte in first 1024 bytes), then `sum(1 for _ in f)` with utf-8 fallback.

### 5.2 Directory Child-File Counting
Iterate each eligible directory's direct children (`iterdir()`), skip symlinks, skip ignored, skip binary; count remaining files. Count is **direct children only** (default), as intended.

### 5.3 Ignore-Pattern Matching
Preserved existing implementation: fnmatch-based, supports comments, blank lines, wildcards, directory (`/`) patterns, recursive `**` matching. Documented limitations: no negation patterns (`!`), no regex, no bracket expressions.

### 5.4 Duplicate Detection
1. **Normalization**: strip comments, blank lines, whitespace, normalize string/number literals to placeholders (`<STR>`, `<NUM>`).
2. **Candidate selection**: tokenize each file into blocks (functions/classes/assignments); compare blocks pairwise across files using normalized text similarity (e.g., set-based Jaccard on tokens or Levenshtein ratio).
3. **AST verification (when parser available)**: for supported languages, parse with `ast` (Python) or available CLI (e.g., `go`/`eslint`), compare AST subtrees; `confirmed` only on AST equivalence.
4. **Confidence**: `confirmed` = AST-equivalent or >95% normalized similarity; `likely` = 75–95%; `suspected` = heuristic name/pattern match.
5. **Evidence**: show overlapping code snippets (lines 3–10 of each block).

### 5.5 Dead Code Detection
1. **Files**: files with no references and no entry point markers (e.g., `if __name__ == "__main__"`, registered handlers). Mark `suspected` for supported languages.
2. **Imports**: track imports vs. usages; unused imports → `suspected`.
3. **Functions/classes**: reachable-call-graph walk from entry points; unreachable or never-called public symbols → `suspected`.
4. **Dynamic references**: account for `__import__`, `getattr`, decorators, plugin registration dicts; if any such mechanism exists, degrade confidence from `confirmed` to `suspected`.
5. **Unspecified languages**: structural check only (no reference tracking) — always `unsupported`.

### 5.6 Abstraction Checks
- **Wrapper layers**: functions/classes whose body is a single `return <call>` or pass-through delegate → `suspected`, with snippet evidence.
- **One-function modules**: `.py` (or equivalent) files containing exactly one function/class and no docstring-driven purpose → `suspected`, require agent judgment.
- **Excessive interfaces/factories**: directories with >N interfaces per N classes or factories whose variants differ only in parameter values → `suspected`.
- Never `confirmed` violations without sufficient evidence.

### 5.7 Generated-File & Dependency Audit
- **Patterns**: files matching `*_generated*`, `build/`, `dist/`, caches, lock files → flagged as generated; listed for agent review, not deletion.
- **Dependency duplication**: parse `requirements.txt`/`package.json`/`go.mod`; compare declared packages against imports; packages never imported → `suspected unused`. Packages whose functionality exists in stdlib or another already-declared package → `suspected duplicate`.

### 5.8 Git-Aware Change Scope
1. Run `git status --porcelain`, `git diff --stat`, `git diff --name-status`.
2. Classify: added, modified, deleted, renamed files.
3. Compute change volume per directory; flag changes outside the apparent implementation area if task description present.
4. **Task comparison**: parse task description for keywords (file/dir names); flag modifications that touch files not mentioned and not covered by obvious scope (e.g., unrelated test changes).
5. Without Git: skip, report `detectors_unsupported` includes `changes`.
6. **Never modify/reset/revert.** Purely advisory.

### 5.9 Aggregate Warning Policy
```
warning_percentage = warning_file_count / eligible_file_count * 100
trigger = warning_percentage > 30 (strict)
```
- **Area selection**: group WARNING files by parent directory; rank by count (primary), warning density (secondary), and "potential single-operation resolution" (tertiary: areas where one refactor resolves ≥2 findings gets boost).
- **Interaction with REFACTOR SOON**: if any REFACTOR SOON exists, aggregate is reported as supplementary; aggregate never hides individual findings. If CRITICAL exists, aggregate suppressed entirely.

### 5.10 Prioritization
Order: CRITICAL files → directory violations → REFACTOR SOON files → aggregate-warning areas → individual WARNING files → high-confidence duplicates → high-confidence dead code. Deduplicate recommendations that resolve to the same target.

### 5.11 Report Generation & Stale-Finding Removal
- Findings keyed by `<category>:<path>` (+ sub-key for AST-level findings, e.g., `<category>:<path>:<func>`).
- Baseline load: compare current keys vs stored keys → `new` (added), `resolved` (removed + not reappear), `persistent` (present both).
- Files removed from disk are not active findings but logged in baseline diff; history kept in report for reference.
- Atomic write (`<report>.tmp` → rename).

### 5.12 Confidence Model
Severity × confidence matrix for report summary and filtering:
- `confirmed`: high evidence (AST/equivalence/measured).
- `likely`: normalized similarity with clear evidence.
- `suspected`: heuristic; agent must verify before acting.
- `unsupported`: analysis not available for language.
Exit code uses `confirmed`/`likely` severity for CRITICAL; `suspected` entries never raise exit code above 1 alone.

---

## 6. Severity and Confidence Model

| Severity     | Meaning                                             | Exit-code impact          |
|--------------|-----------------------------------------------------|---------------------------|
| CRITICAL     | Mandatory refactoring (≥300 lines, dir >15)         | exit 2                    |
| HIGH         | high-confidence duplicate/dead-code confirmed       | exit 1                    |
| MEDIUM       | REFACTOR SOON (250–299), likely issues              | exit 1                    |
| LOW          | WARNING (200–249), abstracts to investigate         | exit 0 if nothing else    |
| INFO         | generated-file listings, dependency audit           | exit 0                    |

Confidence is orthogonal to severity and is always surfaced per finding; agent instructions include a "Confidence" line.

---

## 7. Dynamic AGENT INSTRUCTIONS Generation

**Generator design (`output/agent_instructions.py`):**
- Each `Finding` carries a per-category `instruction_template` — a dict of required fields: `issue`, `affected`, `why`, `action` (ordered bullets), `constraints`, `verification`.
- Template fills from finding attributes (path, metric, evidence, confidence, threshold) plus policy context.
- Group findings into priority sections: `Priority 1 — CRITICAL`, `Priority 2 — DIRECTORY STRUCTURE`, `Priority 3 — HIGH CONFIDENCE DUPLICATES`, `Priority 4 — REFACTOR SOON / AGGREGATE`, `Priority 5 — LOW CONFIDENCE / INVESTIGATE`.
- **Never hardcode examples.** Generate from verified findings only.
- **Empty-finding case:** if no actionable findings, print `AGENT INSTRUCTIONS` with "No issues requiring action" plus guidance for adding new code safely (the skill's default behavior).

**Instruction fields (required):**
1. `issue` — one-sentence summary.
2. `affected` — file/directory path(s).
3. `why` — why it matters (risk of confusion, maintenance burden, duplication).
4. `action` — ordered, imperative bullets; includes "don't" constraints.
5. `constraints` — preserve behavior/interfaces/tests, no meaningless splits, don't add to over-limit dirs, no auto-delete.
6. `verification` — run relevant tests, rerun Code Hygiene, confirm resolution, verify imports/entry points.

**Evidence injection:** each instruction embeds the finding's `evidence` text and, for duplicates, the two paths + snippet. For suspected/unsupported findings, add: "Inspect evidence before acting; do not delete based on this finding alone."

---

## 8. Skill Design and Installation

### 8.1 Skill (`skills/code-hygiene.md`) — revamp to cover:
- Run `start.py` before substantial changes and after.
- Interpret the AGENT INSTRUCTIONS section first.
- Priority order for acting.
- How to respond to each severity.
- Duplicate findings: compare behavior/ responsibilities/call sites; preserve intentional differences.
- Dead code: inspect evidence (dynamic imports, framework registration, entry points) before deletion.
- Aggregate warning: pick the top area; don't refactor every warning file.
- No file proliferation, no meaningless splits.
- Do not add files to over-limit directories.
- Preserve architecture and behavior; run tests; rerun Code Hygiene.
- Handling uncertain/unsupported findings: report honestly, do not perform destructive changes.
- Agent must not treat scan as permission for broad unrelated refactoring.

### 8.2 Setup (`setup.sh`) — preserve existing, extend:
- Keep explicit destination + env var + auto-detection.
- Add uninstall guidance and update instructions (re-run = overwrite skill only, never project files).
- Preserve safety properties: no root, no unrelated-file overwrite warning, re-runnable, path validation, clear success/error messages.

---

## 9. Detailed Implementation Tickets

### Ticket A: Foundation Refactor — Detector API + Config + Confidence
- **Objective:** unify finding model, add confidence model, config layer; keep existing checkers compatible.
- **Files:** `code_hygiene/engine/base.py` (new), `code_hygiene/config.py` (new), `code_hygiene/engine/confidence.py` (new), `start.py` (update to new API), `code_hygiene/checkers/file_size.py`, `code_hygiene/checkers/directory.py` (rename + adapt).
- **Dependencies:** none.
- **Details:** `Finding` dataclass with id, category, sub_category, path, severity, confidence, metric, threshold, action, evidence, detection_method, first_seen, last_seen. `Detector` ABC with `scan(repo_root, ignore_engine, config)` → list[Finding]. Config merges defaults → env → file. Confidence helper `classify_confidence(evidence_quality)`.
- **Acceptance criteria:** `FileSizeChecker` and `DirectoryChecker` produce `Finding` objects with all fields; config override works.
- **Verification:** `python3 -m unittest tests/test_file_size.py tests/test_directory.py` (rewritten).

### Ticket B: Report Manager Baselines + Delta
- **Objective:** persistent reports with baseline comparison; new/resolved/persistent tracking.
- **Files:** `code_hygiene/report/manager.py` (extend), `tests/test_reporter.py` (extend).
- **Dependencies:** Ticket A.
- **Details:** load previous report; compute diff by finding key; store `baseline` section with `previous_scan`, `previous_total`, `diff: {added, removed}`; keep `history` list of past `total_findings` timestamps.
- **Acceptance criteria:** removed files disappear from active findings but appear in baseline diff; new findings appear in `added`.
- **Verification:** `python3 -m unittest tests/test_reporter.py::test_baseline_new_and_resolved`.

### Ticket C: Duplicate Code Detection
- **Objective:** normalized + AST duplicate detector with confidence tiers.
- **Files:** `code_hygiene/engine/duplicate.py` (new), `tests/test_duplicate.py` (new), `code_hygiene/engine/__init__.py` (register), `start.py` (add detector).
- **Dependencies:** Ticket A.
- **Details:** normalization (strip comments/blanks, placeholder literals); Jaccard similarity on token sets for candidate blocks; AST comparison via Python `ast` module for `confirmed`; evidence = snippet lines; confidence `confirmed/likely/suspected`.
- **Acceptance criteria:** detects near-identical functions in two files; confidence differs between text-similar vs AST-equivalent.
- **Verification:** create test repo with 2 duplicate functions; run; assert findings + evidence.

### Ticket D: Dead Code Detection
- **Objective:** language-aware unused detection for supported languages; structural fallback.
- **Files:** `code_hygiene/engine/dead_code.py` (new), `tests/test_dead_code.py` (new), `start.py`, `code_hygiene/engine/__init__.py`.
- **Dependencies:** Ticket A, C.
- **Details:** entry-point discovery (main guards, registered handlers); import-usage graph; reachable-call-graph walk; dynamic-reference handling (`__import__`, `getattr`, decorators) degrades confidence; `unsupported` for unlisted languages.
- **Acceptance criteria:** unused import and unreachable function flagged `suspected`; function with dynamic call not flagged.
- **Verification:** test repo with unused import, dead function, function called via string reference.

### Ticket E: Abstraction and Generation/Dependency Audits
- **Objective:** wrapper/one-function/excessive-interface checks + generated-file + dependency audit.
- **Files:** `code_hygiene/engine/abstractions.py` (new), `code_hygiene/engine/generation.py` (new), `tests/test_abstractions.py`, `tests/test_generation.py` (new).
- **Dependencies:** Ticket A.
- **Details:** wrapper detection = body is single pass-through return; one-function module detection; interface-to-class ratio; generated-file pattern listing; dependency parsing (requirements.txt/package.json/go.mod) vs imports.
- **Acceptance criteria:** pass-through function flagged `suspected`; package never imported flagged `suspected`; generated files listed not deleted.

### Ticket F: Git-Aware Change Scope
- **Objective:** optional Git diff analysis with task-description comparison.
- **Files:** `code_hygiene/engine/changes.py` (new), `tests/test_changes.py` (new), `start.py`.
- **Dependencies:** Ticket A.
- **Details:** parse `git status`/`git diff --name-status`; classify add/modify/delete/rename; per-directory change volume; keyword match vs task description; no Git → `detectors_unsupported`.
- **Acceptance criteria:** with Git: reports changed files and suspicious scope; without Git: graceful skip.
- **Verification:** create git repo, make unrelated change, run; assert advisory report only.

### Ticket G: Output Layer — Terminal + Machine + AGENT INSTRUCTIONS
- **Objective:** human-readable report, machine-readable report, dynamic AGENT INSTRUCTIONS.
- **Files:** `code_hygiene/output/agent_instructions.py` (new), `code_hygiene/output/terminal.py` (new), `code_hygiene/output/machine.py` (new), `code_hygiene/output/schema.py` (new), `start.py` (output routing + exit codes).
- **Dependencies:** Tickets A–F.
- **Details:** sectioned terminal output per §4.4; machine JSON with documented schema; AGENT INSTRUCTIONS dynamically built from priority-grouped findings; exit codes 0/1/2/3.
- **Acceptance criteria:** terminal includes AGENT INSTRUCTIONS with all required fields; JSON matches schema; exit code 2 with critical, 1 with warnings, 0 clean, 3 on error.
- **Verification:** run on test repo; diff terminal output; validate JSON against schema file.

### Ticket H: Policy Extensions + Aggregate Integration
- **Objective:** extend policy with REFACTOR SOON interaction, area ranking with resolution-potential boost, confidence gating.
- **Files:** `code_hygiene/engine/policy.py` (extend), `tests/test_policy.py` (extend).
- **Dependencies:** Ticket A.
- **Details:** aggregate suppression when CRITICAL present; REFACTOR SOON reported alongside aggregate; ranking criteria count → density → resolution potential; confidence gating for report summary.
- **Acceptance criteria:** CRITICAL present → aggregate suppressed; boundary 30% exact not triggered, 30.1% triggered.

### Ticket I: Skill and Setup Revamp
- **Objective:** comprehensive skill + extended setup (uninstall/update guidance).
- **Files:** `skills/code-hygiene.md` (rewrite), `setup.sh` (extend with uninstall help), `tests/test_setup.py` (extend).
- **Dependencies:** none.
- **Details:** rewrite skill per §8.1; setup adds uninstall/update help, preserves all existing safety properties.
- **Acceptance criteria:** setup --help shows uninstall; re-run overwrites skill, warns before overwriting.
- **Verification:** `bash setup.sh --help`, rerun install test.

### Ticket J: End-to-End Verification + Integration Tests
- **Objective:** full workflow test across all detectors; conftest fixtures.
- **Files:** `tests/conftest.py` (new), `tests/test_end_to_end.py` (new), `tests/test_agent_instructions.py` (new).
- **Dependencies:** Tickets A–I.
- **Details:** fixture creates multi-language-mock repos (Python + "unsupported" language) with known findings; assert terminal output, JSON, AGENT INSTRUCTIONS content, baseline delta on rerun.
- **Acceptance criteria:** 90%+ of expected findings present; AGENT INSTRUCTIONS contains evidence and verification steps for each; baseline diff correct after file removal.
- **Verification:** `python3 -m unittest tests/test_end_to_end.py`.

---

## 10. Test Strategy

**Boundary tests:**
- File lines: files at exactly 199 (SAFE), 200 (WARNING), 249 (WARNING), 250 (REFACTOR SOON), 299 (REFACTOR SOON), 300 (CRITICAL).
- Directory: 15 direct children (ok), 16 (violation).
- Aggregate: repo with exactly 30% WARNING files (not triggered), 30.1% (triggered).
- Empty repo: no findings, exit 0, no AGENT INSTRUCTIONS action block.
- Ignored: `.ignore` entries for files + nested dirs + wildcards; ignored files not counted in eligible totals.
- Stale findings: remove a finding file, rerun; active report clean, baseline diff shows resolved.
- Unsupported languages: repo with `.rs` files; structural checks pass; code-quality checks marked `unsupported`.
- Dynamic references: function invoked via `getattr`/`__import__`; not flagged as dead.
- Symbolic links: symlinked dirs/files not followed; no recursion; outside-repo targets not scanned.
- Existing user modifications: Git ticket verifies tool reads but never modifies/reset/reverts.
- Setup safety: install to custom dir; rerun overwrites skill only; invalid destination error message; no root needed.
- Dynamic instruction generation: repo with duplicate; AGENT INSTRUCTIONS contains both paths + evidence; repo with suspected dead code; instructions include "inspect before acting".

---

## 11. Acceptance Criteria

- [ ] Running `python3 start.py` on any target directory prints terminal report with all 15 required output sections (§15) and an AGENT INSTRUCTIONS section with dynamically generated, evidence-backed actions.
- [ ] Machine-readable report written to `.code-hygiene/report.json` matches documented schema.
- [ ] File size thresholds exact: 199 SAFE, 200 WARNING, 249 WARNING, 250 REFACTOR SOON, 299 REFACTOR SOON, 300 CRITICAL.
- [ ] Directory threshold exact: 15 ok, 16 violation.
- [ ] Aggregate policy: exactly 30% NOT triggered; 31% triggered; area ranked by count/density/resolution-potential.
- [ ] Duplicate detector reports candidates with evidence and confidence; never deletes or merges.
- [ ] Dead-code detector never classifies a file as unused without confidence ≤ `suspected`; dynamic-reference-safe.
- [ ] Git changes are read-only; no reset/revert/modify.
- [ ] Exit codes: 0 clean, 1 warnings, 2 critical, 3 execution error.
- [ ] Baseline delta shows new vs resolved findings after file removal/addition.
- [ ] Setup installs skill to explicit/custom/default destination; re-runnable; uninstall/update documented.
- [ ] `.ignore` consistent across all detectors; default exclusions documented and overridable.
- [ ] 27 original tests still pass + 8 new ticket tests ≥ 80% coverage of new code.

---

## 12. Risks, Limitations, and Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| False positives in duplicate/dead-code detection | Agent wastes time; trust erosion | Confidence tiers; `suspected` never raises exit code; evidence always shown; instructions say inspect before acting |
| AST dependency on parser availability | Degrades duplicate confidence | Fallback to normalized text; `use_ast` config |
| Unsupported languages | Limited code-quality insight | Structural checks still run; marked `unsupported` explicitly |
| Dynamic imports/reflection hiding dead code | Under-detection (conservative) | Favor under-detection over deletion; never delete automatically |
| Large repos (10k+ files) performance | Slow scans | Skip ignored early; binary check first; optional parallelization |
| Over-engineering | Scope creep | Each ticket bounded; AST optional; no abstraction without evidence |
| Baseline confusion | User thinks stale findings are active | `new`/`resolved`/`persistent` labels in report; stale never active |
| Agent over-reliance on tool | Broad unnecessary refactoring | Skill explicitly forbids; instructions emphasize context + existing architecture |

**Design simplicity guardrails:**
- Detectors are pure functions; no global mutable state.
- No database, no daemon, no remote calls.
- One cohesive `engine/` package, one `output/`, one `report/`.
- Config merges rather than replaces.
- Nothing deleted or modified by the scanner — ever.
