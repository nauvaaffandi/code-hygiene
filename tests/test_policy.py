import unittest
from pathlib import Path

from code_hygiene.policy import (
    calculate_aggregate_warning_policy, 
    prioritize_findings, 
    PolicyEngine
)


class TestPolicy(unittest.TestCase):
    def setUp(self):
        self.engine = PolicyEngine()

    def test_aggregate_warning_below_threshold(self):
        file_findings = [
            {"path": "a.py", "severity": "WARNING"},
            {"path": "b.py", "severity": "WARNING"},
            {"path": "c.py", "severity": "SAFE"},
        ]
        triggered, areas, explanation = calculate_aggregate_warning_policy(file_findings, 10)
        self.assertFalse(triggered)
        self.assertEqual(areas, [])
        self.assertEqual(explanation, "")

    def test_aggregate_warning_exactly_30_percent(self):
        # 3/10 = 30% - should NOT trigger (strictly > 30%)
        file_findings = [
            {"path": "a.py", "severity": "WARNING"},
            {"path": "b.py", "severity": "WARNING"},
            {"path": "c.py", "severity": "WARNING"},
        ]
        triggered, areas, explanation = calculate_aggregate_warning_policy(file_findings, 10)
        self.assertFalse(triggered)

    def test_aggregate_warning_above_threshold(self):
        # 4/10 = 40% - should trigger
        file_findings = [
            {"path": "a.py", "severity": "WARNING"},
            {"path": "b.py", "severity": "WARNING"},
            {"path": "c.py", "severity": "WARNING"},
            {"path": "d.py", "severity": "WARNING"},
        ]
        triggered, areas, explanation = calculate_aggregate_warning_policy(file_findings, 10)
        self.assertTrue(triggered)
        self.assertEqual(areas, ["."])

    def test_aggregate_warning_area_concentration(self):
        # More warnings in subdir than root
        file_findings = [
            {"path": "subdir/a.py", "severity": "WARNING"},
            {"path": "subdir/b.py", "severity": "WARNING"},
            {"path": "subdir/c.py", "severity": "WARNING"},
            {"path": "root1.py", "severity": "WARNING"},
        ]
        triggered, areas, explanation = calculate_aggregate_warning_policy(file_findings, 10)
        self.assertTrue(triggered)
        self.assertEqual(areas, ["subdir"])

    def test_prioritization_order(self):
        file_findings = [
            {"path": "warning1.py", "severity": "WARNING", "category": "file_size"},
            {"path": "critical.py", "severity": "CRITICAL", "category": "file_size"},
            {"path": "refactor.py", "severity": "REFACTOR SOON", "category": "file_size"},
            {"path": "warning2.py", "severity": "WARNING", "category": "file_size"},
        ]
        dir_findings = [
            {"path": "bigdir", "severity": "CRITICAL", "category": "directory_file_count"},
        ]
        
        prioritized = prioritize_findings(file_findings, dir_findings, False, [])
        
        # Should be: critical.py, bigdir, refactor.py, warning1.py, warning2.py
        paths = [f["path"] for f in prioritized]
        self.assertEqual(paths[0], "critical.py")
        self.assertEqual(paths[1], "bigdir")
        self.assertEqual(paths[2], "refactor.py")
        self.assertEqual(paths[3], "warning1.py")
        self.assertEqual(paths[4], "warning2.py")

    def test_prioritization_with_aggregate(self):
        file_findings = [
            {"path": "subdir/warn1.py", "severity": "WARNING", "category": "file_size"},
            {"path": "subdir/warn2.py", "severity": "WARNING", "category": "file_size"},
            {"path": "subdir/warn3.py", "severity": "WARNING", "category": "file_size"},
            {"path": "other.py", "severity": "WARNING", "category": "file_size"},
        ]
        dir_findings = []
        
        prioritized = prioritize_findings(file_findings, dir_findings, True, ["subdir"])
        
        # Should have aggregate area finding first, then other warnings
        paths = [f["path"] for f in prioritized]
        # First should be the aggregate area
        self.assertEqual(paths[0], "subdir")
        # Then other warnings not in aggregate area
        self.assertIn("other.py", paths)

    def test_full_evaluation_no_violations(self):
        file_findings = [
            {"path": "a.py", "severity": "SAFE", "category": "file_size"},
        ]
        dir_findings = []
        
        result = self.engine.evaluate(file_findings, dir_findings, 1)
        
        self.assertFalse(result["has_critical_violations"])
        self.assertFalse(result["has_directory_violations"])
        self.assertFalse(result["aggregate_warning_triggered"])
        self.assertEqual(result["total_eligible_files"], 1)

    def test_full_evaluation_critical_file(self):
        file_findings = [
            {"path": "big.py", "severity": "CRITICAL", "category": "file_size"},
        ]
        dir_findings = []
        
        result = self.engine.evaluate(file_findings, dir_findings, 1)
        
        self.assertTrue(result["has_critical_violations"])
        self.assertFalse(result["has_directory_violations"])
        # Aggregate should not hide critical
        self.assertFalse(result["aggregate_warning_triggered"])
        self.assertEqual(result["prioritized_findings"][0]["path"], "big.py")


if __name__ == "__main__":
    unittest.main()