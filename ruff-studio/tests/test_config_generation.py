import unittest
import tomlkit
from ruff_studio.main import App


class TestConfigGeneration(unittest.TestCase):
    def setUp(self):
        # Mock the App class to isolate the get_effective_configs method
        self.app = App(headless=True)
        self.app.controller.pyproject_data = tomlkit.document()
        self.app.controller.all_rules = {
            "pyflakes": {"prefix": "F", "rules": [{"code": "F401"}]},
            "pycodestyle": {"prefix": "E", "rules": [{"code": "E501"}]},
            "Pylint: Convention": {"prefix": "C", "rules": [{"code": "C0103"}]},
        }

    def test_select_category(self):
        self.app.controller.staged_changes = {"F": "select"}
        ruff_config, _ = self.app.controller.get_effective_configs()
        self.assertEqual(ruff_config["select"], ["F"])
        self.assertEqual(ruff_config["ignore"], [])

    def test_ignore_category(self):
        self.app.controller.staged_changes = {"F": "ignore"}
        ruff_config, _ = self.app.controller.get_effective_configs()
        self.assertEqual(ruff_config["select"], [])
        self.assertEqual(ruff_config["ignore"], ["F"])

    def test_select_individual_rule(self):
        self.app.controller.staged_changes = {"F401": "select"}
        ruff_config, _ = self.app.controller.get_effective_configs()
        self.assertEqual(ruff_config["select"], ["F401"])
        self.assertEqual(ruff_config["ignore"], [])

    def test_ignore_individual_rule(self):
        self.app.controller.staged_changes = {"F401": "ignore"}
        ruff_config, _ = self.app.controller.get_effective_configs()
        self.assertEqual(ruff_config["select"], [])
        self.assertEqual(ruff_config["ignore"], ["F401"])

    def test_mixed_changes(self):
        self.app.controller.staged_changes = {"F": "select", "E501": "ignore"}
        ruff_config, _ = self.app.controller.get_effective_configs()
        self.assertEqual(ruff_config["select"], ["F"])
        self.assertEqual(ruff_config["ignore"], ["E501"])

    def test_default_does_not_add_to_config(self):
        self.app.controller.staged_changes = {"F": "default"}
        ruff_config, _ = self.app.controller.get_effective_configs()
        self.assertEqual(ruff_config["select"], [])
        self.assertEqual(ruff_config["ignore"], [])

    def test_pylint_disable_rule(self):
        self.app.controller.staged_changes = {"C0103": "ignore"}
        _, pylint_config = self.app.controller.get_effective_configs()
        self.assertEqual(pylint_config["disable"], ["C0103"])
        self.assertNotIn("enable", pylint_config)


if __name__ == "__main__":
    unittest.main()
