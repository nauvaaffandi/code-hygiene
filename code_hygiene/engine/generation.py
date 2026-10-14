import ast
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from code_hygiene.engine.base import Finding, Detector
from code_hygiene.engine.confidence import CONFIRMED, LIKELY, SUSPECTED, UNSUPPORTED
from code_hygiene.ignore import IgnoreEngine


class AbstractionChecker(Detector):
    name = "abstraction"
    supported_languages = ["python"]
    description = "Detect suspicious abstraction patterns: wrapper layers, one-function modules, excessive interfaces"

    def scan(
        self, repo_root: Path, ignore_engine: IgnoreEngine, config: Dict[str, Any]
    ) -> List[Finding]:
        findings: List[Finding] = []

        if "python" not in config.get("abstractions", {}).get("support", ["python"]):
            return findings

        # Collect Python files
        py_files = []
        for path in repo_root.rglob("*.py"):
            if path.is_symlink():
                continue
            if ignore_engine.is_ignored(path):
                continue
            py_files.append(path)

        # Check one-function modules
        findings.extend(self._check_one_function_modules(py_files, repo_root))

        # Check wrapper layers
        findings.extend(self._check_wrapper_layers(py_files, repo_root))

        # Check excessive interfaces
        findings.extend(self._check_excessive_interfaces(py_files, repo_root, config))

        return findings

    def _check_one_function_modules(self, py_files: List[Path], repo_root: Path) -> List[Finding]:
        findings: List[Finding] = []

        for path in py_files:
            try:
                source = path.read_text(encoding="utf-8")
            except OSError:
                continue

            rel_path = str(path.relative_to(repo_root))

            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            # Count top-level function/class definitions
            definitions = []
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    definitions.append((node.__class__.__name__, node.name))

            if len(definitions) == 1:
                def_type, def_name = definitions[0]
                # Check if there's a docstring or significant comments
                has_docstring = bool(ast.get_docstring(tree))

                confidence = LIKELY if not has_docstring else SUSPECTED
                findings.append(
                    Finding.create(
                        category="abstraction",
                        sub_category="one_function_module",
                        path=rel_path,
                        severity="LOW",
                        confidence=confidence,
                        metric=1,
                        threshold="single top-level definition",
                        action="Assess whether this module provides meaningful organization or merely renames/delegates. "
                               "Consider inlining if it only forwards calls to another implementation.",
                        evidence=f"Module contains exactly one {def_type.lower()} '{def_name}' with {'no' if not has_docstring else 'a'} docstring.",
                        detection_method="ast_analysis",
                        related_paths=[rel_path],
                    )
                )

        return findings

    def _check_wrapper_layers(self, py_files: List[Path], repo_root: Path) -> List[Finding]:
        findings: List[Finding] = []

        for path in py_files:
            try:
                source = path.read_text(encoding="utf-8")
            except OSError:
                continue

            rel_path = str(path.relative_to(repo_root))

            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Check if function body is a single return statement calling another function
                    if len(node.body) == 1 and isinstance(node.body[0], ast.Return):
                        return_stmt = node.body[0]
                        if isinstance(return_stmt.value, ast.Call):
                            # Check if it's a simple pass-through (same args or subset)
                            findings.append(
                                Finding.create(
                                    category="abstraction",
                                    sub_category="wrapper_layer",
                                    path=f"{rel_path}:{node.name}",
                                    severity="LOW",
                                    confidence=SUSPECTED,
                                    metric=node.lineno,
                                    threshold="single pass-through return",
                                    action="Determine if this wrapper adds value (validation, logging, transformation) or merely forwards calls. "
                                           "Consider removing if it adds no meaningful behavior.",
                                    evidence=f"Function '{node.name}' at line {node.lineno} only returns the result of another function call.",
                                    detection_method="ast_analysis",
                                    related_paths=[rel_path],
                                )
                            )

        return findings

    def _check_excessive_interfaces(self, py_files: List[Path], repo_root: Path, config: Dict[str, Any]) -> List[Finding]:
        findings: List[Finding] = []
        max_interfaces = config.get("abstractions", {}).get("max_interfaces_per_class", 10)

        # Group by directory
        dir_files: Dict[str, List[Path]] = {}
        for path in py_files:
            dir_path = str(path.parent.relative_to(repo_root))
            dir_files.setdefault(dir_path, []).append(path)

        for dir_path, files in dir_files.items():
            if len(files) < 2:
                continue

            class_count = 0
            interface_count = 0

            for path in files:
                try:
                    source = path.read_text(encoding="utf-8")
                    tree = ast.parse(source)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            class_count += 1
                            # Check if it's an abstract base or interface-like
                            if any(isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant) and b.value.value == "ABC" for b in node.bases):
                                interface_count += 1
                            elif all(isinstance(n, ast.FunctionDef) and not n.body for n in node.body):
                                # All methods are abstract (no body)
                                interface_count += 1
                except (OSError, SyntaxError):
                    continue

            if class_count > 0 and interface_count > max_interfaces:
                findings.append(
                    Finding.create(
                        category="abstraction",
                        sub_category="excessive_interfaces",
                        path=dir_path,
                        severity="LOW",
                        confidence=SUSPECTED,
                        metric=interface_count,
                        threshold=f"> {max_interfaces} interfaces per {class_count} classes",
                        action="Review if the number of interfaces/abstract classes is justified by genuine domain boundaries "
                               "or if consolidation would simplify the architecture.",
                        evidence=f"Directory '{dir_path}' has {interface_count} interface-like classes for {class_count} total classes.",
                        detection_method="ast_analysis",
                        related_paths=[str(f.relative_to(repo_root)) for f in files],
                    )
                )

        return findings


