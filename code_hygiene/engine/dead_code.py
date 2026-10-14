import ast
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple, Optional

from code_hygiene.engine.base import Finding, Detector
from code_hygiene.engine.confidence import CONFIRMED, LIKELY, SUSPECTED, UNSUPPORTED
from code_hygiene.ignore import IgnoreEngine


DYNAMIC_PATTERNS = [
    r"__import__",
    r"getattr\(",
    r"hasattr\(",
    r"setattr\(",
    r"importlib",
    r"pkgutil",
    r"__import__",
    r"\.load_module",
    r"entry_points",
    r"@register",
    r"@.*plugin",
]

ENTRY_POINT_PATTERNS = [
    r"if __name__ == [\"']__main__[\"']",
    r"def main\(",
    r"app\.run\(",
    r"uvicorn\.run\(",
    r"gunicorn",
    r"if __name__ == '__main__'",
]

# Framework-specific patterns that indicate public APIs
FRAMEWORK_PUBLIC_PATTERNS = [
    # Flask
    r"@app\.route",
    r"@blueprint\.route",
    # Django
    r"def.*_view\(",
    r"class.*View",
    # FastAPI
    r"@app\.(get|post|put|delete|patch)",
    r"@router\.(get|post|put|delete|patch)",
    # pytest
    r"@pytest\.fixture",
    r"def test_",
    # CLI entry points
    r"@click\.command",
    r"@click\.group",
    # Celery tasks
    r"@app\.task",
    r"@shared_task",
    # SQLAlchemy models
    r"class.*\(.*Model\)",
    # Pydantic models
    r"class.*\(.*BaseModel\)",
]


def _decorator_matches_pattern(decorator: ast.AST, patterns: List[str]) -> bool:
    """Check if a decorator AST node matches any of the framework patterns."""
    try:
        if hasattr(ast, 'unparse'):
            deco_str = ast.unparse(decorator)
        else:
            if isinstance(decorator, ast.Call):
                func = decorator.func
                if isinstance(func, ast.Attribute):
                    deco_str = f"{ast.unparse(func) if hasattr(ast, 'unparse') else func.attr}()"
                elif isinstance(func, ast.Name):
                    deco_str = f"{func.id}()"
                else:
                    deco_str = str(decorator)
            elif isinstance(decorator, ast.Attribute):
                deco_str = f"{decorator.attr}"
            elif isinstance(decorator, ast.Name):
                deco_str = f"{decorator.id}"
            else:
                deco_str = str(decorator)
    except Exception:
        deco_str = str(decorator)
    
    # Check both with and without leading @
    check_strs = [deco_str, f"@{deco_str}"]
    for p in patterns:
        for s in check_strs:
            if re.search(p, s):
                return True
    return False


def _is_likely_public_api(source: str, node: ast.AST) -> bool:
    """Check if a function/class is likely a public API (framework entry point, export, etc.)"""
    # Check for decorators indicating public API
    if hasattr(node, 'decorator_list'):
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                if decorator.id in ('property', 'classmethod', 'staticmethod'):
                    continue
            # Check for framework decorators
            if _decorator_matches_pattern(decorator, FRAMEWORK_PUBLIC_PATTERNS):
                return True
    
    # Check if function/class name suggests public API
    name = getattr(node, 'name', '')
    if name.startswith('test_') or name.endswith('_test'):
        return True
    if name in ('main', 'run', 'setup', 'teardown', 'initialize', 'configure'):
        return True
    
    return False


def _has_dunder_all(source: str) -> bool:
    """Check if module has __all__ defined (explicit public API)"""
    return '__all__' in source


