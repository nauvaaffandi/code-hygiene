from pathlib import Path
from typing import Any, Dict, List

from code_hygiene.engine import Finding


PRIORITY_ORDER = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
    "INFO": 4,
}

CATEGORY_LABELS = {
    "file_size": "FILE SIZE",
    "directory": "DIRECTORY STRUCTURE",
    "duplicate": "DUPLICATE IMPLEMENTATION",
    "dead_code": "UNUSED CODE / DEAD CODE",
    "abstraction": "ABSTRACTION / FILE PROLIFERATION",
    "generation": "GENERATED FILES & DEPENDENCIES",
    "changes": "CHANGE SCOPE",
}


def generate_agent_instructions(findings: List[Finding], policy_result: Dict[str, Any]) -> str:
    """Generate the AGENT INSTRUCTIONS section from findings."""
    if not findings:
        return ""

    # Group findings by priority
    priority_groups = {}
    for f in findings:
        sev = f.severity
        priority = PRIORITY_ORDER.get(sev, 5)
        priority_groups.setdefault(priority, []).append(f)

    # Sort by priority
    sorted_priorities = sorted(priority_groups.keys())

    lines = ["\n=== AGENT INSTRUCTIONS ==="]

    priority_num = 1
    for priority in sorted_priorities:
        group = priority_groups[priority]
        if not group:
            continue

        # Determine the category label for this priority
        primary_finding = group[0]
        category_label = CATEGORY_LABELS.get(primary_finding.category, primary_finding.category.upper())

        lines.append(f"\nPriority {priority_num} — {primary_finding.severity}")
        lines.append(f"Category: {category_label}")
        lines.append("")

        for f in group:
            # Issue with confidence
            confidence_str = f" [{f.confidence.upper()}]" if f.confidence != "confirmed" else " [CONFIRMED]"
            lines.append(f"Issue: {f.evidence}{confidence_str}")

            # Affected with location
            lines.append(f"Affected: {f.path}")

            # Why
            why = _generate_why(f)
            lines.append(f"Why: {why}")

            # Action
            lines.append("Required action:")
            for action_line in f.action.split(". "):
                if action_line.strip():
                    lines.append(f"  - {action_line.strip()}.")

            # Constraints
            constraints = _generate_constraints(f)
            if constraints:
                lines.append("Constraints:")
                for c in constraints:
                    lines.append(f"  - {c}")

            # Verification
            verification = _generate_verification(f)
            lines.append(f"Verification: {verification}")

            lines.append("")

        priority_num += 1

    return "\n".join(lines)


def _generate_why(finding: Finding) -> str:
    """Generate 'why' explanation for a finding."""
    category = finding.category
    if category == "file_size":
        return f"Files exceeding {finding.threshold} are harder to understand, test, and maintain. They often indicate mixed responsibilities."
    elif category == "directory":
        return f"Directories with more than 15 files reduce discoverability and make it difficult to locate related code."
    elif category == "duplicate":
        return "Duplicate implementations increase maintenance burden and risk of inconsistencies. Changes must be applied in multiple places."
    elif category == "dead_code":
        return "Unused code creates confusion, increases cognitive load, and may indicate incomplete refactoring or missing tests. However, code may be used via dynamic imports, reflection, or framework conventions not visible to static analysis."
    elif category == "abstraction":
        return "Excessive abstractions or file proliferation without clear benefit adds complexity without value. Verify the abstraction provides genuine separation of concerns."
    elif category == "generation":
        return "Generated files should not be edited directly. Unused dependencies increase build time and attack surface."
    elif category == "changes":
        return "Changes outside the stated task scope may indicate scope creep or unintended modifications."
    else:
        return "This finding indicates a potential code quality issue that should be investigated."


def _generate_constraints(finding: Finding) -> List[str]:
    """Generate constraints for a finding."""
    constraints = [
        "Preserve existing behavior and public interfaces.",
        "Run relevant tests after any modification.",
        "Do not modify code solely to satisfy a numerical threshold.",
        "Rerun Code Hygiene after changes to confirm resolution.",
    ]

    if finding.category == "file_size":
        constraints.append("Do not split code into meaningless modules just to reduce line count.")
        constraints.append("Extract cohesive responsibilities only; avoid creating files that merely delegate.")
    elif finding.category == "directory":
        constraints.append("Do not create arbitrary subdirectories just to satisfy the file count threshold.")
        constraints.append("Group files by genuine functional area, not arbitrarily.")
    elif finding.category == "duplicate":
        constraints.append("Preserve intentional differences. Only consolidate when responsibilities are genuinely equivalent.")
        constraints.append("Compare behavior, inputs, outputs, and call sites before merging.")
        if finding.confidence in ("suspected", "unsupported"):
            constraints.append("This is a heuristic match — manually verify the implementations are truly equivalent.")
    elif finding.category == "dead_code":
        constraints.append("Do not delete code marked as 'suspected' or 'likely' without verifying it is truly unused.")
        constraints.append("Check for dynamic imports, reflection, plugin systems, framework entry points, and test fixtures.")
        constraints.append("Verify no external consumers depend on this code before removal.")
    elif finding.category == "abstraction":
        constraints.append("Verify the abstraction adds value (validation, logging, transformation) before removing.")
        constraints.append("Do not inline code that provides meaningful interface separation.")
    elif finding.category == "generation":
        constraints.append("Do not edit generated files directly; modify the generator instead.")
        constraints.append("Verify dependency is not a transitive or build-time requirement before removing.")
    elif finding.category == "changes":
        constraints.append("Do not revert changes that are part of the intended task scope.")
        constraints.append("Verify unrelated modifications are intentional before including them.")

    return constraints


def _generate_verification(finding: Finding) -> str:
    """Generate verification steps for a finding."""
    category = finding.category
    if category == "file_size":
        return "Run tests for the affected file and its callers; rerun Code Hygiene and confirm the file's severity is reduced."
    elif category == "directory":
        return "Verify imports and references still work after restructuring; rerun Code Hygiene and confirm directory is within threshold."
    elif category == "duplicate":
        return "Run tests for both implementations and all call sites; verify behavior is identical; rerun Code Hygiene to confirm duplicate is resolved."
    elif category == "dead_code":
        return "Run full test suite including integration tests; verify no dynamic loading or plugin systems break; check for external API consumers; rerun Code Hygiene."
    elif category == "abstraction":
        return "Run tests; verify behavior unchanged and interfaces preserved; rerun Code Hygiene."
    elif category == "generation":
        return "If removing dependency, run tests and verify build succeeds; if modifying generated file, update generator instead; rerun Code Hygiene."
    elif category == "changes":
        return "Review diff against task requirements; verify all changes are intentional and no unintended files were modified."
    else:
        return "Run relevant tests; rerun Code Hygiene to confirm resolution."