import ast
import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from code_hygiene.engine.base import Finding, Detector
from code_hygiene.engine.confidence import CONFIRMED, LIKELY, SUSPECTED, is_actionable
from code_hygiene.ignore import IgnoreEngine


def normalize_code(source: str) -> str:
    """Normalize source code for comparison: strip comments/strings/blanks, collapse whitespace."""
    # Remove single-line comments
    source = re.sub(r"#.*$", "", source, flags=re.MULTILINE)
    # Remove multi-line comments (docstrings not removed here; AST handles them)
    source = re.sub(r'"""[\s\S]*?"""', "", source, flags=re.DOTALL)
    source = re.sub(r"'''[\s\S]*?'''", "", source, flags=re.DOTALL)
    # Normalize string literals
    source = re.sub(r'"[^"*]*"', ' "<STR>" ', source)
    source = re.sub(r"'[^']*'", ' "<STR>" ', source)
    # Normalize numbers
    source = re.sub(r"\d+", ' <NUM> ', source)
    # Collapse whitespace
    source = re.sub(r"\s+", " ", source)
    return source.strip()


def tokenize(text: str) -> set:
    return set(text.split())


def jaccard_similarity(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _build_qualified_name(node: ast.AST, scope_stack: List[str]) -> str:
    """Build a fully qualified name including enclosing scopes."""
    parts = scope_stack + [node.name]
    return ".".join(parts)


class _BlockExtractor(ast.NodeVisitor):
    """AST visitor that extracts code blocks with fully qualified names."""
    
    def __init__(self, source: str):
        self.source = source
        self.blocks: List[Tuple[str, int, int, str, str]] = []  # (qualified_name, start_line, end_line, block_src, simple_name)
        self.scope_stack: List[str] = []
    
    def visit_ClassDef(self, node: ast.ClassDef):
        start_line = getattr(node, "lineno", 0)
        end_line = max(getattr(n, "lineno", start_line) for n in ast.walk(node))
        try:
            block_src = "\n".join(self.source.splitlines()[start_line - 1:end_line])
        except IndexError:
            self.generic_visit(node)
            return
        
        qualified_name = _build_qualified_name(node, self.scope_stack)
        self.blocks.append((qualified_name, start_line, end_line, block_src, node.name))
        
        # Enter class scope
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._visit_function(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._visit_function(node)
    
    def _visit_function(self, node: ast.FunctionDef):
        start_line = getattr(node, "lineno", 0)
        end_line = max(getattr(n, "lineno", start_line) for n in ast.walk(node))
        try:
            block_src = "\n".join(self.source.splitlines()[start_line - 1:end_line])
        except IndexError:
            self.generic_visit(node)
            return
        
        qualified_name = _build_qualified_name(node, self.scope_stack)
        self.blocks.append((qualified_name, start_line, end_line, block_src, node.name))
        
        # Enter function scope
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()


def extract_blocks_python(source: str) -> List[Tuple[str, int, int, str, str]]:
    """Extract code blocks (functions/classes) from Python source with line numbers.
    
    Returns list of tuples: (qualified_name, start_line, end_line, block_src, simple_name)
    """
    extractor = _BlockExtractor(source)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    extractor.visit(tree)
    return extractor.blocks


def compare_blocks(block_a: Tuple[str, int, int, str, str], block_b: Tuple[str, int, int, str, str], threshold: float) -> Tuple[bool, float]:
    """Compare two blocks; return (match, similarity)."""
    norm_a = normalize_code(block_a[3])
    norm_b = normalize_code(block_b[3])
    sim = jaccard_similarity(tokenize(norm_a), tokenize(norm_b))
    return sim >= threshold, sim


def ast_equivalence(block_a: Tuple[str, int, int, str, str], block_b: Tuple[str, int, int, str, str]) -> bool:
    """Check AST equivalence of two Python code blocks."""
    try:
        tree_a = ast.parse(block_a[3])
        tree_b = ast.parse(block_b[3])
        return ast.dump(tree_a) == ast.dump(tree_b)
    except SyntaxError:
        return False


class DuplicateChecker(Detector):
    name = "duplicate"
    supported_languages = ["python"]
    description = "Detect likely duplicate implementations across files"

    def scan(
        self, repo_root: Path, ignore_engine: IgnoreEngine, config: Dict[str, Any]
    ) -> List[Finding]:
        dup_config = config.get("duplicate", {})
        min_similarity = dup_config.get("min_similarity", 0.75)
        use_ast = dup_config.get("use_ast", True)

        findings: List[Finding] = []
        processed_pairs = set()

        # Collect eligible Python files and their blocks
        # blocks format: (qualified_name, start_line, end_line, block_src, simple_name)
        file_blocks: Dict[str, List[Tuple[str, int, int, str, str]]] = {}
        for path in repo_root.rglob("*.py"):
            if path.is_symlink():
                continue
            if ignore_engine.is_ignored(path):
                continue
            try:
                source = path.read_text(encoding="utf-8")
            except OSError:
                continue
            rel_path = str(path.relative_to(repo_root))
            blocks = extract_blocks_python(source)
            if blocks:
                file_blocks[rel_path] = blocks

        # Compare blocks pairwise across files
        paths = list(file_blocks.keys())
        for i in range(len(paths)):
            for j in range(i + 1, len(paths)):
                path_a, path_b = paths[i], paths[j]
                for block_a in file_blocks[path_a]:
                    for block_b in file_blocks[path_b]:
                        # Use qualified names for pair identity
                        key = tuple(sorted([(path_a, block_a[0]), (path_b, block_b[0])]))
                        if key in processed_pairs:
                            continue
                        processed_pairs.add(key)

                        matches, sim = compare_blocks(block_a, block_b, min_similarity)
                        if matches:
                            confidence = CONFIRMED if use_ast and ast_equivalence(block_a, block_b) else LIKELY
                            action = (
                                "Compare their behavior, inputs, outputs, and call sites. Determine whether they genuinely duplicate the same responsibility. "
                                "Reuse or consolidate implementations only when their responsibilities are equivalent. Preserve intentional differences."
                            )
                            # Use simple names in evidence for readability
                            evidence = (
                                f"Similar implementations found: {block_a[4]} ({path_a}:{block_a[1]}) and "
                                f"{block_b[4]} ({path_b}:{block_b[1]}) have {sim:.0%} normalized similarity."
                            )
                            # Build stable rule_id using qualified names (scope-aware)
                            sorted_block_a, sorted_block_b = sorted([(path_a, block_a[0]), (path_b, block_b[0])])
                            rule_identity = f"duplicate:implementation:{sorted_block_a[0]}:{sorted_block_a[1]}:{sorted_block_b[0]}:{sorted_block_b[1]}"
                            rule_id = hashlib.sha256(rule_identity.encode()).hexdigest()[:16]

                            findings.append(
                                Finding.create(
                                    category="duplicate",
                                    sub_category="implementation",
                                    path=f"{path_a} <-> {path_b}",
                                    severity="HIGH" if confidence == CONFIRMED else "MEDIUM",
                                    confidence=confidence,
                                    metric=int(sim * 100),
                                    threshold=f">= {int(min_similarity * 100)}% normalized similarity",
                                    action=action,
                                    evidence=evidence,
                                    detection_method="normalized_ast_comparison" if (use_ast and ast_equivalence(block_a, block_b)) else "normalized_text_comparison",
                                    related_paths=[path_a, path_b],
                                    rule_id=rule_id,
                                )
                            )

        return findings