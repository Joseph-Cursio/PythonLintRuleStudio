"""
Tests for StudioController (controller.py).

All external I/O (file system, subprocesses, DB) is mocked so the suite runs
fast and without side-effects.  The WorkspaceAnalyzer is replaced with a
MagicMock for every test that does not need it at all; tests that probe
the analyzer-proxy methods set up return values on that mock.
"""

import os
import queue
import tempfile
import tomlkit
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SIMPLE_PYPROJECT = """\
[tool.ruff.lint]
select = ["E", "F"]
ignore = ["E501"]

[tool.pylint]
disable = ["C0114"]
"""


def _make_controller(db_path=":memory:"):
    """Return a StudioController whose WorkspaceAnalyzer is mocked out."""
    with patch("ruff_studio.workspace_analyzer.WorkspaceAnalyzer") as MockAnalyzer:
        MockAnalyzer.return_value = MagicMock()
        from ruff_studio.controller import StudioController

        ctrl = StudioController(db_path=db_path)
    return ctrl


def _controller_with_pyproject(toml_text=_SIMPLE_PYPROJECT):
    """Return a controller that has loaded a real pyproject.toml from a temp dir."""
    ctrl = _make_controller()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "pyproject.toml")
        with open(path, "w") as f:
            f.write(toml_text)
        ctrl.set_directory(tmpdir)
        # Keep the data alive after the tmpdir is torn down
        ctrl._tmpdir_path = tmpdir  # for reference; not used after this point
    return ctrl


# ---------------------------------------------------------------------------
# set_directory
# ---------------------------------------------------------------------------


class TestSetDirectory(unittest.TestCase):
    def test_loads_pyproject_when_file_exists(self):
        """set_directory reads pyproject_data when pyproject.toml is present."""
        ctrl = _make_controller()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "pyproject.toml")
            with open(path, "w") as f:
                f.write(_SIMPLE_PYPROJECT)
            ctrl.set_directory(tmpdir)

        self.assertEqual(ctrl.current_directory, tmpdir)
        self.assertIsNotNone(ctrl.pyproject_data)
        self.assertIn("tool", ctrl.pyproject_data)

    def test_pyproject_path_set_correctly(self):
        """set_directory builds pyproject_path from the given directory."""
        ctrl = _make_controller()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctrl.set_directory(tmpdir)
        expected = os.path.join(tmpdir, "pyproject.toml")
        self.assertEqual(ctrl.pyproject_path, expected)

    def test_staged_changes_reset(self):
        """set_directory clears any previously staged changes."""
        ctrl = _make_controller()
        ctrl.staged_changes = {"E501": "ignore"}
        with tempfile.TemporaryDirectory() as tmpdir:
            ctrl.set_directory(tmpdir)
        self.assertEqual(ctrl.staged_changes, {})

    def test_pyproject_data_is_none_when_file_absent(self):
        """set_directory sets pyproject_data to None when file is missing."""
        ctrl = _make_controller()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctrl.set_directory(tmpdir)  # no pyproject.toml created
        self.assertIsNone(ctrl.pyproject_data)

    def test_pyproject_data_is_none_when_read_raises(self):
        """set_directory sets pyproject_data to None when parsing fails."""
        ctrl = _make_controller()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "pyproject.toml")
            with open(path, "w") as f:
                f.write(_SIMPLE_PYPROJECT)

            with patch(
                "ruff_studio.config_manager.read_pyproject",
                side_effect=Exception("parse error"),
            ):
                ctrl.set_directory(tmpdir)

        self.assertIsNone(ctrl.pyproject_data)


# ---------------------------------------------------------------------------
# discover_rules_worker
# ---------------------------------------------------------------------------


