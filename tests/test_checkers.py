import os
import tempfile
import unittest
from pathlib import Path

from code_hygiene.ignore import IgnoreEngine
from code_hygiene.checkers import FileSizeChecker, DirectoryChecker, classify_file, is_binary_file, count_lines


class TestCheckers(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.repo_root = Path(self.temp_dir)
        self.ignore_engine = IgnoreEngine(self.repo_root)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_file(self, rel_path: str, lines_count: int = 10, content_prefix: str = "line") -> Path:
        path = self.repo_root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join([f"{content_prefix} {i}" for i in range(lines_count)])
        path.write_text(content)
        return path

    def test_line_count_classification(self):
        self.assertEqual(classify_file(150)[0], "SAFE")
        self.assertEqual(classify_file(199)[0], "SAFE")
        self.assertEqual(classify_file(200)[0], "WARNING")
        self.assertEqual(classify_file(249)[0], "WARNING")
        self.assertEqual(classify_file(250)[0], "REFACTOR SOON")
        self.assertEqual(classify_file(299)[0], "REFACTOR SOON")
        self.assertEqual(classify_file(300)[0], "CRITICAL")
        self.assertEqual(classify_file(500)[0], "CRITICAL")

    def test_file_size_checker_boundaries(self):
        self._create_file("safe.py", 199)
        self._create_file("warning.py", 200)
        self._create_file("warning_high.py", 249)
        self._create_file("refactor.py", 250)
        self._create_file("refactor_high.py", 299)
        self._create_file("critical.py", 300)

        checker = FileSizeChecker(self.repo_root, self.ignore_engine)
        findings = checker.scan()

        # safe.py (<200) should not be reported
        reported_paths = {f["path"] for f in findings}
        self.assertNotIn("safe.py", reported_paths)
        self.assertIn("warning.py", reported_paths)
        self.assertIn("warning_high.py", reported_paths)
        self.assertIn("refactor.py", reported_paths)
        self.assertIn("refactor_high.py", reported_paths)
        self.assertIn("critical.py", reported_paths)

        findings_map = {f["path"]: f for f in findings}
        self.assertEqual(findings_map["warning.py"]["severity"], "WARNING")
        self.assertEqual(findings_map["refactor.py"]["severity"], "REFACTOR SOON")
        self.assertEqual(findings_map["critical.py"]["severity"], "CRITICAL")

    def test_binary_file_detection(self):
        bin_path = self.repo_root / "binary.bin"
        bin_path.write_bytes(b"hello\x00world")
        self.assertTrue(is_binary_file(bin_path))

        text_path = self.repo_root / "text.txt"
        text_path.write_text("hello world")
        self.assertFalse(is_binary_file(text_path))

    def test_directory_checker_thresholds(self):
        # Create 15 files in dir_safe
        dir_safe = self.repo_root / "dir_safe"
        dir_safe.mkdir()
        for i in range(15):
            (dir_safe / f"file_{i}.py").write_text("print(1)")

        # Create 16 files in dir_over
        dir_over = self.repo_root / "dir_over"
        dir_over.mkdir()
        for i in range(16):
            (dir_over / f"file_{i}.py").write_text("print(1)")

        checker = DirectoryChecker(self.repo_root, self.ignore_engine, threshold=15)
        findings = checker.scan()

        reported_dirs = {f["path"] for f in findings}
        self.assertNotIn("dir_safe", reported_dirs)
        self.assertIn("dir_over", reported_dirs)
        
        finding = next(f for f in findings if f["path"] == "dir_over")
        self.assertEqual(finding["metric"], 16)


if __name__ == "__main__":
    unittest.main()