import tempfile
import unittest
from pathlib import Path

from code_hygiene.engine.changes import ChangesChecker
from code_hygiene.ignore import IgnoreEngine


class TestChanges(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.repo_root = Path(self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_file(self, rel_path: str, content: str = "") -> Path:
        path = self.repo_root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def _init_git(self):
        import subprocess
        subprocess.run(["git", "init"], cwd=self.repo_root, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.repo_root, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo_root, capture_output=True)
        self._create_file("README.md", "# Test")
        subprocess.run(["git", "add", "."], cwd=self.repo_root, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=self.repo_root, capture_output=True)

    def test_no_git_repo(self):
        checker = ChangesChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"git": {"enabled": True}}
        findings = checker.scan(self.repo_root, ignore_engine, config)
        self.assertEqual(len(findings), 0)

    def test_clean_git_repo(self):
        self._init_git()
        checker = ChangesChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"git": {"enabled": True}}
        findings = checker.scan(self.repo_root, ignore_engine, config)
        self.assertEqual(len(findings), 0)

    def test_modified_file(self):
        self._init_git()
        self._create_file("src/main.py", "print('hello')")
        import subprocess
        subprocess.run(["git", "add", "src/main.py"], cwd=self.repo_root, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add main"], cwd=self.repo_root, capture_output=True)

        self._create_file("src/main.py", "print('hello world')")
        subprocess.run(["git", "add", "src/main.py"], cwd=self.repo_root, capture_output=True)

        checker = ChangesChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"git": {"enabled": True}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        self.assertGreater(len(findings), 0)
        summary = [f for f in findings if f.sub_category == "summary"]
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0].metric, 1)

    def test_task_scope_check(self):
        self._init_git()
        self._create_file("src/main.py", "print('hello')")
        import subprocess
        subprocess.run(["git", "add", "src/main.py"], cwd=self.repo_root, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add main"], cwd=self.repo_root, capture_output=True)

        self._create_file("src/main.py", "print('hello world')")
        self._create_file("unrelated.py", "print('unrelated')")
        subprocess.run(["git", "add", "src/main.py", "unrelated.py"], cwd=self.repo_root, capture_output=True)

        checker = ChangesChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {
            "git": {"enabled": True},
            "task_description": "Update the main function in src/main.py"
        }
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unrelated = [f for f in findings if f.sub_category == "potentially_unrelated"]
        self.assertGreater(len(unrelated), 0)
        paths = {f.path for f in unrelated}
        self.assertIn("unrelated.py", paths)


if __name__ == "__main__":
    unittest.main()