class TestDiscoverRulesWorker(unittest.TestCase):
    def _ctrl(self):
        return _make_controller()

    @patch("ruff_studio.pylint_adapter.discover_rules")
    @patch("ruff_studio.ruff_adapter.discover_rules")
    def test_success_puts_combined_rules_on_queue(
        self, mock_ruff_discover, mock_pylint_discover
    ):
        """discover_rules_worker merges ruff and pylint rules and enqueues them."""
        mock_ruff_discover.return_value = {"E": {"rules": [], "is_pylint": False}}
        mock_pylint_discover.return_value = {"Convention": {"rules": [], "is_pylint": True}}

        ctrl = self._ctrl()
        ctrl.discover_rules_worker("rules_ready")

        cmd, data = ctrl.queue.get_nowait()
        self.assertEqual(cmd, "rules_ready")
        self.assertIn("E", data)
        self.assertIn("Pylint: Convention", data)

    @patch("ruff_studio.pylint_adapter.discover_rules")
    @patch("ruff_studio.ruff_adapter.discover_rules")
    def test_pylint_keys_are_prefixed(self, mock_ruff_discover, mock_pylint_discover):
        """discover_rules_worker prefixes pylint category keys with 'Pylint: '."""
        mock_ruff_discover.return_value = {}
        mock_pylint_discover.return_value = {
            "Warning": {"rules": []},
            "Refactor": {"rules": []},
        }

        ctrl = self._ctrl()
        ctrl.discover_rules_worker("cmd")

        _, data = ctrl.queue.get_nowait()
        self.assertIn("Pylint: Warning", data)
        self.assertIn("Pylint: Refactor", data)
        self.assertNotIn("Warning", data)

    @patch(
        "ruff_studio.ruff_adapter.discover_rules",
        side_effect=RuntimeError("ruff not found"),
    )
    def test_error_puts_error_tuple_on_queue(self, _mock):
        """discover_rules_worker enqueues ('error', message) on exception."""
        ctrl = self._ctrl()
        ctrl.discover_rules_worker("cmd")

        cmd, msg = ctrl.queue.get_nowait()
        self.assertEqual(cmd, "error")
        self.assertIn("ruff not found", msg)


# ---------------------------------------------------------------------------
# run_full_scan_worker
# ---------------------------------------------------------------------------


class TestRunFullScanWorker(unittest.TestCase):
    def test_success_puts_results_on_queue(self):
        """run_full_scan_worker enqueues scan results on success."""
        ctrl = _make_controller()
        ctrl.pyproject_data = tomlkit.parse(_SIMPLE_PYPROJECT)
        fake_results = [{"file": "a.py", "violations": []}]
        ctrl.analyzer.run_full_scan.return_value = fake_results

        ctrl.run_full_scan_worker("scan_done", "/some/dir")

        cmd, results = ctrl.queue.get_nowait()
        self.assertEqual(cmd, "scan_done")
        self.assertEqual(results, fake_results)

    def test_analyzer_called_with_effective_config(self):
        """run_full_scan_worker passes ruff/pylint configs to the analyzer."""
        ctrl = _make_controller()
        ctrl.pyproject_data = tomlkit.parse(_SIMPLE_PYPROJECT)
        ctrl.analyzer.run_full_scan.return_value = []

        ctrl.run_full_scan_worker("scan_done", "/proj")

        call_kwargs = ctrl.analyzer.run_full_scan.call_args
        config_arg = call_kwargs[1]["config"]
        self.assertIn("ruff", config_arg)
        self.assertIn("pylint", config_arg)

    def test_error_puts_error_tuple_on_queue(self):
        """run_full_scan_worker enqueues ('error', message) on exception."""
        ctrl = _make_controller()
        ctrl.pyproject_data = tomlkit.parse(_SIMPLE_PYPROJECT)
        ctrl.analyzer.run_full_scan.side_effect = OSError("disk full")

        ctrl.run_full_scan_worker("scan_done", "/proj")

        cmd, msg = ctrl.queue.get_nowait()
        self.assertEqual(cmd, "error")
        self.assertIn("disk full", msg)


# ---------------------------------------------------------------------------
# Analyzer proxy methods
# ---------------------------------------------------------------------------


