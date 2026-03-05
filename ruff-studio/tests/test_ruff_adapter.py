import unittest
from unittest.mock import patch, MagicMock
import os
import json
import subprocess
import requests
from ruff_studio import ruff_adapter


class TestRuffAdapter(unittest.TestCase):
    def setUp(self):
        self.test_py_file = "test_file.py"
        with open(self.test_py_file, "w") as f:
            f.write("import os\n\nprint('hello')\n")

    def tearDown(self):
        if os.path.exists(self.test_py_file):
            os.remove(self.test_py_file)

    @patch("subprocess.run")
    def test_run_ruff_command_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="ruff 0.1.0\n", returncode=0)
        output = ruff_adapter._run_ruff_command(["--version"])
        self.assertEqual(output, "ruff 0.1.0\n")

    @patch("subprocess.run")
    def test_run_ruff_command_error(self, mock_run):
        # FileNotFoundError
        mock_run.side_effect = FileNotFoundError()
        with self.assertRaises(FileNotFoundError):
            ruff_adapter._run_ruff_command(["--version"])

        # CalledProcessError (for non-check commands)
        mock_run.side_effect = subprocess.CalledProcessError(1, "ruff", stderr=b"error")
        with self.assertRaises(RuntimeError):
            ruff_adapter._run_ruff_command(["--version"])

    @patch("ruff_studio.ruff_adapter._run_ruff_command")
    def test_get_ruff_version(self, mock_run_cmd):
        mock_run_cmd.return_value = "ruff 0.1.0\n"
        self.assertEqual(ruff_adapter.get_ruff_version(), "0.1.0")

    @patch("requests.get")
    def test_scrape_rule_documentation(self, mock_get):
        # Success
        mock_response = MagicMock()
        mock_response.content = (
            b'<article class="md-content__inner">'
            b"<h2>What it does</h2><p>Rule desc</p></article>"
        )
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        doc = ruff_adapter.scrape_rule_documentation("F401")
        self.assertIn("WHAT IT DOES", doc)
        self.assertIn("Rule desc", doc)

        # Failure
        mock_get.side_effect = requests.RequestException("Network error")
        self.assertIsNone(ruff_adapter.scrape_rule_documentation("F401"))

    @patch("ruff_studio.ruff_adapter.cache_manager")
    @patch("ruff_studio.ruff_adapter._run_ruff_command")
    @patch("ruff_studio.ruff_adapter.get_ruff_version")
    def test_discover_rules_fresh(self, mock_version, mock_run_ruff, mock_cache):
        mock_version.return_value = "0.1.0"
        mock_run_ruff.return_value = json.dumps(
            [
                {
                    "name": "Unused import",
                    "code": "F401",
                    "linter": "pyflakes",
                    "deprecated": False,
                }
            ]
        )
        mock_cache.get_cache.return_value = None

        rules = ruff_adapter.discover_rules()
        self.assertIn("pyflakes", rules)
        mock_cache.set_cache.assert_called_once()

    @patch("ruff_studio.ruff_adapter.cache_manager")
    @patch("ruff_studio.ruff_adapter.get_ruff_version")
    def test_discover_rules_from_cache(self, mock_version, mock_cache):
        mock_version.return_value = "0.1.0"
        mock_cache.get_cache.return_value = {
            "version": "0.1.0",
            "rules": {"pyflakes": {"prefix": "F", "rules": []}},
        }

        rules = ruff_adapter.discover_rules()
        self.assertIn("pyflakes", rules)

    @patch("ruff_studio.ruff_adapter._run_ruff_command")
    def test_run_scan(self, mock_run_ruff):
        mock_run_ruff.return_value = "[]"
        results = ruff_adapter.run_scan("/some/dir")
        self.assertEqual(results, [])

        mock_run_ruff.side_effect = RuntimeError("error")
        self.assertEqual(ruff_adapter.run_scan("/some/dir"), [])

    @patch("ruff_studio.ruff_adapter._run_ruff_command")
    def test_run_scan_with_config(self, mock_run_ruff):
        mock_run_ruff.return_value = "[]"
        # Use existing directory for temp file
        results = ruff_adapter.run_scan_with_config(".", {"select": ["E"]})
        self.assertEqual(results, [])

    @patch("subprocess.run")
    def test_run_ruff_command_check_logic(self, mock_run):
        # check command with violations (non-zero exit code but has stdout)
        mock_run.return_value = MagicMock(stdout='[{"code": "E501"}]', returncode=1)
        output = ruff_adapter._run_ruff_command(["check", "file.py"])
        self.assertEqual(output, '[{"code": "E501"}]')

        # check command with real failure (no stdout)
        mock_run.return_value = MagicMock(stdout="", stderr="fatal error", returncode=2)
        with self.assertRaises(RuntimeError):
            ruff_adapter._run_ruff_command(["check", "file.py"])

    @patch("ruff_studio.ruff_adapter._run_ruff_command")
    def test_get_default_rules(self, mock_run_ruff):
        # Match case
        mock_run_ruff.return_value = "linter.rules.enabled = [F401, E501]"
        self.assertEqual(ruff_adapter.get_default_rules(), {"F401", "E501"})

        # No match case
        mock_run_ruff.return_value = "no match"
        self.assertEqual(ruff_adapter.get_default_rules(), set())

        # Error case
        mock_run_ruff.side_effect = RuntimeError("error")
        self.assertEqual(ruff_adapter.get_default_rules(), set())


if __name__ == "__main__":
    unittest.main()
