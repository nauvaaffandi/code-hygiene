import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from code_hygiene.engine.base import Finding, Detector
from code_hygiene.engine.confidence import CONFIRMED, LIKELY, SUSPECTED, UNSUPPORTED
from code_hygiene.ignore import IgnoreEngine


class ChangesChecker(Detector):
    name = "changes"
    supported_languages = ["*"]
    description = "Git-aware change scope analysis"

    def scan(
        self, repo_root: Path, ignore_engine: IgnoreEngine, config: Dict[str, Any]
    ) -> List[Finding]:
        findings: List[Finding] = []

        git_config = config.get("git", {})
        if not git_config.get("enabled", True):
            return findings

        task_description = config.get("task_description", "")

        # Check if we're in a git repo
        git_dir = repo_root / ".git"
        if not git_dir.exists():
            # Not a git repo - skip gracefully
            return findings

        # Get git status
        try:
            status_output = self._run_git(repo_root, ["status", "--porcelain"])
        except (subprocess.CalledProcessError, FileNotFoundError):
            return findings

        # Parse status
        changed_files = self._parse_status(status_output)

        if not changed_files:
            return findings

        # Get diff stats for more detail
        try:
            diff_output = self._run_git(repo_root, ["diff", "--stat"])
        except subprocess.CalledProcessError:
            diff_output = ""

        # Analyze changes
        findings.extend(self._analyze_changes(changed_files, diff_output, task_description, repo_root))

        return findings

    def _run_git(self, repo_root: Path, args: List[str]) -> str:
        result = subprocess.run(
            ["git", "-C", str(repo_root)] + args,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, args, result.stdout, result.stderr)
        return result.stdout

    def _parse_status(self, output: str) -> List[Dict[str, str]]:
        """Parse git status --porcelain output."""
        changes = []
        for line in output.strip().splitlines():
            if not line:
                continue
            status = line[:2]
            path = line[3:].strip()
            changes.append({
                "status": status,
                "path": path,
                "staged": status[0] != " " and status[0] != "?",
                "untracked": status[0] == "?",
            })
        return changes

    def _analyze_changes(
        self,
        changed_files: List[Dict[str, str]],
        diff_output: str,
        task_description: str,
        repo_root: Path,
    ) -> List[Finding]:
        findings: List[Finding] = []

        added = [c for c in changed_files if c["status"][0] == "A" or c["untracked"]]
        modified = [c for c in changed_files if c["status"][0] == "M" or c["status"][1] == "M"]
        deleted = [c for c in changed_files if c["status"][0] == "D"]
        renamed = [c for c in changed_files if c["status"][0] == "R"]

        # Summary finding
        findings.append(
            Finding.create(
                category="changes",
                sub_category="summary",
                path=".",
                severity="INFO",
                confidence=CONFIRMED,
                metric=len(changed_files),
                threshold="git changes detected",
                action="Review the changed files to ensure they align with the intended task scope.",
                evidence=f"Git changes: {len(added)} added, {len(modified)} modified, {len(deleted)} deleted, {len(renamed)} renamed.",
                detection_method="git_status",
                related_paths=[c["path"] for c in changed_files],
            )
        )

        # Check for changes outside task scope
        if task_description:
            scope_findings = self._check_task_scope(changed_files, task_description, repo_root)
            findings.extend(scope_findings)

        # Check for large changes
        if len(changed_files) > 20:
            findings.append(
                Finding.create(
                    category="changes",
                    sub_category="large_change_set",
                    path=".",
                    severity="LOW",
                    confidence=LIKELY,
                    metric=len(changed_files),
                    threshold="> 20 changed files",
                    action="Large number of changes detected. Verify all modifications are related to the current task. "
                           "Consider splitting into smaller, focused changes if appropriate.",
                    evidence=f"Total changed files: {len(changed_files)}. Diff stats:\n{diff_output[:500]}",
                    detection_method="git_diff",
                    related_paths=[c["path"] for c in changed_files],
                )
            )

        return findings

    def _check_task_scope(
        self,
        changed_files: List[Dict[str, str]],
        task_description: str,
        repo_root: Path,
    ) -> List[Finding]:
        findings: List[Finding] = []

        # Extract keywords from task description
        keywords = self._extract_keywords(task_description)

        for change in changed_files:
            path = change["path"]
            # Check if path matches any keyword
            matched = any(kw.lower() in path.lower() for kw in keywords)

            if not matched:
                findings.append(
                    Finding.create(
                        category="changes",
                        sub_category="potentially_unrelated",
                        path=path,
                        severity="LOW",
                        confidence=SUSPECTED,
                        metric=1,
                        threshold="no keyword match in task description",
                        action=f"File '{path}' was modified but doesn't appear related to the task description. "
                               "Verify this change is intentional and related to the current objective.",
                        evidence=f"Modified file '{path}' does not contain keywords from task: {task_description[:100]}",
                        detection_method="task_scope_analysis",
                        related_paths=[path],
                    )
                )

        return findings

    def _extract_keywords(self, text: str) -> List[str]:
        # Simple keyword extraction: words longer than 3 chars, excluding common words
        stop_words = {"the", "and", "for", "with", "from", "that", "this", "will", "have", "been", "were", "your", "when", "into"}
        words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
        return [w for w in words if w not in stop_words]