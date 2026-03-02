import unittest
from unittest.mock import patch
import os
import json
from ruff_studio.ruff_adapter import discover_rules, run_scan, get_default_rules

class TestRuffAdapter(unittest.TestCase):
    def setUp(self):
        self.test_py_file = "test_file.py"
        with open(self.test_py_file, "w") as f:
            f.write("import os\n\nprint('hello')\n")

    def tearDown(self):
        if os.path.exists(self.test_py_file):
            os.remove(self.test_py_file)

    @patch("ruff_studio.ruff_adapter.cache_manager")
    @patch("ruff_studio.ruff_adapter._run_ruff_command")
    def test_discover_rules_caching(
        self, mock_run_ruff, mock_cache_manager
    ):
        # --- SCENARIO 1: No cache exists, scrape and cache everything ---
        mock_run_ruff.return_value = json.dumps([
            {"name": "Unused import", "code": "F401", "linter": "pyflakes"},
            {"name": "Some other rule", "code": "A001", "linter": "flake8-builtins"}
        ])
        mock_cache_manager.get_cache.return_value = None

        rules = discover_rules()

        # Verify final structure
        self.assertIn("pyflakes", rules)
        doc = rules["pyflakes"]["rules"][0]["documentation"]
        self.assertIsNone(doc)

        # Verify that the cache was written to
        mock_cache_manager.set_cache.assert_called_once()

    def test_run_scan(self):
        results = run_scan(self.test_py_file)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["code"], "F401")
        self.assertEqual(results[0]["filename"], os.path.abspath(self.test_py_file))

    @patch("ruff_studio.ruff_adapter._run_ruff_command")
    def test_get_default_rules(self, mock_run_ruff):
        mock_output = """
        linter.rules.enabled = [
            E402,
            E501,
            E701,
            F841,
            F401,
        ]
        """
        mock_run_ruff.return_value = mock_output

        default_rules = get_default_rules()

        self.assertEqual(default_rules, {"E402", "E501", "E701", "F841", "F401"})

if __name__ == '__main__':
    unittest.main()
