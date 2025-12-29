import unittest
from unittest.mock import patch, mock_open
import os
import json
from ruff_studio.ruff_adapter import discover_rules, run_scan

class TestRuffAdapter(unittest.TestCase):
    def setUp(self):
        self.test_py_file = "test_file.py"
        with open(self.test_py_file, "w") as f:
            f.write("import os\n\nprint('hello')\n")

    def tearDown(self):
        if os.path.exists(self.test_py_file):
            os.remove(self.test_py_file)

    @patch("ruff_studio.ruff_adapter.scrape_rule_documentation")
    @patch("ruff_studio.ruff_adapter._run_ruff_command")
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_discover_rules_incremental_caching(self, mock_file, mock_exists, mock_run_ruff, mock_scrape):
        # --- SCENARIO 1: No cache exists, scrape and cache everything ---
        mock_exists.return_value = False
        mock_run_ruff.return_value = json.dumps([
            {"name": "Unused import", "code": "F401", "linter": "pyflakes"},
            {"name": "Some other rule", "code": "A001", "linter": "flake8-builtins"}
        ])
        mock_scrape.return_value = "--- WHAT IT DOES ---\nScraped documentation"

        rules = discover_rules()

        # Verify final structure
        self.assertIn("pyflakes", rules)
        self.assertEqual(rules["pyflakes"]["rules"][0]["documentation"], "--- WHAT IT DOES ---\nScraped documentation")

        # Verify that the file was opened for writing twice (once per rule)
        self.assertEqual(mock_file.call_count, 2)

        # --- SCENARIO 2: Partial cache exists, scrape only missing rule ---

        # Reset mocks
        mock_file.reset_mock()
        mock_scrape.reset_mock()

        # Simulate a cache file that only has the F401 rule
        partial_cache_content = json.dumps({
            "pyflakes": {
                "prefix": "F",
                "rules": [{
                    "name": "Unused import", "code": "F401", "linter": "pyflakes",
                    "documentation": "Existing documentation"
                }]
            }
        })
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = partial_cache_content

        # `discover_rules` is called again
        rules = discover_rules()

        # Verify that scrape was only called ONCE for the missing A001 rule
        mock_scrape.assert_called_once_with("Some other rule")

        # Verify the final data contains both rules, with old and new docs
        self.assertEqual(rules["pyflakes"]["rules"][0]["documentation"], "Existing documentation")
        self.assertEqual(rules["flake8-builtins"]["rules"][0]["documentation"], "--- WHAT IT DOES ---\nScraped documentation")

        # Verify that the file was opened once to read and once to write
        self.assertEqual(mock_file.call_count, 2)

    def test_run_scan(self):
        results = run_scan(self.test_py_file)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["code"], "F401")
        self.assertEqual(results[0]["filename"], os.path.abspath(self.test_py_file))

if __name__ == '__main__':
    unittest.main()
