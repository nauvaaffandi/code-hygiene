import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from code_hygiene.engine import Finding


SEVERITY_ORDER = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
    "INFO": 4,
}


def _get_severity(f: Any) -> str:
    return f.severity if hasattr(f, "severity") else f.get("severity", "")


def _get_category(f: Any) -> str:
    return f.category if hasattr(f, "category") else f.get("category", "")


def _get_path(f: Any) -> str:
    return f.path if hasattr(f, "path") else f.get("path", "")


def _get_metric(f: Any) -> int:
    return f.metric if hasattr(f, "metric") else f.get("metric", 0)


def _to_dict(f: Any) -> Dict[str, Any]:
    if hasattr(f, "__dict__"):
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
            "rule_id": getattr(f, "rule_id", ""),
        }
    return f


def calculate_aggregate_warning_policy(findings: List[Finding], 
                                       total_eligible_files: int) -> Tuple[bool, float, List[str], str]:
    """
    Returns (triggered, percentage, affected_areas, explanation)
    """
    if total_eligible_files == 0:
        return False, 0.0, [], ""
    
    warning_files = [f for f in findings if _get_severity(f) == "MEDIUM" and _get_category(f) == "file_size"]
    warning_count = len(warning_files)
    
    percentage = (warning_count / total_eligible_files) * 100 if total_eligible_files > 0 else 0.0
    
    if percentage <= 30.0:
        return False, percentage, [], ""
    
    # Group WARNING files by their parent directory (or logical area)
    area_warnings = defaultdict(list)
    for f in warning_files:
        path = _get_path(f)
        area = os.path.dirname(path)
        if not area:
            area = "."
        area_warnings[area].append(f)
    
    # Find area with highest concentration
    area_scores = []
    for area, warnings in area_warnings.items():
        count = len(warnings)
        depth = area.count(os.sep)
        area_scores.append((-count, depth, area))
    
    area_scores.sort()
    top_area = area_scores[0][2] if area_scores else "."
    
    affected_areas = [top_area]
    
    explanation = (
        f"WARNING files ({warning_count}) exceed 30% of total eligible files ({total_eligible_files}). "
        f"Highest concentration in '{top_area}' with {len(area_warnings[top_area])} WARNING files."
    )
    
    return True, percentage, affected_areas, explanation


def prioritize_findings(findings: List[Finding],
                        aggregate_triggered: bool,
                        aggregate_areas: List[str],
                        aggregate_percentage: float) -> List[Finding]:
    """
    Deterministic prioritization:
    1. CRITICAL findings (file_size >= 300, directory > 15)
    2. HIGH findings (confirmed duplicates, REFACTOR SOON file_size)
    3. MEDIUM findings (likely duplicates, dead_code likely, WARNING file_size)
    4. Aggregate warning areas
    5. LOW findings (suspected issues, INFO)
    """
    prioritized = []
    
    # 1. CRITICAL
    critical = [f for f in findings if _get_severity(f) == "CRITICAL"]
    prioritized.extend(critical)
    
    # 2. HIGH
    high = [f for f in findings if _get_severity(f) == "HIGH"]
    prioritized.extend(high)
    
    # 3. MEDIUM
    medium = [f for f in findings if _get_severity(f) == "MEDIUM"]
    prioritized.extend(medium)
    
    # 4. Aggregate warning areas
    if aggregate_triggered:
        for area in aggregate_areas:
            area_warnings = [f for f in findings 
                           if _get_severity(f) == "MEDIUM" 
                           and _get_category(f) == "file_size"
                           and os.path.dirname(_get_path(f)) == area]
            if area_warnings:
                # Create a summary finding
                summary = Finding.create(
                    category="aggregate_warning",
                    sub_category="area",
                    path=area,
                    severity="MEDIUM",
                    confidence="confirmed",
                    metric=len(area_warnings),
                    threshold=f">{aggregate_percentage:.1f}% WARNING files",
                    action=f"Area has {len(area_warnings)} WARNING files exceeding 30% threshold. Prioritize refactoring here.",
                    evidence=f"Concentration of WARNING files in '{area}'.",
                    detection_method="aggregate_policy",
                )
                prioritized.append(summary)
    
    # 5. LOW
    low = [f for f in findings if _get_severity(f) == "LOW"]
    prioritized.extend(low)
    
    # 6. INFO
    info = [f for f in findings if _get_severity(f) == "INFO"]
    prioritized.extend(info)
    
    return prioritized


class PolicyEngine:
    def __init__(self):
        pass
    
    def evaluate(self, findings: List[Finding], 
                 total_eligible_files: int) -> Dict[str, Any]:
        # Check for CRITICAL violations
        critical_findings = [f for f in findings if _get_severity(f) == "CRITICAL"]
        has_critical = len(critical_findings) > 0
        
        # Check for directory violations
        dir_findings = [f for f in findings if _get_category(f) == "directory"]
        has_dir_violations = len(dir_findings) > 0
        
        # Calculate aggregate warning (only for file_size MEDIUM findings)
        aggregate_triggered, aggregate_percentage, aggregate_areas, aggregate_explanation = \
            calculate_aggregate_warning_policy(findings, total_eligible_files)
        
        # Suppress aggregate if CRITICAL exists (individual critical never hidden)
        if has_critical:
            aggregate_triggered = False
            aggregate_areas = []
            aggregate_explanation = ""
        
        # Prioritize
        prioritized = prioritize_findings(
            findings, aggregate_triggered, aggregate_areas, aggregate_percentage
        )
        
        # Summary by severity
        severity_counts = defaultdict(int)
        category_counts = defaultdict(int)
        for f in findings:
            severity_counts[_get_severity(f)] += 1
            category_counts[_get_category(f)] += 1
        
        return {
            "timestamp": datetime.now().isoformat(),
            "repo_root": "",
            "has_critical_violations": has_critical,
            "has_directory_violations": has_dir_violations,
            "aggregate_warning_triggered": aggregate_triggered,
            "aggregate_warning_percentage": aggregate_percentage,
            "aggregate_areas": aggregate_areas,
            "aggregate_explanation": aggregate_explanation,
            "total_eligible_files": total_eligible_files,
            "prioritized_findings": prioritized,
            "summary": {
                "by_severity": dict(severity_counts),
                "by_category": dict(category_counts),
                "new_findings": 0,  # Filled by report manager
                "resolved_findings": 0,  # Filled by report manager
            },
        }