def _resolve_import_path(repo_root: Path, importing_file: str, module_name: str, level: int = 0) -> Optional[str]:
    """Resolve a (possibly relative) import to a project file path.
    
    Returns the relative path from repo_root to the imported module file,
    or None if it's an external dependency or cannot be resolved.
    """
    if level > 0:
        # Relative import
        importing_path = Path(importing_file).parent
        for _ in range(level - 1):
            importing_path = importing_path.parent
        if module_name:
            target_path = importing_path / module_name.replace('.', '/')
        else:
            target_path = importing_path
    else:
        # Absolute import - treat as project module
        target_path = Path(module_name.replace('.', '/'))
    
    # Check for .py file
    for suffix in ['.py', '/__init__.py']:
        candidate = repo_root / target_path.with_suffix('') if suffix == '.py' else repo_root / target_path
        if suffix == '.py':
            candidate = repo_root / (module_name.replace('.', '/') + '.py')
        else:
            candidate = repo_root / module_name.replace('.', '/') / '__init__.py'
        
        # Need to handle both cases properly
        if level > 0:
            if suffix == '.py':
                candidate = repo_root / importing_path / (module_name.replace('.', '/') + '.py')
            else:
                candidate = repo_root / importing_path / module_name.replace('.', '/') / '__init__.py'
        else:
            if suffix == '.py':
                candidate = repo_root / (module_name.replace('.', '/') + '.py')
            else:
                candidate = repo_root / module_name.replace('.', '/') / '__init__.py'
        
        if candidate.exists() and candidate.is_file():
            return str(candidate.relative_to(repo_root))
        if suffix == '/__init__.py':
            # Check directory with __init__.py
            dir_candidate = candidate.parent
            if (dir_candidate / '__init__.py').exists():
                return str(dir_candidate.relative_to(repo_root))
    
    return None


