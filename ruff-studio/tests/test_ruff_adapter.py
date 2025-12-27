import unittest
import os
import json
from ruff_studio.ruff_adapter import discover_rules, run_scan

class TestRuffAdapter(unittest.TestCase):
    def setUp(self):
        self.test_py_file = "test_file.py"
        # Corrected the file content to use single backslashes for newlines
        with open(self.test_py_file, "w") as f:
            f.write("import os\n\nprint('hello')\n")

    def tearDown(self):
        if os.path.exists(self.test_py_file):
            os.remove(self.test_py_file)

    def test_discover_rules(self):
        rules = discover_rules()
        self.assertIsInstance(rules, list)
        self.assertGreater(len(rules), 0)
        # Check for a known rule
        self.assertTrue(any(rule["code"] == "F401" for rule in rules))

    def test_run_scan(self):
        results = run_scan(self.test_py_file)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        # Check for the specific unused import error
        self.assertEqual(results[0]["code"], "F401")
        self.assertEqual(results[0]["filename"], os.path.abspath(self.test_py_file))

if __name__ == '__main__':
    unittest.main()
