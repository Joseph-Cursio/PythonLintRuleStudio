import unittest
from unittest.mock import MagicMock
import tomlkit
from ruff_studio.main import App

class TestConfigGeneration(unittest.TestCase):
    def setUp(self):
        # Mock the App class to isolate the get_effective_config method
        self.app = App(headless=True)
        self.app.pyproject_data = tomlkit.document()
        self.app.managed_prefixes = {"F", "E"}
        self.app.managed_rules = {"F401", "E501"}
        self.app.rule_widgets = {
            "pyflakes": {"prefix": "F", "rules": {"F401": {}}},
            "pycodestyle": {"prefix": "E", "rules": {"E501": {}}},
        }

    def test_select_category(self):
        self.app.staged_changes = {"F": "select"}
        config = self.app.get_effective_config()
        self.assertEqual(config["select"], ["F"])
        self.assertEqual(config["ignore"], [])

    def test_ignore_category(self):
        self.app.staged_changes = {"F": "ignore"}
        config = self.app.get_effective_config()
        self.assertEqual(config["select"], [])
        self.assertEqual(config["ignore"], ["F"])

    def test_select_individual_rule(self):
        self.app.staged_changes = {"F401": "select"}
        config = self.app.get_effective_config()
        self.assertEqual(config["select"], ["F401"])
        self.assertEqual(config["ignore"], [])

    def test_ignore_individual_rule(self):
        self.app.staged_changes = {"F401": "ignore"}
        config = self.app.get_effective_config()
        self.assertEqual(config["select"], [])
        self.assertEqual(config["ignore"], ["F401"])

    def test_mixed_changes(self):
        self.app.staged_changes = {"F": "select", "E501": "ignore"}
        config = self.app.get_effective_config()
        self.assertEqual(config["select"], ["F"])
        self.assertEqual(config["ignore"], ["E501"])

    def test_default_does_not_add_to_config(self):
        self.app.staged_changes = {"F": "default"}
        config = self.app.get_effective_config()
        self.assertEqual(config["select"], [])
        self.assertEqual(config["ignore"], [])

if __name__ == "__main__":
    unittest.main()