class _ImportResolver:
    """Resolve imports and attribute access chains to actual symbol definitions."""
    
    def __init__(self, repo_root: Path, file_sources: Dict[str, str]):
        self.repo_root = repo_root
        self.file_sources = file_sources
        # Maps file -> {local_name -> (module_path, symbol_name)}
        self.import_map: Dict[str, Dict[str, Tuple[str, str]]] = {}
        # Maps file -> set of defined symbols (function/class names)
        self.symbol_table: Dict[str, Set[str]] = {}
        # Maps file -> fully qualified symbol definitions
        self.qualified_symbols: Dict[str, Dict[str, str]] = {}  # file -> {simple_name -> qualified_name}
    
    def build_import_map(self, file_imports: Dict[str, Dict[str, Tuple[str, str]]]):
        """Build import map from extracted imports with aliases."""
        self.import_map = file_imports
    
    def build_symbol_tables(self, file_definitions: Dict[str, Dict[str, List[Tuple[int, str]]]]):
        """Build symbol tables from extracted definitions."""
        for file_path, defs in file_definitions.items():
            symbols = set()
            qualified = {}
            for def_type, def_list in defs.items():
                for line_num, def_name in def_list:
                    symbols.add(def_name)
                    # For now, use simple name as qualified name
                    # Could be enhanced with scope info later
                    qualified[def_name] = def_name
            self.symbol_table[file_path] = symbols
            self.qualified_symbols[file_path] = qualified
    
    def extract_attribute_chains(self, source: str) -> List[Tuple[str, List[str]]]:
        """Extract attribute access chains from source code.
        
        Returns list of (base_name, [attr1, attr2, ...]) where base_name is
        a local variable that was imported, and attrs are the chained attributes.
        E.g., for `helpers.format_name()`, returns ('helpers', ['format_name']).
        For `os.path.join()`, returns ('os', ['path', 'join']).
        """
        chains = []
        
        class AttributeChainVisitor(ast.NodeVisitor):
            def __init__(self):
                self.chains = []
            
            def visit_Attribute(self, node: ast.Attribute):
                # Walk up the attribute chain to find the base name
                chain_attrs = []
                current = node
                while isinstance(current, ast.Attribute):
                    chain_attrs.append(current.attr)
                    current = current.value
                
                if isinstance(current, ast.Name):
                    base_name = current.id
                    chain_attrs.reverse()  # Reverse to get correct order
                    self.chains.append((base_name, chain_attrs))
                
                self.generic_visit(node)
            
            def visit_Call(self, node: ast.Call):
                # Also check the function being called
                if isinstance(node.func, ast.Attribute):
                    self.visit_Attribute(node.func)
                self.generic_visit(node)
        
        try:
            tree = ast.parse(source)
            visitor = AttributeChainVisitor()
            visitor.visit(tree)
            return visitor.chains
        except SyntaxError:
            return []
    
    def extract_direct_calls(self, source: str) -> List[str]:
        """Extract direct function calls that might match imported function names.
        
        Returns list of function names called directly (not via attribute access).
        E.g., for `normalize(text)`, returns ['normalize'].
        """
        calls = []
        
        class DirectCallVisitor(ast.NodeVisitor):
            def __init__(self):
                self.calls = []
            
            def visit_Call(self, node: ast.Call):
                if isinstance(node.func, ast.Name):
                    self.calls.append(node.func.id)
                self.generic_visit(node)
        
        try:
            tree = ast.parse(source)
            visitor = DirectCallVisitor()
            visitor.visit(tree)
            return visitor.calls
        except SyntaxError:
            return []
    
    def resolve_chains_for_file(self, file_path: str) -> Set[str]:
        """Resolve attribute chains in a file to find referenced symbols in other files.
        
        Returns a set of fully qualified symbol references in the format
        "target_file.py:symbol_name".
        """
        referenced = set()
        source = self.file_sources.get(file_path, "")
        chains = self.extract_attribute_chains(source)
        imports = self.import_map.get(file_path, {})
        
        # 1. Resolve attribute chains (e.g., helpers.format_name(), utils.api.fetch())
        for base_name, attrs in chains:
            if base_name not in imports:
                continue  # Not an imported module
            
            module_path, imported_symbol, import_type = imports[base_name]
            
            # Determine the effective module path for symbol lookup
            # For ImportFrom statements, the local name refers directly to the imported symbol
            # For Import statements, the local name refers to the top-level module
            effective_module_path = module_path
            if import_type == 'from' and '.' in imported_symbol:
                # imported_symbol like 'utils.math_helpers' -> 'utils/math_helpers.py'
                effective_module_path = imported_symbol.replace('.', '/')
                if not effective_module_path.endswith('.py'):
                    effective_module_path += '.py'
            
            # The first attribute in the chain corresponds to a symbol in the imported module
            if attrs:
                first_attr = attrs[0]
                
                # Check if the effective module has this symbol
                if effective_module_path in self.symbol_table:
                    if first_attr in self.symbol_table[effective_module_path]:
                        # Found a reference to a symbol in another module
                        qualified = self.qualified_symbols[effective_module_path].get(first_attr, first_attr)
                        referenced.add(f"{effective_module_path}:{qualified}")
                
                # Handle multi-level chains: e.g., utils.api.fetch()
                # If first_attr is a submodule, check subsequent attributes in that submodule
                if len(attrs) >= 2:
                    # Try to resolve first_attr as a submodule
                    submodule_path = None
                    
                    # Case 1: effective_module_path is a package directory, first_attr is a module file
                    # e.g., effective_module_path='utils', first_attr='api' -> utils/api.py
                    candidate_submodule = f"{effective_module_path}/{first_attr}.py"
                    if candidate_submodule in self.symbol_table:
                        submodule_path = candidate_submodule
                    
                    # Case 2: effective_module_path is a module file, first_attr is a submodule package
                    # e.g., effective_module_path='utils/api.py', first_attr='sub' -> utils/api/sub/__init__.py
                    # This is less common, but handle it
                    elif effective_module_path.endswith('.py'):
                        candidate_submodule = f"{effective_module_path[:-3]}/{first_attr}/__init__.py"
                        if candidate_submodule in self.symbol_table:
                            submodule_path = candidate_submodule
                    
                    if submodule_path and submodule_path in self.symbol_table:
                        # Check second attribute in the submodule
                        second_attr = attrs[1]
                        if second_attr in self.symbol_table[submodule_path]:
                            qualified = self.qualified_symbols[submodule_path].get(second_attr, second_attr)
                            referenced.add(f"{submodule_path}:{qualified}")
        
        # 2. Resolve direct calls to imported functions (e.g., from module import func; func())
        direct_calls = self.extract_direct_calls(source)
        for func_name in direct_calls:
            # Check if this function name was imported directly
            for local_name, (module_path, imported_symbol, import_type) in imports.items():
                if imported_symbol == func_name or local_name == func_name:
                    # This direct call matches an imported function
                    # Determine effective module path
                    effective_module_path = module_path
                    if import_type == 'from' and '.' in imported_symbol:
                        effective_module_path = imported_symbol.replace('.', '/')
                        if not effective_module_path.endswith('.py'):
                            effective_module_path += '.py'
                    if effective_module_path in self.symbol_table:
                        if func_name in self.symbol_table[effective_module_path]:
                            qualified = self.qualified_symbols[effective_module_path].get(func_name, func_name)
                            referenced.add(f"{effective_module_path}:{qualified}")
        
        return referenced


