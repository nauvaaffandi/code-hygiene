import json
from pathlib import Path
from typing import Any, Dict


def serialize_finding(f: Any) -> Dict[str, Any]:
    if isinstance(f, dict):
        return f
    return {
        "id": f.id,
        "category": f.category,
        "sub_category": f.sub_category,
        "path": f.path,
        "severity": f.severity,
        "confidence": f.confidence,
        "metric": f.metric,
        "threshold": f.threshold,
        "action": f.action,
        "evidence": f.evidence,
        "detection_method": f.detection_method,
        "first_seen": f.first_seen,
        "last_seen": f.last_seen,
        "related_paths": f.related_paths,
    }


def render_machine_report(policy_result: Dict[str, Any]) -> str:
    """Render machine-readable JSON report."""
    # Convert Finding objects to dicts if needed
    findings = [serialize_finding(f) for f in policy_result.get("prioritized_findings", [])]
    
    report = {
        "version": "2.0",
        "scan_timestamp": policy_result.get("timestamp"),
        "repo_root": policy_result.get("repo_root"),
        "statistics": policy_result.get("statistics", {}),
        "summary": policy_result.get("summary", {}),
        "policy": {
            "has_critical_violations": policy_result.get("has_critical_violations", False),
            "has_directory_violations": policy_result.get("has_directory_violations", False),
            "aggregate_warning_triggered": policy_result.get("aggregate_warning_triggered", False),
            "aggregate_warning_percentage": policy_result.get("aggregate_warning_percentage", 0.0),
            "aggregate_top_area": policy_result.get("aggregate_top_area", ""),
            "aggregate_areas": policy_result.get("aggregate_areas", []),
            "aggregate_explanation": policy_result.get("aggregate_explanation", ""),
            "total_eligible_files": policy_result.get("total_eligible_files", 0),
        },
        "baseline": policy_result.get("baseline", {}),
        "findings": findings,
        "exit_code": policy_result.get("exit_code", 0),
    }

    return json.dumps(report, indent=2)