class TestAnalyzerProxies(unittest.TestCase):
    def setUp(self):
        self.ctrl = _make_controller()

    def test_get_scan_history_delegates_to_analyzer(self):
        self.ctrl.analyzer.get_scan_history.return_value = [{"id": 1}]
        result = self.ctrl.get_scan_history()
        self.ctrl.analyzer.get_scan_history.assert_called_once()
        self.assertEqual(result, [{"id": 1}])

    def test_get_author_stats_delegates_to_analyzer(self):
        self.ctrl.analyzer.get_author_stats.return_value = {"alice": 5}
        result = self.ctrl.get_author_stats()
        self.ctrl.analyzer.get_author_stats.assert_called_once()
        self.assertEqual(result, {"alice": 5})

    def test_get_rule_hotspots_delegates_to_analyzer(self):
        self.ctrl.analyzer.get_rule_hotspots.return_value = [("E501", 10)]
        result = self.ctrl.get_rule_hotspots()
        self.ctrl.analyzer.get_rule_hotspots.assert_called_once()
        self.assertEqual(result, [("E501", 10)])

    def test_get_violation_trend_delegates_to_analyzer(self):
        self.ctrl.analyzer.get_total_violations_trend.return_value = [1, 2, 3]
        result = self.ctrl.get_violation_trend()
        self.ctrl.analyzer.get_total_violations_trend.assert_called_once()
        self.assertEqual(result, [1, 2, 3])


# ---------------------------------------------------------------------------
# get_effective_configs
# ---------------------------------------------------------------------------


class TestGetEffectiveConfigs(unittest.TestCase):
    def test_returns_empty_dicts_when_no_pyproject(self):
        """get_effective_configs returns ({}, {}) when pyproject_data is None."""
        ctrl = _make_controller()
        ctrl.pyproject_data = None
        ruff, pylint = ctrl.get_effective_configs()
        self.assertEqual(ruff, {})
        self.assertEqual(pylint, {})

    def test_baseline_config_without_staged_changes(self):
        """get_effective_configs reflects the pyproject values when no changes are staged."""
        ctrl = _make_controller()
        ctrl.pyproject_data = tomlkit.parse(_SIMPLE_PYPROJECT)
        ruff, pylint = ctrl.get_effective_configs()

        self.assertIn("E", ruff["select"])
        self.assertIn("F", ruff["select"])
        self.assertIn("E501", ruff["ignore"])
        self.assertIn("C0114", pylint["disable"])

    # --- Ruff staged changes ---

    def test_staged_ruff_select_adds_to_select(self):
        """Staging a ruff rule as 'select' moves it into ruff select list."""
        ctrl = _make_controller()
        ctrl.pyproject_data = tomlkit.parse("[tool.ruff.lint]\nselect = []\nignore = []\n")
        ctrl.staged_changes = {"E711": "select"}
        ruff, _ = ctrl.get_effective_configs()
        self.assertIn("E711", ruff["select"])
        self.assertNotIn("E711", ruff["ignore"])

    def test_staged_ruff_ignore_adds_to_ignore(self):
        """Staging a ruff rule as 'ignore' moves it into ruff ignore list."""
        ctrl = _make_controller()
        ctrl.pyproject_data = tomlkit.parse(
            "[tool.ruff.lint]\nselect = [\"E711\"]\nignore = []\n"
        )
        ctrl.staged_changes = {"E711": "ignore"}
        ruff, _ = ctrl.get_effective_configs()
        self.assertIn("E711", ruff["ignore"])
        self.assertNotIn("E711", ruff["select"])

    def test_staged_ruff_default_removes_from_both(self):
        """Staging a ruff rule as 'default' removes it from select and ignore."""
        ctrl = _make_controller()
        ctrl.pyproject_data = tomlkit.parse(
            "[tool.ruff.lint]\nselect = [\"E711\"]\nignore = []\n"
        )
        ctrl.staged_changes = {"E711": "default"}
        ruff, _ = ctrl.get_effective_configs()
        self.assertNotIn("E711", ruff["select"])
        self.assertNotIn("E711", ruff["ignore"])

    # --- Pylint staged changes ---

    def test_staged_pylint_select_adds_to_enable(self):
        """Staging a pylint rule as 'select' adds it to pylint enable list."""
        ctrl = _make_controller()
        ctrl.pyproject_data = tomlkit.parse("[tool.pylint]\ndisable = []\n")
        ctrl.staged_changes = {"C0115": "select"}
        _, pylint = ctrl.get_effective_configs()
        self.assertIn("C0115", pylint["enable"])
        self.assertNotIn("C0115", pylint.get("disable", []))

    def test_staged_pylint_ignore_adds_to_disable(self):
        """Staging a pylint rule as 'ignore' adds it to pylint disable list."""
        ctrl = _make_controller()
        ctrl.pyproject_data = tomlkit.parse("[tool.pylint]\ndisable = []\n")
        ctrl.staged_changes = {"C0115": "ignore"}
        _, pylint = ctrl.get_effective_configs()
        self.assertIn("C0115", pylint["disable"])
        self.assertNotIn("C0115", pylint.get("enable", []))

    def test_staged_pylint_default_removes_from_both(self):
        """Staging a pylint rule as 'default' removes it from disable and enable."""
        ctrl = _make_controller()
        ctrl.pyproject_data = tomlkit.parse(
            "[tool.pylint]\ndisable = [\"C0115\"]\nenable = []\n"
        )
        ctrl.staged_changes = {"C0115": "default"}
        _, pylint = ctrl.get_effective_configs()
        self.assertNotIn("C0115", pylint.get("disable", []))
        self.assertNotIn("C0115", pylint.get("enable", []))

    def test_pylint_disable_key_removed_when_empty_after_default(self):
        """get_effective_configs removes 'disable' key when the set becomes empty."""
        ctrl = _make_controller()
        ctrl.pyproject_data = tomlkit.parse("[tool.pylint]\ndisable = [\"C0115\"]\n")
        ctrl.staged_changes = {"C0115": "default"}
        _, pylint = ctrl.get_effective_configs()
        self.assertNotIn("disable", pylint)

    def test_ruff_select_and_ignore_are_sorted(self):
        """get_effective_configs returns sorted select and ignore lists."""
        ctrl = _make_controller()
        ctrl.pyproject_data = tomlkit.parse(
            "[tool.ruff.lint]\nselect = [\"F\", \"B\", \"E\"]\nignore = [\"E501\", \"B006\"]\n"
        )
        ruff, _ = ctrl.get_effective_configs()
        self.assertEqual(ruff["select"], sorted(ruff["select"]))
        self.assertEqual(ruff["ignore"], sorted(ruff["ignore"]))


