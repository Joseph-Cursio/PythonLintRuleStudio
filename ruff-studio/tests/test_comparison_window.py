"""
Tests for ProfileComparisonWindow (comparison_window.py).

Covers the do_comparison branches:
  - Same profile selected → shows warning message
  - Different profiles → all diff branches (select_only_in_1/2, ignore_only_in_1/2,
    common_select, common_ignore)
  - Empty diff dict → no lines appended beyond the headers
"""

import pytest
import customtkinter as ctk
import tomlkit
from unittest.mock import patch, MagicMock

from ruff_studio.main import App
from ruff_studio.controller import StudioController
from ruff_studio.ui.comparison_window import ProfileComparisonWindow


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    with (
        patch.object(StudioController, "run_in_thread", return_value=None),
        patch.object(StudioController, "get_scan_history", return_value=[]),
        patch.object(StudioController, "get_author_stats", return_value={}),
        patch.object(StudioController, "get_rule_hotspots", return_value={}),
        patch("ruff_studio.proposal_manager.get_proposals", return_value=[]),
        patch("ruff_studio.main.messagebox"),
        patch("ruff_studio.main.filedialog"),
        patch("ruff_studio.ui.proposal_window.messagebox"),
        patch("ruff_studio.ui.dashboard_window.messagebox"),
    ):
        app_instance = App(headless=False)
        app_instance.update_idletasks()
        yield app_instance
        app_instance.destroy()


@pytest.fixture
def win(app):
    """Open a ProfileComparisonWindow and close it after the test."""
    w = None
    with patch("ruff_studio.ui.comparison_window.profile_manager.get_built_in_profiles",
               return_value=["standard", "strict"]):
        w = ProfileComparisonWindow(app)
        app.update_idletasks()
    yield w
    try:
        w.destroy()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestProfileComparisonWindowInit:

    def test_window_has_compare_button(self, win):
        assert hasattr(win, "compare_button")

    def test_window_has_results_textbox(self, win):
        assert hasattr(win, "results_textbox")

    def test_initial_text_is_placeholder(self, win):
        text = win.results_textbox.get("1.0", "end").strip()
        assert "Select two profiles" in text


# ---------------------------------------------------------------------------
# do_comparison — same profile guard
# ---------------------------------------------------------------------------

class TestDoComparisonSameProfile:

    def test_same_profile_shows_warning_text(self, win):
        """When both dropdowns show the same profile, a warning is written."""
        win.profile1_var.set("standard")
        win.profile2_var.set("standard")

        win.do_comparison()

        text = win.results_textbox.get("1.0", "end")
        assert "two different profiles" in text

    def test_empty_profile_shows_warning_text(self, win):
        """When a profile var is empty, the same guard triggers."""
        win.profile1_var.set("")
        win.profile2_var.set("strict")

        win.do_comparison()

        text = win.results_textbox.get("1.0", "end")
        assert "two different profiles" in text


# ---------------------------------------------------------------------------
# do_comparison — all diff branches
# ---------------------------------------------------------------------------

FULL_DIFF = {
    "select_only_in_1": ["E501", "W503"],
    "select_only_in_2": ["F401"],
    "ignore_only_in_1": ["D100"],
    "ignore_only_in_2": ["N801", "S101"],
    "common_select": ["E", "F"],
    "common_ignore": ["W"],
}

EMPTY_DIFF = {
    "select_only_in_1": [],
    "select_only_in_2": [],
    "ignore_only_in_1": [],
    "ignore_only_in_2": [],
    "common_select": [],
    "common_ignore": [],
}


class TestDoComparisonDiff:

    def _run(self, win, app, diff):
        win.profile1_var.set("standard")
        win.profile2_var.set("strict")
        with patch("ruff_studio.ui.comparison_window.profile_manager.compare_profiles",
                   return_value=diff):
            win.do_comparison()
        app.update_idletasks()
        return win.results_textbox.get("1.0", "end")

    def test_select_only_in_1_appears_in_report(self, win, app):
        text = self._run(win, app, FULL_DIFF)
        assert "E501" in text

    def test_select_only_in_2_appears_in_report(self, win, app):
        text = self._run(win, app, FULL_DIFF)
        assert "F401" in text

    def test_ignore_only_in_1_appears_in_report(self, win, app):
        text = self._run(win, app, FULL_DIFF)
        assert "D100" in text

    def test_ignore_only_in_2_appears_in_report(self, win, app):
        text = self._run(win, app, FULL_DIFF)
        assert "N801" in text

    def test_common_select_appears_in_report(self, win, app):
        text = self._run(win, app, FULL_DIFF)
        assert "Commonly Selected" in text

    def test_common_ignore_appears_in_report(self, win, app):
        text = self._run(win, app, FULL_DIFF)
        assert "Commonly Ignored" in text

    def test_report_contains_profile_names(self, win, app):
        text = self._run(win, app, FULL_DIFF)
        assert "standard" in text
        assert "strict" in text

    def test_empty_diff_shows_only_headers(self, win, app):
        """When diffs are all empty, individual rule lines are absent."""
        text = self._run(win, app, EMPTY_DIFF)
        # Headers present, but no rule codes.
        assert "RULES SELECTED" in text
        assert "E501" not in text
