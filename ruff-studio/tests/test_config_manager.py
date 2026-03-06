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


# ---------------------------------------------------------------------------
# Additional coverage: read_pyproject_text, get_pyproject_text,
# get_ruff_config, update_ruff_config, get_pylint_config, update_pylint_config
# ---------------------------------------------------------------------------


class TestReadPyprojectText(unittest.TestCase):
    def test_returns_raw_string_content(self, tmp_path=None):
        """read_pyproject_text returns the file contents as a plain string."""
        import tempfile, os
        from ruff_studio.config_manager import read_pyproject_text

        content = "[tool.ruff]\nline-length = 88\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write(content)
            path = f.name
        try:
            result = read_pyproject_text(path)
            self.assertEqual(result, content)
        finally:
            os.unlink(path)

    def test_preserves_comments(self):
        """read_pyproject_text preserves inline comments verbatim."""
        import tempfile, os
        from ruff_studio.config_manager import read_pyproject_text

        content = "# top comment\n[tool]\nkey = 1  # side comment\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write(content)
            path = f.name
        try:
            result = read_pyproject_text(path)
            self.assertIn("# top comment", result)
            self.assertIn("# side comment", result)
        finally:
            os.unlink(path)


class TestGetPyprojectText(unittest.TestCase):
    def test_round_trips_tomlkit_document(self):
        """get_pyproject_text serialises a tomlkit document back to TOML."""
        import tomlkit
        from ruff_studio.config_manager import get_pyproject_text

        doc = tomlkit.parse("[tool.ruff]\nline-length = 88\n")
        text = get_pyproject_text(doc)
        self.assertIn("line-length = 88", text)

    def test_preserves_comments_in_serialisation(self):
        """get_pyproject_text keeps tomlkit comment nodes when serialising."""
        import tomlkit
        from ruff_studio.config_manager import get_pyproject_text

        raw = "# comment\n[tool]\nkey = 1\n"
        doc = tomlkit.parse(raw)
        text = get_pyproject_text(doc)
        self.assertIn("# comment", text)


class TestGetRuffConfig(unittest.TestCase):
    def test_returns_empty_dict_when_data_is_none(self):
        """get_ruff_config returns {} when pyproject_data is None."""
        from ruff_studio.config_manager import get_ruff_config

        self.assertEqual(get_ruff_config(None), {})

    def test_returns_empty_dict_when_tool_section_missing(self):
        """get_ruff_config returns {} when [tool] key is absent."""
        import tomlkit
        from ruff_studio.config_manager import get_ruff_config

        doc = tomlkit.parse("[project]\nname = 'x'\n")
        self.assertEqual(get_ruff_config(doc), {})

    def test_returns_empty_dict_when_ruff_lint_missing(self):
        """get_ruff_config returns {} when [tool.ruff.lint] is absent."""
        import tomlkit
        from ruff_studio.config_manager import get_ruff_config

        doc = tomlkit.parse("[tool.ruff]\nline-length = 88\n")
        self.assertEqual(get_ruff_config(doc), {})

    def test_returns_lint_section_when_present(self):
        """get_ruff_config returns the [tool.ruff.lint] table."""
        import tomlkit
        from ruff_studio.config_manager import get_ruff_config

        raw = '[tool.ruff.lint]\nselect = ["E", "F"]\nignore = ["E501"]\n'
        doc = tomlkit.parse(raw)
        result = get_ruff_config(doc)
        self.assertEqual(list(result["select"]), ["E", "F"])
        self.assertEqual(list(result["ignore"]), ["E501"])