# ---------------------------------------------------------------------------
# is_pylint_rule
# ---------------------------------------------------------------------------


class TestIsPylintRule(unittest.TestCase):
    def setUp(self):
        self.ctrl = _make_controller()

    def test_single_char_prefix_C_is_pylint(self):
        self.assertTrue(self.ctrl.is_pylint_rule("C0114"))

    def test_single_char_prefix_R_is_pylint(self):
        self.assertTrue(self.ctrl.is_pylint_rule("R0201"))

    def test_single_char_prefix_W_is_pylint(self):
        self.assertTrue(self.ctrl.is_pylint_rule("W0611"))

    def test_single_char_prefix_I_is_pylint(self):
        self.assertTrue(self.ctrl.is_pylint_rule("I0001"))

    def test_long_code_is_pylint(self):
        """Any code longer than 5 characters is treated as pylint."""
        self.assertTrue(self.ctrl.is_pylint_rule("missing-docstring"))

    def test_E_code_is_not_pylint(self):
        self.assertFalse(self.ctrl.is_pylint_rule("E501"))

    def test_F_code_is_not_pylint(self):
        self.assertFalse(self.ctrl.is_pylint_rule("F401"))

    def test_B_code_is_not_pylint(self):
        self.assertFalse(self.ctrl.is_pylint_rule("B006"))

    def test_ANN_code_is_not_pylint(self):
        # ANN201 is exactly 6 chars — but does not start with C/R/W/I
        # len("ANN201") == 6 > 5, so it IS treated as pylint by current logic
        self.assertTrue(self.ctrl.is_pylint_rule("ANN201"))

    def test_short_ruff_code_not_pylint(self):
        self.assertFalse(self.ctrl.is_pylint_rule("E711"))