class DeadCodeChecker(Detector):
    name = "dead_code"
    supported_languages = ["python", "javascript", "typescript", "go", "java"]
    description = "Detect potentially unused files, functions, classes, and imports"

    def scan(
        self, repo_root: Path, ignore_engine: IgnoreEngine, config: Dict[str, Any]
    ) -> List[Finding]:
        findings: List[Finding] = []

        if "python" not in config.get("dead_code", {}).get("support", []):
            return findings

        py_files = []
        for path in repo_root.rglob("*.py"):
            if path.is_symlink():
                continue
            if ignore_engine.is_ignored(path):
                continue
            py_files.append(path)

        if not py_files:
            return findings

        # Build import graph and collect all definitions
        # file_imports now maps file -> {local_name -> (module_path, imported_symbol)}
        file_imports: Dict[str, Dict[str, Tuple[str, str]]] = {}
        file_definitions: Dict[str, Dict[str, List[Tuple[int, str]]]] = {}
        entry_point_files: Set[str] = set()
        dynamic_references: Set[str] = set()
        public_exports: Dict[str, Set[str]] = {}  # file -> set of exported names
        has_dunder_all_map: Dict[str, bool] = {}
        file_sources: Dict[str, str] = {}

        for path in py_files:
            rel_path = str(path.relative_to(repo_root))
            try:
                source = path.read_text(encoding="utf-8")
            except OSError:
                continue
            file_sources[rel_path] = source

            # Check for entry points
            if any(re.search(p, source) for p in ENTRY_POINT_PATTERNS):
                entry_point_files.add(rel_path)

            # Check for dynamic patterns
            if any(re.search(p, source) for p in DYNAMIC_PATTERNS):
                dynamic_references.add(rel_path)

            # Check for __all__ exports
            if _has_dunder_all(source):
                has_dunder_all_map[rel_path] = True

            # Parse imports and definitions
            imports = self._extract_imports(source, rel_path, repo_root)
            file_imports[rel_path] = imports

            defs, exports = self._extract_definitions_and_exports(source, rel_path)
            if defs:
                file_definitions[rel_path] = defs
            if exports:
                public_exports[rel_path] = exports

        # Build call graph from entry points (using module-level imports for file reachability)
        # Convert detailed imports to simple module set for call graph
        simple_imports: Dict[str, Set[str]] = {}
        for file_path, imports in file_imports.items():
            simple_imports[file_path] = set(imp[0] for imp in imports.values())

        reachable = self._build_call_graph(simple_imports, entry_point_files)

        # Also consider files that import our public exports as reachable
        reachable.update(self._find_importers_of_exports(simple_imports, public_exports))

        # Cross-module reference resolution: find symbols referenced via attribute chains
        resolver = _ImportResolver(repo_root, file_sources)
        resolver.build_import_map(file_imports)
        resolver.build_symbol_tables(file_definitions)
        
        # Collect cross-module references
        cross_module_refs: Dict[str, Set[str]] = {}  # target_file -> set of referenced symbols
        for file_path in file_sources:
            refs = resolver.resolve_chains_for_file(file_path)
            for ref in refs:
                target_file, symbol = ref.split(':', 1)
                cross_module_refs.setdefault(target_file, set()).add(symbol)

        # Check unused imports
        for file_path, imports in file_imports.items():
            for local_name, (module_path, imported_symbol, import_type) in imports.items():
                if module_path in reachable or any(module_path in r for r in reachable):
                    continue
                # Check if import might be dynamic or used for side effects
                confidence = SUSPECTED if file_path in dynamic_references else LIKELY
                # Don't flag imports in files with __all__ (they may be re-exported)
                if file_path in has_dunder_all_map:
                    confidence = SUSPECTED
                findings.append(
                    Finding.create(
                        category="dead_code",
                        sub_category="unused_import",
                        path=file_path,
                        severity="LOW" if confidence == LIKELY else "INFO",
                        confidence=confidence,
                        metric=1,
                        threshold="unused import",
                        action="Verify the import is truly unused. Check for dynamic loading, side effects, re-exports, or framework conventions before removing.",
                        evidence=f"Import '{local_name}' (from '{module_path}') in {file_path} is not referenced in the call graph from entry points.",
                        detection_method="static_import_analysis",
                        related_paths=[file_path],
                    )
                )

        # Check unreachable functions/classes
        for file_path, defs in file_definitions.items():
            for def_type, def_list in defs.items():
                for line_num, def_name in def_list:
                    # Check if this definition is reachable
                    is_reachable = False
                    
                    # 1. Symbols in entry point files are reachable
                    if file_path in entry_point_files:
                        is_reachable = True
                    
                    # 2. Explicitly exported via __all__
                    if file_path in public_exports and def_name in public_exports[file_path]:
                        is_reachable = True
                    
                    # 3. Framework public API (test functions, CLI commands, web routes, etc.)
                    # This is already tracked in public_exports via _is_likely_public_api
                    
                    # 4. Cross-module references via attribute chains
                    if file_path in cross_module_refs and def_name in cross_module_refs[file_path]:
                        is_reachable = True

                    if not is_reachable:
                        # Reduce confidence for: dynamic files, test files, files with __all__, framework entry points
                        confidence = LIKELY
                        if file_path in dynamic_references:
                            confidence = SUSPECTED
                        if file_path in has_dunder_all_map:
                            confidence = SUSPECTED
                        if any(kw in file_path.lower() for kw in ('test', 'spec', 'fixture', 'mock')):
                            confidence = SUSPECTED
                        
                        findings.append(
                            Finding.create(
                                category="dead_code",
                                sub_category=f"unreachable_{def_type}",
                                path=file_path,
                                severity="MEDIUM" if confidence == LIKELY else "LOW",
                                confidence=confidence,
                                metric=line_num,
                                threshold="unreachable definition",
                                action=f"Inspect if {def_type} '{def_name}' is used via dynamic imports, reflection, framework conventions, or as a public API. Remove only if confirmed unused.",
                                evidence=f"{def_type.capitalize()} '{def_name}' at line {line_num} in {file_path} is not reachable from any entry point or known importer.",
                                detection_method="static_call_graph",
                                related_paths=[file_path],
                            )
                        )

        return findings

    def _extract_imports(self, source: str, rel_path: str, repo_root: Path) -> Dict[str, Tuple[str, str, str]]:
        """Extract imports with alias information, resolving module names to file paths.
        
        Returns a dict mapping local_name -> (resolved_module_file_path, imported_symbol, import_type).
        import_type is 'import' for `import ...` or 'from' for `from ... import ...`.
        For example:
        - `import os` -> {'os': ('os', 'os', 'import')} (external, not resolved)
        - `import utils.api` -> {'utils': ('utils', 'utils.api', 'import')}
        - `from utils import helpers` -> {'helpers': ('utils/helpers.py', 'helpers', 'from')}
        - `from utils.helpers import format_name` -> {'format_name': ('utils/helpers.py', 'format_name', 'from')}
        """
        imports = {}
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return imports

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # For `import a.b.c`, the local name is `a` (unless aliased as `import a.b.c as x`)
                    # When aliased, the local name refers to the full module
                    if alias.asname:
                        local_name = alias.asname
                        # Resolve the full module path
                        module_path = self._resolve_module_to_file(repo_root, rel_path, alias.name, 0)
                    else:
                        local_name = alias.name.split('.')[0]
                        # Try to resolve the TOP-LEVEL module to a project file
                        top_level_module = alias.name.split('.')[0]
                        module_path = self._resolve_module_to_file(repo_root, rel_path, top_level_module, 0)
                    
                    if module_path:
                        imports[local_name] = (module_path, alias.name, 'import')
                    else:
                        # External dependency - keep as-is
                        imports[local_name] = (alias.name, alias.name, 'import')
                        # External dependency - keep as-is
                        imports[local_name] = (alias.name, alias.name, 'import')
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                level = node.level
                for alias in node.names:
                    local_name = alias.asname or alias.name
                    # Resolve relative import
                    full_module = f"{module}.{alias.name}" if module else alias.name
                    module_path = self._resolve_module_to_file(repo_root, rel_path, module, level, alias.name)
                    if module_path:
                        # For from X import Y, the module_path is the file containing Y
                        imports[local_name] = (module_path, alias.name, 'from')
                    else:
                        # External dependency
                        imports[local_name] = (full_module, alias.name, 'from')
        return imports

    def _resolve_module_to_file(self, repo_root: Path, importing_file: str, module_name: str, level: int, imported_symbol: Optional[str] = None) -> Optional[str]:
        """Resolve a (possibly relative) import module to a project file path.
        
        Returns the relative path from repo_root to the imported module file,
        or None if it's an external dependency or cannot be resolved.
        """
        if not module_name and level == 0:
            return None
            
        # For relative imports, we need to find the package root
        # The importing_file is like 'pkg/services/handler.py'
        # The package is 'pkg.services' (directories up to repo_root)
        importing_path = Path(importing_file).parent
        
        if level > 0:
            # Relative import: go up (level - 1) directories from the current package
            # level=1 means current package (from . import X)
            # level=2 means parent package (from .. import X)
            # level=3 means grandparent package (from ... import X)
            for _ in range(level - 1):
                importing_path = importing_path.parent
            if module_name:
                target_parts = module_name.split('.')
                target_path = importing_path
                for part in target_parts:
                    target_path = target_path / part
            else:
                # from . import X or from .. import X - target is the package itself
                target_path = importing_path
        else:
            # Absolute import - resolve from repo root
            target_path = Path(module_name.replace('.', '/'))
        
        # Convert to absolute path from repo_root
        abs_target_path = repo_root / target_path
        
        # If we have an imported_symbol (from `from X import Y`), try to resolve Y as a module within X
        if imported_symbol:
            # First check if X.Y is a module file
            candidate_with_symbol = abs_target_path / imported_symbol
            py_candidate = candidate_with_symbol.with_suffix('.py')
            if py_candidate.exists() and py_candidate.is_file():
                return str(py_candidate.relative_to(repo_root))
            # Check if X.Y is a package
            init_candidate = candidate_with_symbol / '__init__.py'
            if init_candidate.exists() and init_candidate.is_file():
                return str(candidate_with_symbol.relative_to(repo_root))
        
        # Check for .py file (X is a module) - only if target_path has a name
        if target_path.name:
            py_candidate = abs_target_path.with_suffix('.py')
            if py_candidate.exists() and py_candidate.is_file():
                return str(py_candidate.relative_to(repo_root))
        
        # Check for package (directory with __init__.py)
        init_candidate = abs_target_path / '__init__.py'
        if init_candidate.exists() and init_candidate.is_file():
            return str(target_path)
            
        # Also check if target_path is a directory without __init__.py (namespace package or module folder)
        if abs_target_path.exists() and abs_target_path.is_dir():
            return str(target_path)
        
        return None

    def _extract_definitions_and_exports(self, source: str, rel_path: str) -> Tuple[Dict[str, List[Tuple[int, str]]], Set[str]]:
        """Extract function/class definitions with line numbers and public exports."""
        defs = {"function": [], "class": []}
        exports = set()
        
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return defs, exports

        # Check for __all__
        has_all = _has_dunder_all(source)
        all_names = set()
        if has_all:
            # Try to extract __all__ content
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == '__all__':
                            if isinstance(node.value, (ast.List, ast.Tuple)):
                                for elt in node.value.elts:
                                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                        all_names.add(elt.value)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs["function"].append((node.lineno, node.name))
                # Check if explicitly exported
                if node.name in all_names:
                    exports.add(node.name)
                # Check if likely public API
                elif _is_likely_public_api(source, node):
                    exports.add(node.name)
            elif isinstance(node, ast.ClassDef):
                defs["class"].append((node.lineno, node.name))
                if node.name in all_names:
                    exports.add(node.name)
                elif _is_likely_public_api(source, node):
                    exports.add(node.name)

        return defs, exports

    def _build_call_graph(self, file_imports: Dict[str, Set[str]], entry_points: Set[str]) -> Set[str]:
        """Simple transitive closure of imports from entry points."""
        reachable = set(entry_points)
        changed = True

        while changed:
            changed = False
            for file_path, imports in file_imports.items():
                if file_path in reachable:
                    for imp in imports:
                        if imp not in reachable:
                            reachable.add(imp)
                            changed = True

        return reachable

    def _find_importers_of_exports(self, file_imports: Dict[str, Set[str]], public_exports: Dict[str, Set[str]]) -> Set[str]:
        """Find files that import from modules with public exports."""
        importers = set()
        for file_path, imports in file_imports.items():
            for imp in imports:
                # Check if this import matches a file with public exports
                for export_file, exports in public_exports.items():
                    # Simplistic matching - could be improved
                    if export_file.replace('/', '.').replace('.py', '') in imp:
                        importers.add(file_path)
        return importers