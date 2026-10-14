#!/usr/bin/env python3
"""
Code Hygiene - A lightweight codebase hygiene tool for AI coding agents.
Prevents unnecessary file proliferation, oversized source files, poor directory organization,
duplicate implementations, dead code, and excessive abstractions.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from code_hygiene.config import load_config
from code_hygiene.engine import (
    FileSizeChecker, 
    DirectoryChecker, 
    DuplicateChecker,
    DeadCodeChecker,
    AbstractionChecker,
    GenerationChecker,
    ChangesChecker,
    PolicyEngine,
)
from code_hygiene.ignore import IgnoreEngine
from code_hygiene.output import render_terminal_report, render_machine_report
from code_hygiene.reporter import ReportManager


def count_total_eligible_files(repo_root: Path, ignore_engine: IgnoreEngine) -> int:
    """Count total eligible (non-ignored, non-binary) files in the repository."""
    count = 0
    for path in repo_root.rglob("*"):
        if path.is_symlink():
            continue
        if path.is_file():
            if not ignore_engine.is_ignored(path):
                try:
                    with open(path, "rb") as f:
                        chunk = f.read(1024)
                        if not chunk or b"\x00" not in chunk:
                            count += 1
                except OSError:
                    pass
    return count


def run_detectors(repo_root: Path, ignore_engine: IgnoreEngine, config: Dict[str, Any], task_description: str = "") -> List:
    """Run all detectors and collect findings."""
    findings = []
    
    # Core checkers
    detectors = [
        FileSizeChecker(),
        DirectoryChecker(),
    ]
    
    # Optional detectors based on config
    if config.get("duplicate", {}).get("enabled", True):
        detectors.append(DuplicateChecker())
    if config.get("dead_code", {}).get("enabled", True):
        detectors.append(DeadCodeChecker())
    if config.get("abstractions", {}).get("enabled", True):
        detectors.append(AbstractionChecker())
    if config.get("generation", {}).get("enabled", True):
        detectors.append(GenerationChecker())
    if config.get("git", {}).get("enabled", True):
        detectors.append(ChangesChecker())
    
    for detector in detectors:
        try:
            # Add task_description to config for changes detector
            detector_config = config.copy()
            if isinstance(detector, ChangesChecker):
                detector_config["task_description"] = task_description
            detector_findings = detector.scan(repo_root, ignore_engine, detector_config)
            findings.extend(detector_findings)
        except Exception as e:
            # Don't let one detector failure stop the whole scan
            print(f"Warning: Detector {detector.name} failed: {e}", file=sys.stderr)
    
    return findings


def main():
    parser = argparse.ArgumentParser(
        description="Code Hygiene - Scan codebase for structural and quality issues.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 start.py                    # Scan current directory
  python3 start.py /path/to/project   # Scan specific project
  python3 start.py --json             # Output JSON for programmatic use
  python3 start.py --task "refactor payment module"  # With task description
        """
    )
    parser.add_argument(
        "target_dir",
        nargs="?",
        default=".",
        help="Target directory to scan (default: current directory)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON to stdout"
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Don't save persistent report"
    )
    parser.add_argument(
        "--task",
        type=str,
        default="",
        help="Task description for change scope analysis"
    )
    parser.add_argument(
        "--no-instructions",
        action="store_true",
        help="Suppress AGENT INSTRUCTIONS in terminal output"
    )
    
    args = parser.parse_args()
    
    target_path = Path(args.target_dir).resolve()
    if not target_path.exists():
        print(f"Error: Target directory '{target_path}' does not exist.", file=sys.stderr)
        sys.exit(3)
    
    if not target_path.is_dir():
        print(f"Error: '{target_path}' is not a directory.", file=sys.stderr)
        sys.exit(3)
    
    # Load configuration
    config = load_config(str(target_path))
    
    # Initialize components
    ignore_engine = IgnoreEngine(target_path, target_path / ".ignore")
    
    # Run detectors
    findings = run_detectors(target_path, ignore_engine, config, args.task)
    
    # Count eligible files
    total_eligible = count_total_eligible_files(target_path, ignore_engine)
    
    # Evaluate policy
    policy_engine = PolicyEngine()
    policy_result = policy_engine.evaluate(findings, total_eligible)
    policy_result["repo_root"] = str(target_path)
    
    # Handle report (baseline comparison)
    report_manager = ReportManager(target_path)
    existing_report = report_manager.load_report()
    
    baseline = {}
    if existing_report:
        existing_findings = existing_report.get("findings", [])
        # Use rule_id for stable identity (category:path:sub_category as fallback)
        existing_keys = set()
        for f in existing_findings:
            rule_id = f.get('rule_id')
            if rule_id:
                existing_keys.add(f"rule:{rule_id}")
            else:
                existing_keys.add(f"{f.get('category', '')}:{f.get('path', '')}:{f.get('sub_category', '')}")
        
        current_keys = set()
        for f in findings:
            if hasattr(f, 'rule_id') and f.rule_id:
                current_keys.add(f"rule:{f.rule_id}")
            else:
                current_keys.add(f"{f.category}:{f.path}:{f.sub_category}")
        
        added = list(current_keys - existing_keys)
        removed = list(existing_keys - current_keys)
        baseline = {
            "previous_scan": existing_report.get("last_scan"),
            "previous_total": len(existing_findings),
            "diff": {
                "added": added,
                "removed": removed,
            }
        }
    
    if not args.no_report:
        report_manager.save_report(policy_result)
    
    policy_result["baseline"] = baseline
    policy_result["new_findings"] = len(baseline.get("diff", {}).get("added", []))
    policy_result["resolved_findings"] = len(baseline.get("diff", {}).get("removed", []))
    
    # Add statistics
    policy_result["statistics"] = {
        "eligible_files": total_eligible,
        "ignored_files": 0,  # Could compute if needed
        "detectors_run": ["file_size", "directory", "duplicate", "dead_code", "abstraction", "generation", "changes"],
    }
    
    # Determine exit code
    exit_codes = config.get("exit_codes", {"clean": 0, "warnings": 1, "critical": 2, "error": 3})
    if policy_result.get("has_critical_violations"):
        exit_code = exit_codes["critical"]
    elif policy_result.get("has_directory_violations") or len(findings) > 0:
        exit_code = exit_codes["warnings"]
    else:
        exit_code = exit_codes["clean"]
    policy_result["exit_code"] = exit_code
    
    # Output
    if args.json:
        from code_hygiene.output.machine import render_machine_report
        print(render_machine_report(policy_result))
    else:
        print(render_terminal_report(policy_result, show_instructions=not args.no_instructions))
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()