# ---------------------------------------------------------------------------
# get_color_for_prefix
# ---------------------------------------------------------------------------


class TestGetColorForPrefix(unittest.TestCase):
    def setUp(self):
        self.ctrl = _make_controller()

    def test_E_prefix_returns_red(self):
        dark, light = self.ctrl.get_color_for_prefix("E")
        self.assertEqual(dark, "#f44336")

    def test_F_prefix_returns_red(self):
        dark, _ = self.ctrl.get_color_for_prefix("F")
        self.assertEqual(dark, "#f44336")

    def test_B_prefix_returns_red(self):
        dark, _ = self.ctrl.get_color_for_prefix("B")
        self.assertEqual(dark, "#f44336")

    def test_ERR_prefix_returns_red(self):
        dark, _ = self.ctrl.get_color_for_prefix("ERR")
        self.assertEqual(dark, "#f44336")

    def test_W_prefix_returns_amber(self):
        dark, _ = self.ctrl.get_color_for_prefix("W")
        self.assertEqual(dark, "#ff9800")

    def test_ANN_prefix_returns_amber(self):
        dark, _ = self.ctrl.get_color_for_prefix("ANN")
        self.assertEqual(dark, "#ff9800")

    def test_WARN_prefix_returns_amber(self):
        dark, _ = self.ctrl.get_color_for_prefix("WARN")
        self.assertEqual(dark, "#ff9800")

    def test_C_prefix_returns_blue(self):
        dark, _ = self.ctrl.get_color_for_prefix("C")
        self.assertEqual(dark, "#2196f3")

    def test_PL_prefix_returns_blue(self):
        dark, _ = self.ctrl.get_color_for_prefix("PL")
        self.assertEqual(dark, "#2196f3")

    def test_R_prefix_returns_blue(self):
        dark, _ = self.ctrl.get_color_for_prefix("R")
        self.assertEqual(dark, "#2196f3")

    def test_I_prefix_returns_green(self):
        dark, _ = self.ctrl.get_color_for_prefix("I")
        self.assertEqual(dark, "#4caf50")

    def test_D_prefix_returns_green(self):
        dark, _ = self.ctrl.get_color_for_prefix("D")
        self.assertEqual(dark, "#4caf50")

    def test_N_prefix_returns_green(self):
        dark, _ = self.ctrl.get_color_for_prefix("N")
        self.assertEqual(dark, "#4caf50")

    def test_PERF_prefix_returns_green(self):
        dark, _ = self.ctrl.get_color_for_prefix("PERF")
        self.assertEqual(dark, "#4caf50")

    def test_S_prefix_returns_green(self):
        dark, _ = self.ctrl.get_color_for_prefix("S")
        self.assertEqual(dark, "#4caf50")

    def test_unknown_prefix_returns_gray(self):
        dark, _ = self.ctrl.get_color_for_prefix("XYZ")
        self.assertEqual(dark, "#9e9e9e")

    def test_lowercase_input_normalised(self):
        """get_color_for_prefix uppercases the prefix before comparison."""
        dark_lower, _ = self.ctrl.get_color_for_prefix("e")
        dark_upper, _ = self.ctrl.get_color_for_prefix("E")
        self.assertEqual(dark_lower, dark_upper)


# ---------------------------------------------------------------------------
# get_explicit_rule_state
# ---------------------------------------------------------------------------


