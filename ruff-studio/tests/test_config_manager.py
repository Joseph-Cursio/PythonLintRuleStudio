import unittest
from ruff_studio.config_manager import read_pyproject, write_pyproject
import os


class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.test_toml_path = "test_pyproject.toml"
        self.output_toml_path = "output_pyproject.toml"
        # Create a dummy pyproject.toml file with comments and specific formatting
        self.toml_content = """
# This is a comment
[tool.poetry]
name = "test-project"
version = "0.1.0" # version comment

[tool.ruff]
# another comment
line-length = 88
"""
        with open(self.test_toml_path, "w") as f:
            f.write(self.toml_content)

    def tearDown(self):
        if os.path.exists(self.test_toml_path):
            os.remove(self.test_toml_path)
        if os.path.exists(self.output_toml_path):
            os.remove(self.output_toml_path)

    def test_toml_round_trip_preserves_style(self):
        # Read the TOML file
        data = read_pyproject(self.test_toml_path)

        # Modify the data
        data["tool"]["ruff"]["line-length"] = 100

        # Write the data to a new file
        write_pyproject(self.output_toml_path, data)

        with open(self.output_toml_path, "r") as f:
            new_content = f.read()

        # Assert that the new content contains the modification
        self.assertIn("line-length = 100", new_content)

        # Assert that comments and structure are preserved
        # (tomlkit doesn't guarantee exact byte-for-byte reproduction,
        # but comments should be there)
        self.assertIn("# This is a comment", new_content)
        self.assertIn("# version comment", new_content)
        self.assertIn("# another comment", new_content)


if __name__ == "__main__":
    unittest.main()
