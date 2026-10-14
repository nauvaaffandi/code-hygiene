import os
from pathlib import Path
from typing import Dict, List, Tuple, Any

from code_hygiene.ignore import IgnoreEngine


def is_binary_file(file_path: Path, chunk_size: int = 1024) -> bool:
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(chunk_size)
            if not chunk:
                return False
            if b"\x00" in chunk:
                return True
            # Check for high ratio of non-text bytes if needed, but null byte is standard
            return False
    except OSError:
        return True


def count_lines(file_path: Path) -> int:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def classify_file(line_count: int) -> Tuple[str, str]:
    if line_count < 200:
        return "SAFE", "No action required."
    elif 200 <= line_count <= 249:
        return "WARNING", "Avoid adding complex logic or heavy functionality to the file."
    elif 250 <= line_count <= 299:
        return "REFACTOR SOON", "Prioritize refactoring the file as soon as reasonably possible."
    else:
        return "CRITICAL", "Refactoring is mandatory."


class FileSizeChecker:
    def __init__(self, repo_root: Path, ignore_engine: IgnoreEngine):
        self.repo_root = repo_root.resolve()
        self.ignore_engine = ignore_engine

    def scan(self) -> List[Dict[str, Any]]:
        findings = []
        for path in self.repo_root.rglob("*"):
            # Skip symlinks to avoid infinite recursion or scanning outside
            if path.is_symlink():
                continue
            if path.is_file():
                if self.ignore_engine.is_ignored(path):
                    continue
                if is_binary_file(path):
                    continue
                
                lines = count_lines(path)
                severity, action = classify_file(lines)
                
                if severity == "SAFE":
                    continue

                rel_path = str(path.relative_to(self.repo_root))
                findings.append({
                    "path": rel_path,
                    "category": "file_size",
                    "metric": lines,
                    "severity": severity,
                    "action": action,
                    "threshold": ">=200 (warning), >=250 (refactor soon), >=300 (critical)"
                })
        return findings


class DirectoryChecker:
    def __init__(self, repo_root: Path, ignore_engine: IgnoreEngine, threshold: int = 15):
        self.repo_root = repo_root.resolve()
        self.ignore_engine = ignore_engine
        self.threshold = threshold

    def scan(self) -> List[Dict[str, Any]]:
        findings = []
        
        # Traverse directories recursively
        for dir_path in [self.repo_root] + [p for p in self.repo_root.rglob("*") if p.is_dir() and not p.is_symlink()]:
            if self.ignore_engine.is_ignored(dir_path):
                continue
                
            if dir_path.is_symlink():
                continue

            # Count direct child files that are eligible (not ignored, not symlinks, not binary)
            eligible_count = 0
            try:
                for child in dir_path.iterdir():
                    if child.is_symlink():
                        continue
                    if child.is_file():
                        if not self.ignore_engine.is_ignored(child) and not is_binary_file(child):
                            eligible_count += 1
            except OSError:
                continue

            if eligible_count > self.threshold:
                rel_path = "." if dir_path == self.repo_root else str(dir_path.relative_to(self.repo_root))
                findings.append({
                    "path": rel_path,
                    "category": "directory_file_count",
                    "metric": eligible_count,
                    "severity": "CRITICAL",
                    "action": "Refactor directory structure to distribute files into meaningful subdirectories.",
                    "threshold": f"> {self.threshold} eligible files"
                })
                
        return findings
