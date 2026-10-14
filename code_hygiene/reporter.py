import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from code_hygiene.engine import Finding


REPORT_DIR = ".code-hygiene"
REPORT_FILE = "report.json"


def _finding_get(finding: Union[Finding, Dict[str, Any]], key: str, default: Any = None) -> Any:
    """Get attribute from Finding object or dict."""
    if isinstance(finding, Finding):
        return getattr(finding, key, default)
    return finding.get(key, default)


def _finding_set(finding: Union[Finding, Dict[str, Any]], key: str, value: Any) -> None:
    """Set attribute on Finding object or dict."""
    if isinstance(finding, Finding):
        setattr(finding, key, value)
    else:
        finding[key] = value


def _finding_to_dict(finding: Union[Finding, Dict[str, Any]]) -> Dict[str, Any]:
    """Convert Finding object to dict for JSON serialization."""
    if isinstance(finding, Finding):
        return {
            "id": finding.id,
            "category": finding.category,
            "sub_category": finding.sub_category,
            "path": finding.path,
            "severity": finding.severity,
            "confidence": finding.confidence,
            "metric": finding.metric,
            "threshold": finding.threshold,
            "action": finding.action,
            "evidence": finding.evidence,
            "detection_method": finding.detection_method,
            "first_seen": finding.first_seen,
            "last_seen": finding.last_seen,
            "related_paths": finding.related_paths,
            "rule_id": getattr(finding, "rule_id", ""),
        }
    return finding


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

    def _build_finding_key(self, finding: Union[Finding, Dict[str, Any]]) -> str:
        """Build stable key using rule_id if available, otherwise fallback to category:path."""
        rule_id = _finding_get(finding, 'rule_id', None)
        if rule_id:
            return f"rule:{rule_id}"
        return f"{_finding_get(finding, 'category', 'unknown')}:{_finding_get(finding, 'path', 'unknown')}"

    def save_report(self, policy_result: Dict[str, Any]) -> None:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        
        existing = self._load_existing_report()
        existing_findings = existing.get("findings", []) if existing else []
        
        # Build a map of current findings by key
        current_findings = policy_result.get("prioritized_findings", [])
        current_keys = {self._build_finding_key(f): f for f in current_findings}
        
        # Merge: keep existing findings that still exist in current scan (updated)
        # Add new findings from current scan
        # Remove findings that no longer exist (stale)
        merged_findings = []
        for f in current_findings:
            key = self._build_finding_key(f)
            # Find matching existing finding for history if needed
            existing_match = next((ef for ef in existing_findings 
                                 if self._build_finding_key(ef) == key), None)
            if existing_match:
                # Preserve first_seen timestamp
                _finding_set(f, "first_seen", _finding_get(existing_match, "first_seen", _finding_get(f, "timestamp", datetime.now().isoformat())))
            else:
                _finding_set(f, "first_seen", _finding_get(f, "timestamp", datetime.now().isoformat()))
            _finding_set(f, "last_seen", datetime.now().isoformat())
            merged_findings.append(_finding_to_dict(f))
        
        report = {
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
            "findings": merged_findings
        }
        
        # Write atomically
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