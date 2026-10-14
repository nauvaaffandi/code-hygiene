import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


REPORT_DIR = ".code-hygiene"
REPORT_FILE = "report.json"


class ReportManager:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        self.report_dir = self.repo_root / REPORT_DIR
        self.report_file = self.report_dir / REPORT_FILE

    def _load_existing_report(self) -> Optional[Dict[str, Any]]:
        if not self.report_file.exists():
            return None
        try:
            with open(self.report_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _build_finding_key(self, finding: Dict[str, Any]) -> str:
        return finding.get("id") or f"{finding.get('category', 'unknown')}:{finding.get('path', 'unknown')}"

    def save_report(self, policy_result: Dict[str, Any]) -> None:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        
        existing = self._load_existing_report()
        existing_findings = existing.get("findings", []) if existing else []
        existing_keys = {self._build_finding_key(f) for f in existing_findings}
        
        current_findings = policy_result.get("prioritized_findings", [])
        current_keys = {self._build_finding_key(f) for f in current_findings}
        
        # Compute baseline diff
        added_keys = current_keys - existing_keys
        removed_keys = existing_keys - current_keys
        
        merged_findings = []
        for f in current_findings:
            key = self._build_finding_key(f)
            existing_match = next((ef for ef in existing_findings if self._build_finding_key(ef) == key), None)
            if existing_match:
                f["first_seen"] = existing_match.get("first_seen", f.get("timestamp"))
            else:
                f["first_seen"] = f.get("timestamp", datetime.now().isoformat())
            f["last_seen"] = datetime.now().isoformat()
            merged_findings.append(f)
        
        # History
        history = existing.get("history", []) if existing else []
        if existing and "last_scan" in existing:
            history.append({
                "timestamp": existing.get("last_scan"),
                "total_findings": len(existing_findings),
            })
            # Keep last 20 history items
            history = history[-20:]

        baseline = {
            "previous_scan": existing.get("last_scan") if existing else None,
            "previous_total": len(existing_findings),
            "diff": {
                "added": list(added_keys),
                "removed": list(removed_keys),
            }
        }

        report = {
            "version": "2.0",
            "last_scan": datetime.now().isoformat(),
            "repo_root": str(self.repo_root),
            "summary": policy_result.get("summary", {}),
            "policy": {
                "has_critical_violations": policy_result.get("has_critical_violations", False),
                "has_directory_violations": policy_result.get("has_directory_violations", False),
                "aggregate_warning_triggered": policy_result.get("aggregate_warning_triggered", False),
                "aggregate_areas": policy_result.get("aggregate_areas", []),
                "aggregate_explanation": policy_result.get("aggregate_explanation", ""),
                "total_eligible_files": policy_result.get("total_eligible_files", 0),
            },
            "baseline": baseline,
            "history": history,
            "findings": merged_findings
        }
        
        temp_file = self.report_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        temp_file.replace(self.report_file)

    def load_report(self) -> Optional[Dict[str, Any]]:
        return self._load_existing_report()

    def get_active_findings(self) -> List[Dict[str, Any]]:
        report = self.load_report()
        if not report:
            return []
        return report.get("findings", [])

    def get_history(self) -> List[Dict[str, Any]]:
        report = self.load_report()
        if not report:
            return []
        return report.get("history", [])