class TestUpdateRuffConfig(unittest.TestCase):
    def test_creates_tool_and_ruff_tables_when_absent(self):
        """update_ruff_config creates nested tables if they do not exist."""
        import tomlkit
        from ruff_studio.config_manager import update_ruff_config

        doc = tomlkit.document()
        lint_cfg = tomlkit.table()
        lint_cfg["select"] = ["E"]
        update_ruff_config(doc, lint_cfg)

        self.assertEqual(doc["tool"]["ruff"]["lint"]["select"], ["E"])

    def test_overwrites_existing_lint_section(self):
        """update_ruff_config replaces the existing [tool.ruff.lint] table."""
        import tomlkit
        from ruff_studio.config_manager import update_ruff_config, get_ruff_config

        raw = '[tool.ruff.lint]\nselect = ["E"]\n'
        doc = tomlkit.parse(raw)
        new_lint = tomlkit.table()
        new_lint["select"] = ["F"]
        new_lint["ignore"] = ["F401"]
        update_ruff_config(doc, new_lint)

        result = get_ruff_config(doc)
        self.assertEqual(list(result["select"]), ["F"])
        self.assertEqual(list(result["ignore"]), ["F401"])

    def test_persists_to_disk_via_write_pyproject(self):
        """update_ruff_config changes are visible after a write/read cycle."""
        import tempfile, os, tomlkit
        from ruff_studio.config_manager import (
            update_ruff_config,
            write_pyproject,
            read_pyproject,
            get_ruff_config,
        )

        doc = tomlkit.parse("[tool.ruff]\nline-length = 88\n")
        lint_cfg = tomlkit.table()
        lint_cfg["select"] = ["B"]
        update_ruff_config(doc, lint_cfg)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            path = f.name
        try:
            write_pyproject(path, doc)
            reloaded = read_pyproject(path)
            self.assertEqual(list(get_ruff_config(reloaded)["select"]), ["B"])
        finally:
            os.unlink(path)


class TestGetPylintConfig(unittest.TestCase):
    def test_returns_empty_dict_when_data_is_none(self):
        """get_pylint_config returns {} when pyproject_data is None."""
        from ruff_studio.config_manager import get_pylint_config

        self.assertEqual(get_pylint_config(None), {})

    def test_returns_empty_dict_when_tool_section_missing(self):
        """get_pylint_config returns {} when [tool] key is absent."""
        import tomlkit
        from ruff_studio.config_manager import get_pylint_config

        doc = tomlkit.parse("[project]\nname = 'x'\n")
        self.assertEqual(get_pylint_config(doc), {})

    def test_returns_empty_dict_when_pylint_section_missing(self):
        """get_pylint_config returns {} when [tool.pylint] is absent."""
        import tomlkit
        from ruff_studio.config_manager import get_pylint_config

        doc = tomlkit.parse("[tool.ruff]\nline-length = 88\n")
        self.assertEqual(get_pylint_config(doc), {})

    def test_returns_pylint_section_when_present(self):
        """get_pylint_config returns the [tool.pylint] table."""
        import tomlkit
        from ruff_studio.config_manager import get_pylint_config

        raw = '[tool.pylint]\ndisable = ["C0114"]\n'
        doc = tomlkit.parse(raw)
        result = get_pylint_config(doc)
        self.assertEqual(list(result["disable"]), ["C0114"])


class TestUpdatePylintConfig(unittest.TestCase):
    def test_creates_tool_table_when_absent(self):
        """update_pylint_config creates [tool] if it does not exist."""
        import tomlkit
        from ruff_studio.config_manager import update_pylint_config

        doc = tomlkit.document()
        cfg = tomlkit.table()
        cfg["disable"] = ["C0114"]
        update_pylint_config(doc, cfg)

        self.assertEqual(doc["tool"]["pylint"]["disable"], ["C0114"])

    def test_overwrites_existing_pylint_section(self):
        """update_pylint_config replaces an existing [tool.pylint] table."""
        import tomlkit
        from ruff_studio.config_manager import update_pylint_config, get_pylint_config

        raw = '[tool.pylint]\ndisable = ["C0114"]\n'
        doc = tomlkit.parse(raw)
        new_cfg = tomlkit.table()
        new_cfg["disable"] = ["W0611"]
        new_cfg["enable"] = ["C0115"]
        update_pylint_config(doc, new_cfg)

        result = get_pylint_config(doc)
        self.assertEqual(list(result["disable"]), ["W0611"])
        self.assertEqual(list(result["enable"]), ["C0115"])

    def test_persists_to_disk_via_write_pyproject(self):
        """update_pylint_config changes are visible after a write/read cycle."""
        import tempfile, os, tomlkit
        from ruff_studio.config_manager import (
            update_pylint_config,
            write_pyproject,
            read_pyproject,
            get_pylint_config,
        )

        doc = tomlkit.parse("[tool.ruff]\nline-length = 88\n")
        cfg = tomlkit.table()
        cfg["disable"] = ["C0114", "W0611"]
        update_pylint_config(doc, cfg)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            path = f.name
        try:
            write_pyproject(path, doc)
            reloaded = read_pyproject(path)
            result = get_pylint_config(reloaded)
            self.assertIn("C0114", list(result["disable"]))
            self.assertIn("W0611", list(result["disable"]))
        finally:
            os.unlink(path)