class TestGetExplicitRuleState(unittest.TestCase):
    def setUp(self):
        self.ctrl = _make_controller()

    # --- Ruff rules ---

    def test_ruff_rule_in_select_returns_select(self):
        ruff_cfg = {"select": ["E501"], "ignore": []}
        self.assertEqual(self.ctrl.get_explicit_rule_state("E501", ruff_cfg), "select")

    def test_ruff_rule_in_ignore_returns_ignore(self):
        ruff_cfg = {"select": [], "ignore": ["E501"]}
        self.assertEqual(self.ctrl.get_explicit_rule_state("E501", ruff_cfg), "ignore")

    def test_ruff_rule_not_in_either_returns_default(self):
        ruff_cfg = {"select": [], "ignore": []}
        self.assertEqual(self.ctrl.get_explicit_rule_state("E501", ruff_cfg), "default")

    # --- Pylint rules ---

    def test_pylint_rule_in_disable_returns_ignore(self):
        ruff_cfg = {}
        pylint_cfg = {"disable": ["C0114"], "enable": []}
        self.assertEqual(
            self.ctrl.get_explicit_rule_state("C0114", ruff_cfg, pylint_cfg), "ignore"
        )

    def test_pylint_rule_in_enable_returns_select(self):
        ruff_cfg = {}
        pylint_cfg = {"disable": [], "enable": ["C0114"]}
        self.assertEqual(
            self.ctrl.get_explicit_rule_state("C0114", ruff_cfg, pylint_cfg), "select"
        )

    def test_pylint_rule_in_neither_returns_default(self):
        ruff_cfg = {}
        pylint_cfg = {"disable": [], "enable": []}
        self.assertEqual(
            self.ctrl.get_explicit_rule_state("C0114", ruff_cfg, pylint_cfg), "default"
        )

    def test_pylint_rule_with_no_pylint_config_returns_default(self):
        """Passing pylint_config=None for a pylint rule always returns 'default'."""
        ruff_cfg = {}
        self.assertEqual(
            self.ctrl.get_explicit_rule_state("C0114", ruff_cfg, pylint_config=None),
            "default",
        )


# ---------------------------------------------------------------------------
# get_effective_rule_state
# ---------------------------------------------------------------------------


class TestGetEffectiveRuleState(unittest.TestCase):
    def _ctrl_with_data(self, toml_text=_SIMPLE_PYPROJECT):
        ctrl = _make_controller()
        ctrl.pyproject_data = tomlkit.parse(toml_text)
        return ctrl

    def test_rule_staged_select_returns_true(self):
        """A rule staged as 'select' overrides everything and returns True."""
        ctrl = self._ctrl_with_data()
        ctrl.staged_changes = {"E711": "select"}
        self.assertTrue(ctrl.get_effective_rule_state("E711", "E"))

    def test_rule_staged_ignore_returns_false(self):
        """A rule staged as 'ignore' overrides everything and returns False."""
        ctrl = self._ctrl_with_data()
        ctrl.staged_changes = {"E711": "ignore"}
        self.assertFalse(ctrl.get_effective_rule_state("E711", "E"))

    def test_category_staged_select_returns_true(self):
        """When only the category prefix is staged as 'select', the rule is True."""
        ctrl = self._ctrl_with_data()
        ctrl.staged_changes = {"E": "select"}
        self.assertTrue(ctrl.get_effective_rule_state("E711", "E"))

    def test_category_staged_ignore_returns_false(self):
        """When only the category prefix is staged as 'ignore', the rule is False."""
        ctrl = self._ctrl_with_data()
        ctrl.staged_changes = {"E": "ignore"}
        self.assertFalse(ctrl.get_effective_rule_state("E711", "E"))

    def test_rule_staged_takes_priority_over_category(self):
        """Per-rule staged state overrides the category-level staged state."""
        ctrl = self._ctrl_with_data()
        ctrl.staged_changes = {"E": "ignore", "E711": "select"}
        self.assertTrue(ctrl.get_effective_rule_state("E711", "E"))

    def test_pylint_rule_not_disabled_returns_true(self):
        """A pylint rule absent from the disable list is considered enabled."""
        ctrl = self._ctrl_with_data("[tool.pylint]\ndisable = []\n")
        self.assertTrue(ctrl.get_effective_rule_state("C0115", "C"))

    def test_pylint_rule_disabled_returns_false(self):
        """A pylint rule present in the disable list is considered disabled."""
        ctrl = self._ctrl_with_data("[tool.pylint]\ndisable = [\"C0115\"]\n")
        self.assertFalse(ctrl.get_effective_rule_state("C0115", "C"))

    def test_ruff_rule_not_in_select_returns_false(self):
        """A ruff rule not matching any select prefix is disabled."""
        ctrl = self._ctrl_with_data(
            "[tool.ruff.lint]\nselect = [\"F\"]\nignore = []\n"
        )
        # E711 does not start with "F", so it should not be in the enabled set
        # (all_rules is empty, so _get_ruff_rules_from_config returns an empty set)
        self.assertFalse(ctrl.get_effective_rule_state("E711", "E"))


