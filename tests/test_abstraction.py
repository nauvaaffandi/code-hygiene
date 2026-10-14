import tempfile
import unittest
from pathlib import Path

from code_hygiene.engine.generation import AbstractionChecker, GenerationChecker
from code_hygiene.ignore import IgnoreEngine


class TestAbstraction(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.repo_root = Path(self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_file(self, rel_path: str, content: str) -> Path:
        path = self.repo_root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_one_function_module(self):
        self._create_file("single_func.py", """
def helper():
    return 42
""")

        checker = AbstractionChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"abstractions": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        one_func = [f for f in findings if f.sub_category == "one_function_module"]
        self.assertGreater(len(one_func), 0)
        self.assertEqual(one_func[0].path, "single_func.py")

    def test_wrapper_layer(self):
        self._create_file("wrapper.py", """
def inner():
    return "inner"

def outer():
    return inner()
""")

        checker = AbstractionChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"abstractions": {"support": ["python"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        wrappers = [f for f in findings if f.sub_category == "wrapper_layer"]
        self.assertGreater(len(wrappers), 0)

    def test_generated_file_detection(self):
        self._create_file("gen_out/generated.py", """
# This file is generated
def gen_func():
    pass
""")
        self._create_file("normal.py", """
def normal():
    pass
""")

        checker = GenerationChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"generation": {"patterns": ["gen_out/*", "*generated*"]}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        generated = [f for f in findings if f.sub_category == "generated_file"]
        paths = {f.path for f in generated}
        self.assertIn("gen_out/generated.py", paths)
        self.assertNotIn("normal.py", paths)

    def test_unused_dependency_python(self):
        self._create_file("requirements.txt", """
requests==2.31.0
unused-package==1.0.0
""")
        self._create_file("main.py", """
import requests
print("hello")
""")

        checker = GenerationChecker()
        ignore_engine = IgnoreEngine(self.repo_root)
        config = {"generation": {"patterns": []}}
        findings = checker.scan(self.repo_root, ignore_engine, config)

        unused = [f for f in findings if f.sub_category == "unused_dependency"]
        names = {f.evidence for f in unused}
        self.assertTrue(any("unused-package" in n for n in names))


if __name__ == "__main__":
    unittest.main()