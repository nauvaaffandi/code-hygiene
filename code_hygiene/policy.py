import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


SEVERITY_ORDER = {
    "CRITICAL": 0,
    "REFACTOR SOON": 1,
    "WARNING": 2,
    "SAFE": 3
}

CATEGORY_ORDER = {
    "file_size": 0,
    "directory_file_count": 1
}


def calculate_aggregate_warning_policy(file_findings: List[Dict[str, Any]], 
                                       total_eligible_files: int) -> Tuple[bool, List[str], str]:
    """
    Returns (triggered, affected_areas, explanation)
    """
    if total_eligible_files == 0:
        return False, [], ""
    
    warning_files = [f for f in file_findings if f.get("severity") == "WARNING"]
    warning_count = len(warning_files)
    
    if warning_count / total_eligible_files <= 0.30:
        return False, [], ""
    
    # Group WARNING files by their parent directory (or logical area)
    area_warnings = defaultdict(list)
    for f in warning_files:
        path = f["path"]
        # Get the parent directory as the area
        area = os.path.dirname(path)
        if not area:
            area = "."
        area_warnings[area].append(f)
    
    # Find area with highest concentration of WARNING files
    # Primary: highest count, Secondary: highest density (warnings / total files in area)
    area_scores = []
    for area, warnings in area_warnings.items():
        count = len(warnings)
        # Calculate density - need to know total files in this area
        # For simplicity, we'll use the count of WARNING files as primary
        # and the area depth as secondary (prefer deeper/shorter paths)
        depth = area.count(os.sep)
        area_scores.append((-count, depth, area))
    
    area_scores.sort()
    top_area = area_scores[0][2] if area_scores else "."
    
    affected_areas = [top_area]
    
    explanation = (
        f"WARNING files ({warning_count}) exceed 30% of total eligible files ({total_eligible_files}). "
        f"Highest concentration in '{top_area}' with {len(area_warnings[top_area])} WARNING files."
    )
    
    return True, affected_areas, explanation


def prioritize_findings(file_findings: List[Dict[str, Any]], 
                        dir_findings: List[Dict[str, Any]],
                        aggregate_triggered: bool,
                        aggregate_areas: List[str]) -> List[Dict[str, Any]]:
    """
    Deterministic prioritization:
    1. CRITICAL files (300+ lines)
    2. Directories with >15 files
    3. REFACTOR SOON files (250-299 lines)
    4. Areas affected by aggregate WARNING policy
    5. Individual WARNING files (200-249 lines)
    """
    prioritized = []
    
    # 1. CRITICAL files
    critical_files = [f for f in file_findings if f.get("severity") == "CRITICAL"]
    prioritized.extend(critical_files)
    
    # 2. Over-limit directories
    prioritized.extend(dir_findings)
    
    # 3. REFACTOR SOON files
    refactor_soon_files = [f for f in file_findings if f.get("severity") == "REFACTOR SOON"]
    prioritized.extend(refactor_soon_files)
    
    # 4. Aggregate WARNING areas
    if aggregate_triggered:
        # Add area findings
        for area in aggregate_areas:
            area_warnings = [f for f in file_findings 
                           if f.get("severity") == "WARNING" 
                           and (os.path.dirname(f["path"]) or ".") == area]
            # Add a summary finding for the area
            prioritized.append({
                "path": area,
                "category": "aggregate_warning",
                "metric": len(area_warnings),
                "severity": "WARNING",
                "action": f"Area has {len(area_warnings)} WARNING files exceeding 30% threshold. Prioritize refactoring here.",
                "threshold": ">30% WARNING files"
            })
    
    # 5. Individual WARNING files (not in aggregate areas)
    warning_files = [f for f in file_findings if f.get("severity") == "WARNING"]
    # Filter out those already covered by aggregate areas
    for f in warning_files:
        if aggregate_triggered and (os.path.dirname(f["path"]) or ".") in aggregate_areas:
            continue
        prioritized.append(f)
    
    return prioritized


class PolicyEngine:
    def __init__(self):
        pass
    
    def evaluate(self, file_findings: List[Dict[str, Any]], 
                 dir_findings: List[Dict[str, Any]],
                 total_eligible_files: int) -> Dict[str, Any]:
        # Check for CRITICAL file violations
        critical_files = [f for f in file_findings if f.get("severity") == "CRITICAL"]
        has_critical = len(critical_files) > 0
        
        # Check for directory violations
        has_dir_violations = len(dir_findings) > 0
        
        # Calculate aggregate warning
        aggregate_triggered, aggregate_areas, aggregate_explanation = calculate_aggregate_warning_policy(
            file_findings, total_eligible_files
        )
        
        # Prioritize
        prioritized = prioritize_findings(
            file_findings, dir_findings, aggregate_triggered, aggregate_areas
        )
        
        return {
            "timestamp": datetime.now().isoformat(),
            "has_critical_violations": has_critical,
            "has_directory_violations": has_dir_violations,
            "aggregate_warning_triggered": aggregate_triggered,
            "aggregate_areas": aggregate_areas,
            "aggregate_explanation": aggregate_explanation,
            "total_eligible_files": total_eligible_files,
            "prioritized_findings": prioritized,
            "summary": {
                "critical_files": len(critical_files),
                "over_limit_directories": len(dir_findings),
                "refactor_soon_files": len([f for f in file_findings if f.get("severity") == "REFACTOR SOON"]),
                "warning_files": len([f for f in file_findings if f.get("severity") == "WARNING"]),
                "safe_files": total_eligible_files - len(file_findings)
            }
        }