import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestSetupScript(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.repo_root = Path(__file__).parent.parent
        self.setup_script = self.repo_root / "setup.sh"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_help(self):
        result = subprocess.run(
            [str(self.setup_script), "--help"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)

    def test_install_to_custom_dir(self):
        dest = Path(self.temp_dir) / "custom_skill"
        result = subprocess.run(
            [str(self.setup_script), str(dest)],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue((dest / "SKILL.md").exists())
        
        content = (dest / "SKILL.md").read_text()
        self.assertIn("Code Hygiene Skill", content)

    def test_rerun_safe(self):
        dest = Path(self.temp_dir) / "rerun_test"
        
        # First run
        subprocess.run([str(self.setup_script), str(dest)], capture_output=True, text=True)
        
        # Second run
        result = subprocess.run(
            [str(self.setup_script), str(dest)],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Overwriting existing skill", result.stdout)
        self.assertTrue((dest / "SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()