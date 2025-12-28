import unittest
import os
from ruff_studio.ruff_adapter import run_scan_with_config

class TestRuffAdapterSimulation(unittest.TestCase):
    def setUp(self):
        self.test_py_file = "test_simulation_file.py"
        with open(self.test_py_file, "w") as f:
            # Corrected the newline characters
            f.write("import os\n\nprint('hello')\n")

    def tearDown(self):
        if os.path.exists(self.test_py_file):
            os.remove(self.test_py_file)

    def test_run_scan_with_config_selects_rule(self):
        # This config enables F401 ("unused-import")
        config = {
            "lint": {
                "select": ["F401"]
            }
        }
        results = run_scan_with_config(self.test_py_file, config)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["code"], "F401")

    def test_run_scan_with_config_ignores_rule(self):
        # This config ignores F401, so no results should be returned
        config = {
            "lint": {
                "select": ["F"], # Select all F rules
                "ignore": ["F401"] # But ignore unused-import
            }
        }
        results = run_scan_with_config(self.test_py_file, config)
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 0)

if __name__ == '__main__':
    unittest.main()
