from pathlib import Path
from typing import Any, Dict, List

from code_hygiene.engine.base import Finding, Detector
from code_hygiene.ignore import IgnoreEngine


def is_binary_file(file_path: Path, chunk_size: int = 1024) -> bool:
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(chunk_size)
            if not chunk:
                return False
            if b"\x00" in chunk:
                return True
            return False
    except OSError:
        return True


def count_lines(file_path: Path) -> int:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


class FileSizeChecker(Detector):
    name = "file_size"
    supported_languages = ["*"]
    description = "Check physical line count of source files"

    def scan(
        self, repo_root: Path, ignore_engine: IgnoreEngine, config: Dict[str, Any]
    ) -> List[Finding]:
        fs_config = config.get("file_size", {})
        warning = fs_config.get("warning", 200)
        refactor_soon = fs_config.get("refactor_soon", 250)
        critical = fs_config.get("critical", 300)

        findings: List[Finding] = []

        for path in repo_root.rglob("*"):
            if path.is_symlink():
                continue
            if not path.is_file():
                continue
            if ignore_engine.is_ignored(path):
                continue
            if is_binary_file(path):
                continue

            lines = count_lines(path)
            rel_path = str(path.relative_to(repo_root))

            if lines >= critical:
                severity = "CRITICAL"
                action = "Refactoring is mandatory. Identify cohesive responsibilities and extract them while preserving behavior."
            elif lines >= refactor_soon:
                severity = "HIGH"
                action = "Prioritize refactoring. Inspect responsibilities and extract meaningful modules."
            elif lines >= warning:
                severity = "MEDIUM"
                action = "Avoid adding complex logic. Plan refactoring before expanding this file."
            else:
                continue  # SAFE - no finding

            findings.append(
                Finding.create(
                    category="file_size",
                    sub_category="lines",
                    path=rel_path,
                    severity=severity,
                    confidence="confirmed",
                    metric=lines,
                    threshold=f">= {warning} (warning), >= {refactor_soon} (refactor soon), >= {critical} (critical)",
                    action=action,
                    evidence=f"Physical line count of {lines}, including blank and comment lines.",
                    detection_method="physical_line_count",
                )
            )

        return findings