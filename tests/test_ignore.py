import os
import tempfile
import unittest
from pathlib import Path

from code_hygiene.ignore import IgnoreEngine


class TestIgnoreEngine(unittest.TestCase):
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

    def _create_dir(self, rel_path: str) -> Path:
        path = self.repo_root / rel_path
        path.mkdir(parents=True, exist_ok=True)
        return path

    def test_default_patterns(self):
        engine = IgnoreEngine(self.repo_root)
        
        git_dir = self._create_dir(".git")
        self.assertTrue(engine.is_ignored(git_dir))
        
        node_modules = self._create_dir("node_modules")
        self.assertTrue(engine.is_ignored(node_modules))
        
        venv = self._create_dir("venv")
        self.assertTrue(engine.is_ignored(venv))
        
        pycache = self._create_dir("__pycache__")
        self.assertTrue(engine.is_ignored(pycache))

    def test_custom_ignore_file(self):
        ignore_file = self._create_file(".ignore", "custom_dir/\n*.custom\n")
        engine = IgnoreEngine(self.repo_root, ignore_file)
        
        custom_dir = self._create_dir("custom_dir")
        self.assertTrue(engine.is_ignored(custom_dir))
        
        custom_file = self._create_file("test.custom")
        self.assertTrue(engine.is_ignored(custom_file))
        
        normal_file = self._create_file("normal.txt")
        self.assertFalse(engine.is_ignored(normal_file))

    def test_wildcard_patterns(self):
        ignore_file = self._create_file(".ignore", "*.log\nlogs/")
        engine = IgnoreEngine(self.repo_root, ignore_file)
        
        log_file = self._create_file("app.log")
        self.assertTrue(engine.is_ignored(log_file))
        
        nested_log = self._create_file("subdir/debug.log")
        self.assertTrue(engine.is_ignored(nested_log))
        
        logs_dir = self._create_dir("logs")
        self.assertTrue(engine.is_ignored(logs_dir))

    def test_comments_and_empty_lines(self):
        ignore_file = self._create_file(".ignore", "# This is a comment\n\n*.tmp\n")
        engine = IgnoreEngine(self.repo_root, ignore_file)
        
        tmp_file = self._create_file("test.tmp")
        self.assertTrue(engine.is_ignored(tmp_file))
        
        normal_file = self._create_file("normal.txt")
        self.assertFalse(engine.is_ignored(normal_file))

    def test_directory_trailing_slash(self):
        ignore_file = self._create_file(".ignore", "build/")
        engine = IgnoreEngine(self.repo_root, ignore_file)
        
        build_dir = self._create_dir("build")
        self.assertTrue(engine.is_ignored(build_dir))
        
        build_file = self._create_file("build.txt")
        self.assertFalse(engine.is_ignored(build_file))

    def test_nested_paths(self):
        engine = IgnoreEngine(self.repo_root)
        
        nested_git = self._create_dir("src/.git")
        self.assertTrue(engine.is_ignored(nested_git))
        
        src_file = self._create_file("src/main.py")
        self.assertFalse(engine.is_ignored(src_file))

    def test_filter_paths(self):
        engine = IgnoreEngine(self.repo_root)
        
        paths = [
            self._create_file("main.py"),
            self._create_file(".git/config"),
            self._create_file("node_modules/pkg/index.js"),
            self._create_file("src/utils.py"),
        ]
        
        filtered = engine.filter_paths(paths)
        self.assertEqual(len(filtered), 2)
        self.assertIn(self.repo_root / "main.py", filtered)
        self.assertIn(self.repo_root / "src/utils.py", filtered)

    def test_outside_repo(self):
        engine = IgnoreEngine(self.repo_root)
        
        outside = Path("/tmp/outside_file")
        self.assertTrue(engine.is_ignored(outside))


if __name__ == "__main__":
    unittest.main()