from pathlib import Path
from typing import Any, Dict, List

from code_hygiene.engine import Finding


SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
SEVERITY_ICONS = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢", "INFO": "🔵"}


def render_terminal_report(policy_result: Dict[str, Any], show_instructions: bool = True) -> str:
    """Render human-readable terminal report."""
    lines = []

    lines.append("\n=== Code Hygiene Scan Results ===")
    lines.append(f"Timestamp: {policy_result.get('timestamp', 'N/A')}")
    lines.append(f"Total eligible files: {policy_result.get('total_eligible_files', 0)}")
    lines.append("")

    summary = policy_result.get("summary", {})
    lines.append("Summary by severity:")
    by_severity = summary.get("by_severity", {})
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
        count = by_severity.get(sev, 0)
        if count > 0:
            icon = SEVERITY_ICONS.get(sev, "")
            lines.append(f"  {icon} {sev}: {count}")

    lines.append("")
    lines.append("Summary by category:")
    cat_summary = summary.get("by_category", {})
    for cat, count in sorted(cat_summary.items()):
        if count > 0:
            lines.append(f"  {cat}: {count}")

    # Baseline info
    baseline = policy_result.get("baseline", {})
    if baseline.get("previous_scan"):
        lines.append("")
        lines.append("Baseline comparison:")
        lines.append(f"  Previous scan: {baseline['previous_scan']}")
        lines.append(f"  Previous total: {baseline['previous_total']}")
        diff = baseline.get("diff", {})
        if diff.get("added"):
            lines.append(f"  New findings: {len(diff['added'])}")
        if diff.get("removed"):
            lines.append(f"  Resolved findings: {len(diff['removed'])}")

    # Critical findings
    findings = policy_result.get("prioritized_findings", [])
    critical_findings = [f for f in findings if f.severity == "CRITICAL"]
    if critical_findings:
        lines.append("")
        lines.append("=== CRITICAL FINDINGS ===")
        for i, f in enumerate(critical_findings, 1):
            lines.append(_format_finding(f, i))

    # Directory violations
    dir_findings = [f for f in findings if f.category == "directory"]
    if dir_findings:
        lines.append("")
        lines.append("=== DIRECTORY VIOLATIONS ===")
        for i, f in enumerate(dir_findings, 1):
            lines.append(_format_finding(f, i))

    # Highest priority targets
    lines.append("")
    lines.append("=== HIGHEST-PRIORITY REFACTORING TARGETS ===")
    top_findings = findings[:10]
    if top_findings:
        for i, f in enumerate(top_findings, 1):
            lines.append(_format_finding(f, i))
    else:
        lines.append("  No issues found. Codebase is healthy!")

    # Aggregate warning
    if policy_result.get("aggregate_warning_triggered"):
        lines.append("")
        lines.append("=== AGGREGATE WARNING ===")
        lines.append(f"  Triggered: {policy_result.get('aggregate_warning_triggered')}")
        lines.append(f"  Percentage: {policy_result.get('aggregate_warning_percentage', 'N/A')}%")
        lines.append(f"  Top area: {policy_result.get('aggregate_top_area', 'N/A')}")
        lines.append(f"  Explanation: {policy_result.get('aggregate_explanation', '')}")

    # New/Resolved findings
    new_findings = policy_result.get("new_findings", [])
    resolved_findings = policy_result.get("resolved_findings", [])
    # Handle both list of findings and integer counts
    new_count = len(new_findings) if isinstance(new_findings, list) else new_findings
    resolved_count = len(resolved_findings) if isinstance(resolved_findings, list) else resolved_findings
    if new_count or resolved_count:
        lines.append("")
        lines.append("=== BASELINE: NEW / RESOLVED ===")
        if new_count:
            lines.append(f"  New findings ({new_count}):")
            if isinstance(new_findings, list):
                for f in new_findings[:5]:
                    lines.append(f"    + {f.path} ({f.category}:{f.sub_category}) [{f.severity}]")
                if len(new_findings) > 5:
                    lines.append(f"    ... and {len(new_findings) - 5} more")
        if resolved_count:
            lines.append(f"  Resolved findings ({resolved_count}):")
            if isinstance(resolved_findings, list):
                for f in resolved_findings[:5]:
                    lines.append(f"    - {f.path} ({f.category}:{f.sub_category})")
                if len(resolved_findings) > 5:
                    lines.append(f"    ... and {len(resolved_findings) - 5} more")

    # AGENT INSTRUCTIONS
    if show_instructions:
        from code_hygiene.output.agent_instructions import generate_agent_instructions
        instructions = generate_agent_instructions(findings, policy_result)
        if instructions:
            lines.append(instructions)

    # Verification recommendations
    lines.append("")
    lines.append("=== VERIFICATION RECOMMENDATIONS ===")
    lines.append("1. Run the relevant test suite for any modified code.")
    lines.append("2. Rerun Code Hygiene after completing changes.")
    lines.append("3. Confirm that new findings are resolved and no new critical findings were introduced.")
    lines.append("4. For 'suspected' findings, inspect evidence manually before acting.")

    lines.append("\n=== End of Report ===\n")

    return "\n".join(lines)


def _format_finding(f: Finding, index: int) -> str:
    icon = SEVERITY_ICONS.get(f.severity, "")
    confidence = f.confidence
    conf_str = f" [{confidence}]" if confidence != "confirmed" else ""
    return f"  {index}. {icon} [{f.severity}] {f.path} (metric: {f.metric}){conf_str}\n     Action: {f.action}\n     Evidence: {f.evidence}"