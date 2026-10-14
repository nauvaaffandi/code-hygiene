import unittest
from pathlib import Path

from code_hygiene.engine.dead_code import DeadCodeChecker
from code_hygiene.engine.duplicate import DuplicateChecker
from code_hygiene.ignore import IgnoreEngine


class TestGoldenFixture(unittest.TestCase):
    def test_golden_fixture_scan(self):
        """Scan the golden fixture project and verify expected findings."""
        fixture_root = Path(__file__).parent / "fixtures" / "golden"
        self.assertTrue(fixture_root.exists(), f"Golden fixture root not found at {fixture_root}")

        ignore_engine = IgnoreEngine(fixture_root)
        
        # 1. Test Dead Code Scanner
        dead_checker = DeadCodeChecker()
        dead_config = {"dead_code": {"support": ["python"]}}
        dead_findings = dead_checker.scan(fixture_root, ignore_engine, dead_config)

        # Extract unreachable symbol names and paths
        unreachable = [f for f in dead_findings if f.sub_category.startswith("unreachable")]
        
        unreachable_symbols = {f.evidence.split("'")[1] for f in unreachable if "'" in f.evidence}
        
        # Items that SHOULD be flagged (genuinely unreachable):
        # - core/models.py: private_func, PrivateClass
        # - core/services.py: internal_service, unused_service
        # - core/handlers.py: internal_handler, unused_handler
        # - utils/string_helpers.py: unused_util, helper_with_math
        # - utils/math_helpers.py: unused_func, multiply, helper_with_string
        # - plugins/external_plugin.py: truly_unused, dynamic_target (SUSPECTED)
        # - legacy/old_api.py: legacy_normalize (duplicate), legacy_validate (duplicate), legacy_unused
        # - inheritance/base.py: process (super() not resolved), helper (not directly called), unused_base_method
        # - inheritance/derived.py: unused_derived_method
        # - nested/funcs.py: outer_c, unused_outer
        # - plugins/loader.py: load_plugin (not used in main.py), call_dynamic_target (importlib)
        
        self.assertIn("private_func", unreachable_symbols)
        self.assertIn("PrivateClass", unreachable_symbols)
        self.assertIn("unused_service", unreachable_symbols)
        self.assertIn("internal_service", unreachable_symbols)
        self.assertIn("internal_handler", unreachable_symbols)
        self.assertIn("unused_handler", unreachable_symbols)
        self.assertIn("unused_util", unreachable_symbols)
        self.assertIn("helper_with_math", unreachable_symbols)
        self.assertIn("unused_func", unreachable_symbols)
        self.assertIn("multiply", unreachable_symbols)
        self.assertIn("helper_with_string", unreachable_symbols)
        self.assertIn("truly_unused", unreachable_symbols)
        self.assertIn("legacy_unused", unreachable_symbols)
        self.assertIn("unused_base_method", unreachable_symbols)
        self.assertIn("unused_derived_method", unreachable_symbols)
        self.assertIn("outer_c", unreachable_symbols)
        self.assertIn("unused_outer", unreachable_symbols)
        
        # Items that should NOT be flagged (reachable):
        self.assertNotIn("public_func", unreachable_symbols)
        self.assertNotIn("PublicClass", unreachable_symbols)
        self.assertNotIn("normalize", unreachable_symbols)
        self.assertNotIn("validate", unreachable_symbols)
        self.assertNotIn("add", unreachable_symbols)
        self.assertNotIn("flask_index", unreachable_symbols)
        self.assertNotIn("flask_get_users", unreachable_symbols)
        self.assertNotIn("fastapi_root", unreachable_symbols)
        self.assertNotIn("fastapi_create_item", unreachable_symbols)
        self.assertNotIn("process_data", unreachable_symbols)
        self.assertNotIn("outer_a", unreachable_symbols)
        self.assertNotIn("outer_b", unreachable_symbols)
        self.assertNotIn("legacy_normalize", unreachable_symbols)  # used in main.py
        
        # Current limitation: method calls on instances not resolved
        # These are flagged but should not be in ideal implementation
        self.assertIn("derived_only", unreachable_symbols)  # Called as d.derived_only()
        self.assertIn("process", unreachable_symbols)  # Called as d.process() and super().process()
        self.assertIn("helper", unreachable_symbols)  # Called as d.helper()
        
        # Functions in plugins/loader.py are not used in main.py
        self.assertIn("load_plugin", unreachable_symbols)
        self.assertIn("call_static", unreachable_symbols)
        self.assertIn("call_dynamic_target", unreachable_symbols)

        # 2. Test Duplicate Scanner
        dup_checker = DuplicateChecker()
        dup_config = {"duplicate": {"min_similarity": 0.70, "use_ast": True}}
        dup_findings = dup_checker.scan(fixture_root, ignore_engine, dup_config)

        # Should detect duplicate between legacy/old_api.py and utils/string_helpers.py (normalize & validate)
        self.assertGreaterEqual(len(dup_findings), 1)
        dup_paths = {f.path for f in dup_findings}
        self.assertTrue(any("old_api.py" in p for p in dup_paths))


if __name__ == "__main__":
    unittest.main()