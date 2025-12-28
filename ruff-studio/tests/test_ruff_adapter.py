import unittest
from unittest.mock import patch
import os
import json
from ruff_studio.ruff_adapter import _fetch_and_process_rules, run_scan

class TestRuffAdapter(unittest.TestCase):
    def setUp(self):
        self.test_py_file = "test_file.py"
        # Corrected the file content to use single backslashes for newlines
        with open(self.test_py_file, "w") as f:
            f.write("import os\n\nprint('hello')\n")

    def tearDown(self):
        if os.path.exists(self.test_py_file):
            os.remove(self.test_py_file)

    @patch("ruff_studio.ruff_adapter.scrape_rule_documentation")
    @patch("ruff_studio.ruff_adapter._run_ruff_command")
    def test_fetch_and_process_rules(self, mock_run_ruff, mock_scrape):
        # Mock the raw output from the `ruff rule --all` command
        mock_run_ruff.return_value = json.dumps([
            {"name": "Unused import", "code": "F401", "linter": "pyflakes"},
            {"name": "Some other rule", "code": "A001", "linter": "flake8-builtins"}
        ])
        mock_scrape.return_value = "Scraped documentation"

        rules = _fetch_and_process_rules()

        self.assertIsInstance(rules, dict)
        self.assertIn("pyflakes", rules)
        self.assertEqual(len(rules["pyflakes"]["rules"]), 1)

        f401_rule = rules["pyflakes"]["rules"][0]
        self.assertEqual(f401_rule["code"], "F401")
        self.assertEqual(f401_rule["documentation"], "Scraped documentation")
        self.assertEqual(f401_rule["status"], "stable")

    def test_run_scan(self):
        results = run_scan(self.test_py_file)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        # Check for the specific unused import error
        self.assertEqual(results[0]["code"], "F401")
        self.assertEqual(results[0]["filename"], os.path.abspath(self.test_py_file))

if __name__ == '__main__':
    unittest.main()