class GenerationChecker(Detector):
    name = "generation"
    supported_languages = ["*"]
    description = "Detect generated files and unused dependencies"

    def scan(
        self, repo_root: Path, ignore_engine: IgnoreEngine, config: Dict[str, Any]
    ) -> List[Finding]:
        findings: List[Finding] = []

        # Check generated files
        findings.extend(self._check_generated_files(repo_root, ignore_engine, config))

        # Check dependency auditing
        findings.extend(self._check_dependencies(repo_root, ignore_engine, config))

        return findings

    def _check_generated_files(self, repo_root: Path, ignore_engine: IgnoreEngine, config: Dict[str, Any]) -> List[Finding]:
        findings: List[Finding] = []
        patterns = config.get("generation", {}).get("patterns", [])

        for path in repo_root.rglob("*"):
            if path.is_symlink():
                continue
            if ignore_engine.is_ignored(path):
                continue
            if not path.is_file():
                continue

            rel_path = str(path.relative_to(repo_root))
            matched = False

            for pattern in patterns:
                if self._match_pattern(rel_path, pattern):
                    matched = True
                    break

            if matched:
                findings.append(
                    Finding.create(
                        category="generation",
                        sub_category="generated_file",
                        path=rel_path,
                        severity="INFO",
                        confidence=LIKELY,
                        metric=1,
                        threshold="matches generated pattern",
                        action="Verify this is a generated file. Do not edit generated files directly; modify the generator instead. "
                               "Ensure generated files are in .ignore to avoid false positives in other checks.",
                        evidence=f"File matches generated pattern: {pattern}",
                        detection_method="pattern_match",
                        related_paths=[rel_path],
                    )
                )

        return findings

    def _check_dependencies(self, repo_root: Path, ignore_engine: IgnoreEngine, config: Dict[str, Any]) -> List[Finding]:
        findings: List[Finding] = []

        # Check requirements.txt
        req_file = repo_root / "requirements.txt"
        if req_file.exists() and not ignore_engine.is_ignored(req_file):
            findings.extend(self._check_python_deps(req_file, repo_root, ignore_engine))

        # Check package.json
        pkg_file = repo_root / "package.json"
        if pkg_file.exists() and not ignore_engine.is_ignored(pkg_file):
            findings.extend(self._check_js_deps(pkg_file, repo_root, ignore_engine))

        # Check go.mod
        go_file = repo_root / "go.mod"
        if go_file.exists() and not ignore_engine.is_ignored(go_file):
            findings.extend(self._check_go_deps(go_file, repo_root, ignore_engine))

        return findings

    def _check_python_deps(self, req_file: Path, repo_root: Path, ignore_engine: IgnoreEngine) -> List[Finding]:
        findings: List[Finding] = []
        try:
            content = req_file.read_text(encoding="utf-8")
        except OSError:
            return findings

        # Parse dependencies
        deps = []
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                # Extract package name (before version specifiers)
                pkg = re.split(r"[=<>!~]", line)[0].strip()
                if pkg:
                    deps.append(pkg)

        # Find all Python imports in the repo
        imports = set()
        for path in repo_root.rglob("*.py"):
            if path.is_symlink() or ignore_engine.is_ignored(path):
                continue
            try:
                source = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for match in re.finditer(r"^\s*(?:import|from)\s+([\w.]+)", source, re.MULTILINE):
                imports.add(match.group(1).split(".")[0])

        # Check for unused deps
        for dep in deps:
            if dep.lower() not in {i.lower() for i in imports}:
                findings.append(
                    Finding.create(
                        category="generation",
                        sub_category="unused_dependency",
                        path=str(req_file.relative_to(repo_root)),
                        severity="LOW",
                        confidence=SUSPECTED,
                        metric=1,
                        threshold="declared but not imported",
                        action="Verify if this dependency is truly unused. It may be used dynamically, as a transitive dependency, "
                               "or for side effects. Remove only if confirmed unnecessary.",
                        evidence=f"Dependency '{dep}' declared in requirements.txt but not found in import statements.",
                        detection_method="dependency_audit",
                        related_paths=[str(req_file.relative_to(repo_root))],
                    )
                )

        return findings

    def _check_js_deps(self, pkg_file: Path, repo_root: Path, ignore_engine: IgnoreEngine) -> List[Finding]:
        findings: List[Finding] = []
        try:
            content = json.loads(pkg_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return findings

        deps = {**content.get("dependencies", {}), **content.get("devDependencies", {})}

        # Find all JS/TS imports
        imports = set()
        for path in repo_root.rglob("*.js"):
            if path.is_symlink() or ignore_engine.is_ignored(path):
                continue
            try:
                source = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for match in re.finditer(r"from\s+[\"']([^\"']+)[\"']", source):
                imports.add(match.group(1).split("/")[0])
            for match in re.finditer(r"require\([\"']([^\"']+)[\"']\)", source):
                imports.add(match.group(1).split("/")[0])

        for dep in deps:
            if dep not in imports and not dep.startswith("."):
                findings.append(
                    Finding.create(
                        category="generation",
                        sub_category="unused_dependency",
                        path=str(pkg_file.relative_to(repo_root)),
                        severity="LOW",
                        confidence=SUSPECTED,
                        metric=1,
                        threshold="declared but not imported",
                        action="Verify if this dependency is truly unused. Check for peer dependencies, transitive deps, or build-time only packages.",
                        evidence=f"Dependency '{dep}' declared in package.json but not found in import statements.",
                        detection_method="dependency_audit",
                        related_paths=[str(pkg_file.relative_to(repo_root))],
                    )
                )

        return findings

    def _check_go_deps(self, go_file: Path, repo_root: Path, ignore_engine: IgnoreEngine) -> List[Finding]:
        findings: List[Finding] = []
        try:
            content = go_file.read_text(encoding="utf-8")
        except OSError:
            return findings

        # Parse go.mod for requires
        deps = []
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("require") or (line and not line.startswith("//") and "github.com/" in line):
                parts = line.split()
                if len(parts) >= 2 and "github.com/" in parts[0]:
                    deps.append(parts[0])

        # Find all Go imports
        imports = set()
        for path in repo_root.rglob("*.go"):
            if path.is_symlink() or ignore_engine.is_ignored(path):
                continue
            try:
                source = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for match in re.finditer(r'import\s+\(([\s\S]*?)\)', source):
                for line in match.group(1).splitlines():
                    line = line.strip().strip('"')
                    if line and "/" in line:
                        imports.add(line.split("/")[0])
            for match in re.finditer(r'import\s+"([^"]+)"', source):
                imports.add(match.group(1).split("/")[0])

        for dep in deps:
            dep_name = dep.split("/")[-1]
            if dep_name not in imports:
                findings.append(
                    Finding.create(
                        category="generation",
                        sub_category="unused_dependency",
                        path=str(go_file.relative_to(repo_root)),
                        severity="LOW",
                        confidence=SUSPECTED,
                        metric=1,
                        threshold="declared but not imported",
                        action="Verify if this Go module is truly unused. Check for build tags, test files, or transitive dependencies.",
                        evidence=f"Module '{dep}' declared in go.mod but not found in import statements.",
                        detection_method="dependency_audit",
                        related_paths=[str(go_file.relative_to(repo_root))],
                    )
                )

        return findings

    def _match_pattern(self, path: str, pattern: str) -> bool:
        import fnmatch
        return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, f"*/{pattern}")