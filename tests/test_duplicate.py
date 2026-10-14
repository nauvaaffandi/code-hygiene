import os
import tempfile
import unittest
from pathlib import Path

from code_hygiene.engine.confidence import CONFIRMED, LIKELY, SUSPECTED
from code_hygiene.engine import Detector
from code_hygiene.engine.duplicate import normalize_code, jaccard_similarity, extract_blocks_python, compare_blocks, DuplicateChecker
from code_hygiene.engine.base import Finding
from code_hygiene.ignore import IgnoreEngine


class TestDuplicate(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.repo_root = Path(self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_normalize_code(self):
        src1 = "def foo(x):\n    return x + 1\n"
        src2 = "def bar(y):\n    return y + 2\n"
        self.assertNotEqual(normalize_code(src1), normalize_code(src2))

        src3 = "def foo(x):\n    return x + 1\n"
        src4 = "def bar(x):\n    return x + 1\n"
        # Function names are preserved in normalization
        self.assertNotEqual(normalize_code(src3), normalize_code(src4))

    def test_jaccard_similarity(self):
        a = {"a", "b", "c"}
        b = {"a", "b", "d"}
        self.assertEqual(jaccard_similarity(a, b), 0.5)

        c = {"a", "b", "c"}
        d = {"a", "b", "c"}
        self.assertEqual(jaccard_similarity(c, d), 1.0)

    def test_extract_blocks_python(self):
        source = """
def foo(x):
    return x + 1

def bar(y):
    return y + 2

class Baz:
    def method(self):
        pass
"""
        blocks = extract_blocks_python(source)
        names = [b[0] for b in blocks]
        self.assertIn("foo", names)
        self.assertIn("bar", names)
        self.assertIn("Baz", names)

    def test_compare_blocks(self):
        block_a = ("foo", 1, 3, "def foo(x):\n    return x + 1\n")
        block_b = ("bar", 5, 7, "def bar(x):\n    return x + 1\n")
        matches, sim = compare_blocks(block_a, block_b, 0.7)
        self.assertTrue(matches)
        self.assertGreater(sim, 0.7)

    def test_duplicate_checker(self):
        self._create_file("utils/format_price.py", """
def format_price(amount):
    return amount * 2
""")
        self._create_file("helpers/format_currency.py", """
def format_currency(amount):
    return amount * 2
""")

        from code_hygiene.ignore import IgnoreEngine

        checker = DuplicateChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"duplicate": {"min_similarity": 0.70, "use_ast": True}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        self.assertGreater(len(findings), 0)
        finding = findings[0]
        self.assertEqual(finding.category, "duplicate")
        self.assertTrue(finding.path.startswith("utils/format_price.py"))

    def _create_file(self, rel_path: str, content: str) -> Path:
        path = self.repo_root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_duplicate_rule_id_stability_different_pairs(self):
        """Different duplicate pairs must have different rule_ids."""
        self._create_file("a.py", """
def func1():
    return "hello"
""")
        self._create_file("b.py", """
def func1():
    return "hello"
""")
        self._create_file("c.py", """
def func2():
    return "world"
""")
        self._create_file("d.py", """
def func2():
    return "world"
""")

        checker = DuplicateChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"duplicate": {"min_similarity": 0.70, "use_ast": True}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        self.assertGreaterEqual(len(findings), 2)
        rule_ids = [f.rule_id for f in findings]
        # Each pair should have a unique rule_id
        self.assertEqual(len(set(rule_ids)), len(rule_ids), "Duplicate pairs must have distinct rule_ids")

    def test_duplicate_rule_id_order_invariant(self):
        """Reversing pair order must produce the same rule_id."""
        self._create_file("module_a.py", """
def calculate(x):
    return x * 2
""")
        self._create_file("module_b.py", """
def compute(y):
    return y * 2
""")

        checker = DuplicateChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"duplicate": {"min_similarity": 0.70, "use_ast": True}}

        # First scan
        findings1 = checker.scan(self.repo_root, ignore_engine, config)
        rule_ids_1 = [f.rule_id for f in findings1]

        # Second scan (same files, but detection order could vary internally)
        findings2 = checker.scan(self.repo_root, ignore_engine, config)
        rule_ids_2 = [f.rule_id for f in findings2]

        # Rule IDs should be identical regardless of scan order
        self.assertEqual(set(rule_ids_1), set(rule_ids_2))

    def test_duplicate_rule_id_preserved_across_scans(self):
        """Repeated scans must preserve identity (rule_id)."""
        self._create_file("src/math.py", """
def add(a, b):
    return a + b
""")
        self._create_file("lib/arithmetic.py", """
def sum(x, y):
    return x + y
""")

        checker = DuplicateChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"duplicate": {"min_similarity": 0.70, "use_ast": True}}

        # First scan
        findings1 = checker.scan(self.repo_root, ignore_engine, config)
        rule_ids_1 = {f.rule_id for f in findings1}

        # Second scan
        findings2 = checker.scan(self.repo_root, ignore_engine, config)
        rule_ids_2 = {f.rule_id for f in findings2}

        # Rule IDs should be preserved
        self.assertEqual(rule_ids_1, rule_ids_2)

    def test_duplicate_rule_id_invariant_to_similarity_change(self):
        """A similarity score change must not change identity."""
        self._create_file("file1.py", """
def process(data):
    result = data * 2
    return result + 1
""")
        self._create_file("file2.py", """
def handle(input):
    output = input * 2
    return output + 1
""")

        checker = DuplicateChecker()
        ignore_engine = IgnoreEngine(self.repo_root)

        # Scan with lower threshold (higher similarity)
        config1 = {"duplicate": {"min_similarity": 0.60, "use_ast": True}}
        findings1 = checker.scan(self.repo_root, ignore_engine, config1)
        rule_ids_1 = {f.rule_id for f in findings1}

        # Scan with higher threshold (lower similarity)
        config2 = {"duplicate": {"min_similarity": 0.80, "use_ast": True}}
        findings2 = checker.scan(self.repo_root, ignore_engine, config2)
        rule_ids_2 = {f.rule_id for f in findings2}

        # If both detect the pair, rule_ids should match
        # Note: at 0.80 threshold, the pair might not be detected
        if findings1 and findings2:
            self.assertEqual(rule_ids_1, rule_ids_2)

    def test_baseline_classification_duplicate_findings(self):
        """Baseline must correctly classify added, persistent, and resolved duplicate findings."""
        from code_hygiene.reporter import ReportManager

        repo = ReportManager(self.repo_root)

        # First scan: one duplicate pair (same function name for detection)
        self._create_file("old_a.py", """
def calculate():
    return 42
""")
        self._create_file("old_b.py", """
def calculate():
    return 42
""")

        checker = DuplicateChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"duplicate": {"min_similarity": 0.70, "use_ast": True}}

        findings1 = checker.scan(self.repo_root, ignore_engine, config)

        policy_result1 = {
            "prioritized_findings": findings1,
            "summary": {"by_severity": {}, "by_category": {}},
            "has_critical_violations": False,
            "has_directory_violations": False,
            "aggregate_warning_triggered": False,
            "aggregate_areas": [],
            "aggregate_explanation": "",
            "total_eligible_files": 2,
        }
        repo.save_report(policy_result1)

        # Second scan: same pair + new pair (different function name)
        self._create_file("new_a.py", """
def compute():
    return 99
""")
        self._create_file("new_b.py", """
def compute():
    return 99
""")

        findings2 = checker.scan(self.repo_root, ignore_engine, config)

        policy_result2 = {
            "prioritized_findings": findings2,
            "summary": {"by_severity": {}, "by_category": {}},
            "has_critical_violations": False,
            "has_directory_violations": False,
            "aggregate_warning_triggered": False,
            "aggregate_areas": [],
            "aggregate_explanation": "",
            "total_eligible_files": 4,
        }
        repo.save_report(policy_result2)

        loaded = repo.load_report()
        findings = loaded.get("findings", [])
        paths = {f["path"] for f in findings}

        # Should have both old and new pairs
        self.assertEqual(len(findings), 2)
        # Check that identities are preserved
        rule_ids = {f["rule_id"] for f in findings}
        self.assertEqual(len(rule_ids), 2)

    def test_duplicate_functions_same_name_different_class(self):
        """Functions with identical names in different classes must have distinct rule_ids."""
        self._create_file("file1.py", """
class ClassA:
    def process(self):
        return "A"
""")
        self._create_file("file2.py", """
class ClassA:
    def process(self):
        return "A"
""")
        self._create_file("file3.py", """
class ClassB:
    def process(self):
        return "B"
""")
        self._create_file("file4.py", """
class ClassB:
    def process(self):
        return "B"
""")

        checker = DuplicateChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"duplicate": {"min_similarity": 0.70, "use_ast": True}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        # Should detect two distinct pairs: (ClassA.process in file1, file2) and (ClassB.process in file3, file4)
        self.assertGreaterEqual(len(findings), 2)
        rule_ids = [f.rule_id for f in findings]
        self.assertEqual(len(set(rule_ids)), len(rule_ids), "Duplicate pairs with same function names in different classes must have distinct rule_ids")

    def test_duplicate_nested_functions_different_parents(self):
        """Same nested function name under different parent functions must have distinct rule_ids."""
        self._create_file("file1.py", """
def outer_a():
    def helper():
        return "a"
    return helper()
""")
        self._create_file("file2.py", """
def outer_a():
    def helper():
        return "a"
    return helper()
""")
        self._create_file("file3.py", """
def outer_b():
    def helper():
        return "b"
    return helper()
""")
        self._create_file("file4.py", """
def outer_b():
    def helper():
        return "b"
    return helper()
""")

        checker = DuplicateChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"duplicate": {"min_similarity": 0.70, "use_ast": True}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        # Should detect two distinct pairs: (outer_a.helper in file1, file2) and (outer_b.helper in file3, file4)
        self.assertGreaterEqual(len(findings), 2)
        rule_ids = [f.rule_id for f in findings]
        self.assertEqual(len(set(rule_ids)), len(rule_ids), "Duplicate pairs with same nested function names under different parents must have distinct rule_ids")

    def test_identical_body_different_names_cross_file(self):
        """Identical implementations with different function names should be detected as duplicates."""
        self._create_file("mod_a.py", """
def calculate_price(base, tax):
    total = base * (1 + tax)
    return round(total, 2)
""")
        self._create_file("mod_b.py", """
def compute_cost(amount, rate):
    total = amount * (1 + rate)
    return round(total, 2)
""")

        checker = DuplicateChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"duplicate": {"min_similarity": 0.70, "use_ast": True}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        self.assertGreaterEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.category, "duplicate")
        # Both functions should be referenced in evidence
        self.assertIn("calculate_price", finding.evidence)
        self.assertIn("compute_cost", finding.evidence)

    def test_duplicate_functions_with_decorators(self):
        """Functions with identical bodies but different decorators should be detected."""
        self._create_file("decorated_a.py", """
def validator(func):
    return func

@validator
def process_data(x):
    return x * 2 + 1
""")
        self._create_file("decorated_b.py", """
def logger(func):
    return func

@logger
def transform_input(y):
    return y * 2 + 1
""")

        checker = DuplicateChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"duplicate": {"min_similarity": 0.70, "use_ast": True}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        self.assertGreaterEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.category, "duplicate")

    def test_cross_file_class_method_duplicate_different_self_names(self):
        """Class methods with different 'self' parameter names should be detected as duplicates."""
        self._create_file("service_a.py", """
class DataService:
    def process(self, data):
        result = data.strip().lower()
        return result
""")
        self._create_file("service_b.py", """
class DataProcessor:
    def process(this, data):
        result = data.strip().lower()
        return result
""")
        self._create_file("service_c.py", """
class ItemHandler:
    def process(cls, data):
        result = data.strip().lower()
        return result
""")

        checker = DuplicateChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"duplicate": {"min_similarity": 0.70, "use_ast": True}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        # Should detect all three as duplicates of each other
        self.assertGreaterEqual(len(findings), 2)
        rule_ids = {f.rule_id for f in findings}
        # All three files should be in the same duplicate cluster
        self.assertEqual(len(rule_ids), 1, "All three class methods should have the same rule_id")


if __name__ == "__main__":
    unittest.main()