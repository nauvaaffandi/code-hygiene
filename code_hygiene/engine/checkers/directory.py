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


class DirectoryChecker(Detector):
    name = "directory"
    supported_languages = ["*"]
    description = "Check number of direct child files in directories"

    def scan(
        self, repo_root: Path, ignore_engine: IgnoreEngine, config: Dict[str, Any]
    ) -> List[Finding]:
        dir_config = config.get("directory", {})
        threshold = dir_config.get("threshold", 15)
        count_direct_only = dir_config.get("count_direct_only", True)

        findings: List[Finding] = []

        # Collect all eligible directories (including repo root)
        dirs_to_check = [repo_root]
        for path in repo_root.rglob("*"):
            if path.is_symlink():
                continue
            if path.is_dir() and not ignore_engine.is_ignored(path):
                dirs_to_check.append(path)

        for dir_path in dirs_to_check:
            if dir_path.is_symlink():
                continue

            # Count direct child files
            eligible_count = 0
            eligible_names = []
            try:
                for child in dir_path.iterdir():
                    if child.is_symlink():
                        continue
                    if child.is_file():
                        if not ignore_engine.is_ignored(child) and not is_binary_file(child):
                            eligible_count += 1
                            eligible_names.append(child.name)
            except OSError:
                continue

            if eligible_count > threshold:
                rel_path = "." if dir_path == repo_root else str(dir_path.relative_to(repo_root))
                findings.append(
                    Finding.create(
                        category="directory",
                        sub_category="file_count",
                        path=rel_path,
                        severity="CRITICAL",
                        confidence="confirmed",
                        metric=eligible_count,
                        threshold=f"> {threshold} eligible files",
                        action="Refactor directory structure to distribute files into meaningful subdirectories. Group by responsibility.",
                        evidence=f"Directory contains {eligible_count} eligible files: {', '.join(eligible_names[:10])}{'...' if len(eligible_names) > 10 else ''}",
                        detection_method="direct_child_count",
                    )
                )

        return findings