# ---------------------------------------------------------------------------
# _get_ruff_rules_from_config
# ---------------------------------------------------------------------------


class TestGetRuffRulesFromConfig(unittest.TestCase):
    def _ctrl_with_rules(self, all_rules):
        ctrl = _make_controller()
        ctrl.all_rules = all_rules
        return ctrl

    def test_returns_empty_set_when_all_rules_empty(self):
        """With no known rules, nothing can be enabled."""
        ctrl = self._ctrl_with_rules({})
        result = ctrl._get_ruff_rules_from_config({"select": ["E"], "ignore": []})
        self.assertEqual(result, set())

    def test_rule_matching_select_prefix_is_enabled(self):
        """Rules whose code starts with a selected prefix are included."""
        all_rules = {
            "Pycodestyle": {
                "is_pylint": False,
                "rules": [{"code": "E501"}, {"code": "E711"}],
            }
        }
        ctrl = self._ctrl_with_rules(all_rules)
        result = ctrl._get_ruff_rules_from_config({"select": ["E"], "ignore": []})
        self.assertIn("E501", result)
        self.assertIn("E711", result)

    def test_ignored_rule_excluded_even_if_selected(self):
        """A rule matching an ignore prefix is excluded even if also selected."""
        all_rules = {
            "Pycodestyle": {
                "is_pylint": False,
                "rules": [{"code": "E501"}, {"code": "E711"}],
            }
        }
        ctrl = self._ctrl_with_rules(all_rules)
        result = ctrl._get_ruff_rules_from_config(
            {"select": ["E"], "ignore": ["E501"]}
        )
        self.assertNotIn("E501", result)
        self.assertIn("E711", result)

    def test_pylint_category_is_skipped(self):
        """Categories flagged is_pylint=True are not included in ruff results."""
        all_rules = {
            "Pylint: Convention": {
                "is_pylint": True,
                "rules": [{"code": "C0114"}],
            },
            "Pyflakes": {
                "is_pylint": False,
                "rules": [{"code": "F401"}],
            },
        }
        ctrl = self._ctrl_with_rules(all_rules)
        result = ctrl._get_ruff_rules_from_config(
            {"select": ["C", "F"], "ignore": []}
        )
        self.assertNotIn("C0114", result)
        self.assertIn("F401", result)

    def test_rule_not_matching_any_select_prefix_is_excluded(self):
        """Rules whose code does not start with any selected prefix are excluded."""
        all_rules = {
            "Bugbear": {
                "is_pylint": False,
                "rules": [{"code": "B006"}, {"code": "B007"}],
            }
        }
        ctrl = self._ctrl_with_rules(all_rules)
        result = ctrl._get_ruff_rules_from_config({"select": ["E"], "ignore": []})
        self.assertEqual(result, set())

    def test_multiple_select_prefixes(self):
        """Rules matching any of multiple select prefixes are all included."""
        all_rules = {
            "Mixed": {
                "is_pylint": False,
                "rules": [{"code": "E501"}, {"code": "F401"}, {"code": "B006"}],
            }
        }
        ctrl = self._ctrl_with_rules(all_rules)
        result = ctrl._get_ruff_rules_from_config(
            {"select": ["E", "F"], "ignore": []}
        )
        self.assertIn("E501", result)
        self.assertIn("F401", result)
        self.assertNotIn("B006", result)


if __name__ == "__main__":
    unittest.main()
