import fnmatch
import os
from pathlib import Path
from typing import List, Optional


DEFAULT_IGNORE_PATTERNS = [
    ".git/",
    "node_modules/",
    "venv/",
    ".env/",
    "vendor/",
    "dist/",
    "build/",
    "*.pyc",
    "__pycache__/",
    "*.o",
    "*.so",
    "*.dylib",
    "*.dll",
    ".vscode/",
    ".idea/",
    "*.swp",
    "*.swo",
    "*~",
    ".DS_Store",
    "Thumbs.db",
    ".code-hygiene/",
    "*.log",
    "*.tar.gz",
    "*.zip",
    "*.tar",
    "*.rar",
]


class IgnoreEngine:
    def __init__(self, repo_root: Path, ignore_file: Optional[Path] = None):
        self.repo_root = repo_root.resolve()
        self.patterns: List[str] = []
        self._load_patterns(ignore_file)

    def _load_patterns(self, ignore_file: Optional[Path]) -> None:
        self.patterns = DEFAULT_IGNORE_PATTERNS.copy()
        if ignore_file and ignore_file.exists():
            try:
                content = ignore_file.read_text(encoding="utf-8")
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        self.patterns.append(line)
            except OSError:
                pass

    def _match_pattern(self, path: Path, pattern: str) -> bool:
        rel_path = str(path.relative_to(self.repo_root))
        rel_path_with_slash = rel_path + "/"
        
        if pattern.endswith("/"):
            pattern_dir = pattern.rstrip("/")
            if pattern.startswith("/"):
                pattern_dir = pattern_dir[1:]
                return fnmatch.fnmatch(rel_path, pattern_dir) or fnmatch.fnmatch(rel_path, pattern_dir + "/*")
            return (fnmatch.fnmatch(rel_path, pattern_dir) or
                    fnmatch.fnmatch(rel_path, pattern_dir + "/*") or
                    fnmatch.fnmatch(rel_path_with_slash, "**/" + pattern) or
                    fnmatch.fnmatch(rel_path, "**/" + pattern_dir) or
                    fnmatch.fnmatch(rel_path, "**/" + pattern_dir + "/*"))
        
        if pattern.startswith("/"):
            pattern = pattern[1:]
            return fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(rel_path + "/", pattern + "/*")
        
        return (fnmatch.fnmatch(rel_path, pattern) or
                fnmatch.fnmatch(rel_path + "/", pattern + "/*") or
                fnmatch.fnmatch(path.name, pattern) or
                fnmatch.fnmatch(rel_path, "**/" + pattern) or
                fnmatch.fnmatch(rel_path, "**/" + pattern + "/*"))

    def is_ignored(self, path: Path) -> bool:
        try:
            path = path.resolve()
            if not path.is_relative_to(self.repo_root):
                return True
        except (ValueError, OSError):
            return True

        # Check path itself and all parent directories up to repo_root
        current = path
        while current != self.repo_root:
            for pattern in self.patterns:
                if self._match_pattern(current, pattern):
                    return True
            current = current.parent
            if current == current.parent:
                break
                
        return False

    def filter_paths(self, paths: List[Path]) -> List[Path]:
        return [p for p in paths if not self.is_ignored(p)]