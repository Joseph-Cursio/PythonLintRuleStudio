"""
Tests for UI panel modules: ResultsPanel, InfoPanel, and ProfileComparisonWindow.

These tests use a real App instance with mocked background tasks and dialogs,
following the same fixture pattern established in test_main_ui.py.
"""

import pytest
import customtkinter as ctk
from unittest.mock import patch, MagicMock
import tomlkit

from ruff_studio.main import App
from ruff_studio.controller import StudioController
from ruff_studio.workspace_analyzer import UnifiedViolationModel
from ruff_studio.ui.comparison_window import ProfileComparisonWindow


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

MOCK_RULES = {
    "Error": {
        "prefix": "E",
        "rules": [
            {
                "code": "E501",
                "name": "LineTooLong",
                "summary": "S",
                "status": "stable",
            },
        ],
    },
    "Pyflakes": {
        "prefix": "F",
        "rules": [
            {
                "code": "F401",
                "name": "UnusedImport",
                "summary": "An imported module is not used.",
                "fix": True,
                "status": "stable",
            },
        ],
    },
    "Pylint: Convention": {
        "prefix": "C",
        "is_pylint": True,
        "rules": [
            {
                "code": "C0103",
                "name": "invalid-name",
                "summary": "Invalid name for variable.",
                "fix": False,
                "status": "stable",
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Creates a real App instance with all blocking background tasks mocked."""
    with (
        patch.object(App, "run_in_thread", return_value=None),
        patch.object(StudioController, "run_in_thread", return_value=None),
        patch.object(StudioController, "get_scan_history", return_value=[]),
        patch.object(StudioController, "get_author_stats", return_value={}),
        patch.object(StudioController, "get_rule_hotspots", return_value={}),
        patch("ruff_studio.proposal_manager.get_proposals", return_value=[]),
        patch("ruff_studio.main.messagebox"),
        patch("ruff_studio.main.filedialog"),
        patch("ruff_studio.ui.proposal_window.messagebox"),
        patch("ruff_studio.ui.dashboard_window.messagebox"),
        patch("tkinter.messagebox.showinfo"),
        patch("tkinter.messagebox.showerror"),
        patch("tkinter.messagebox.showwarning"),
        patch("tkinter.messagebox.askyesno", return_value=True),
        patch("tkinter.filedialog.askdirectory", return_value="/fake/dir"),
        patch("tkinter.filedialog.asksaveasfilename", return_value="/fake/file"),
    ):
        app_instance = App(headless=False)
        app_instance.controller.all_rules = MOCK_RULES
        app_instance.controller.current_directory = "/fake/dir"
        app_instance.controller.pyproject_path = "/fake/dir/pyproject.toml"
        app_instance.controller.pyproject_data = tomlkit.parse("dummy = true")
        app_instance.controller.analyzer.conn = MagicMock()
        app_instance.populate_rules_initial()
        app_instance.update_idletasks()
        yield app_instance
        app_instance.destroy()


def _get_label_texts(widget):
    """Return a list of text strings from all CTkLabel children of widget."""
    return [
        w.cget("text")
        for w in widget.winfo_children()
        if isinstance(w, ctk.CTkLabel)
    ]


# ---------------------------------------------------------------------------
# ResultsPanel tests
# ---------------------------------------------------------------------------

class TestResultsPanel:

    def test_set_results_empty_shows_zero_in_label(self, app):
        """set_results([]) updates the results_label to reflect a count of 0."""
        # Arrange
        panel = app.results_panel

        # Act
        panel.set_results([])
        app.update_idletasks()

        # Assert
        label_text = panel.results_label.cget("text")
        assert "0" in label_text

    def test_set_results_with_single_violation_shows_count_of_one(self, app):
        """set_results with one violation updates the results_label to reflect a count of 1."""
        # Arrange
        panel = app.results_panel
        violations = [UnifiedViolationModel("E501", "f.py", 1, 1, "line too long")]

        # Act
        panel.set_results(violations)
        app.update_idletasks()

        # Assert
        label_text = panel.results_label.cget("text")
        assert "1" in label_text

    def test_set_results_with_author_renders_author_name(self, app):
        """set_results with an authored violation renders the author name in a child label."""
        # Arrange
        panel = app.results_panel
        violation = UnifiedViolationModel("E501", "f.py", 1, 1, "line too long")
        violation.author = "Alice"

        # Act
        panel.set_results([violation])
        app.update_idletasks()

        # Assert — the author name must appear somewhere in the child labels
        child_texts = _get_label_texts(panel)
        assert any("Alice" in t for t in child_texts), (
            f"Expected 'Alice' in a child label, found: {child_texts}"
        )

    def test_set_scanning_updates_label_text(self, app):
        """set_scanning() sets the results_label text to 'Scanning...'."""
        # Arrange
        panel = app.results_panel

        # Act
        panel.set_scanning()
        app.update_idletasks()

        # Assert
        assert panel.results_label.cget("text") == "Scanning..."

    def test_simulation_with_added_violations_shows_positive_delta_and_new_header(self, app):
        """
        When base results are empty and the simulation introduces violations,
        the delta label must show (+N) and a 'NEW VIOLATIONS' header must appear.
        """
        # Arrange
        panel = app.results_panel
        app.controller.base_scan_results = []
        sim_results = [
            {
                "code": "E501",
                "filename": "f.py",
                "location": {"row": 1, "column": 1},
                "message": "m",
            }
        ]

        # Act
        panel.set_simulation_results(sim_results)
        app.update_idletasks()

        # Assert delta in header label
        label_text = panel.results_label.cget("text")
        assert "(+1)" in label_text, f"Expected '(+1)' in label text, got: {label_text!r}"

        # Assert NEW VIOLATIONS section header exists as a child label
        child_texts = _get_label_texts(panel)
        assert any("NEW VIOLATIONS" in t for t in child_texts), (
            f"Expected 'NEW VIOLATIONS' header in child labels, found: {child_texts}"
        )

    def test_simulation_no_change_shows_no_change_label(self, app):
        """
        When both base and simulation results are empty, a 'No change' label
        must be rendered in the panel.
        """
        # Arrange
        panel = app.results_panel
        app.controller.base_scan_results = []

        # Act
        panel.set_simulation_results([])
        app.update_idletasks()

        # Assert
        child_texts = _get_label_texts(panel)
        assert any("No change" in t for t in child_texts), (
            f"Expected a 'No change' label, found: {child_texts}"
        )


# ---------------------------------------------------------------------------
# InfoPanel tests
# ---------------------------------------------------------------------------

class TestInfoPanel:

    def test_set_rule_ruff_updates_header_and_name_label(self, app):
        """
        set_rule() with a Ruff rule updates the info_label to include the
        rule code and renders a child label containing the rule name.
        """
        # Arrange
        panel = app.info_panel
        rule = {
            "code": "E501",
            "name": "LineTooLong",
            "summary": "Line is too long",
            "documentation": None,
        }

        # Act
        panel.set_rule(rule)
        app.update_idletasks()

        # Assert header label
        assert "E501" in panel.info_label.cget("text"), (
            f"Expected 'E501' in info_label, got: {panel.info_label.cget('text')!r}"
        )

        # Assert a child label with the rule name
        child_texts = _get_label_texts(panel)
        assert any("LineTooLong" in t for t in child_texts), (
            f"Expected 'LineTooLong' in a child label, found: {child_texts}"
        )

    def test_set_rule_with_documentation_renders_textbox(self, app):
        """
        set_rule() for a rule that has documentation content must render a
        CTkTextbox widget containing that documentation.
        """
        # Arrange
        panel = app.info_panel
        rule = {
            "code": "C0103",
            "name": "invalid-name",
            "summary": "Bad name",
            "documentation": "some docs about naming conventions",
        }

        # Act
        panel.set_rule(rule)
        app.update_idletasks()

        # Assert at least one CTkTextbox child exists
        textboxes = [
            w for w in panel.winfo_children() if isinstance(w, ctk.CTkTextbox)
        ]
        assert len(textboxes) >= 1, (
            "Expected at least one CTkTextbox child after set_rule with documentation"
        )

    def test_clear_removes_dynamic_children_leaving_only_info_label(self, app):
        """
        After set_rule() populates dynamic children, clear() must remove them
        all so that only the permanent info_label remains.
        """
        # Arrange
        panel = app.info_panel
        rule = {
            "code": "E501",
            "name": "LineTooLong",
            "summary": "Line is too long",
            "documentation": None,
        }
        panel.set_rule(rule)
        app.update_idletasks()

        # Precondition: there should be more children than just the info_label
        children_before = panel.winfo_children()
        assert len(children_before) > 1, (
            "Precondition failed: set_rule should have added children"
        )

        # Act
        panel.clear()
        app.update_idletasks()

        # Assert only the info_label remains
        children_after = panel.winfo_children()
        label_texts_after = [
            w.cget("text") for w in children_after if isinstance(w, ctk.CTkLabel)
        ]
        # All remaining labels must be the permanent info_label (text "Rule Info" or
        # the code from a previous set_rule — it does NOT get reset by clear())
        non_info_label_children = [w for w in children_after if w is not panel.info_label]
        assert len(non_info_label_children) == 0, (
            f"Expected no children besides info_label after clear(), "
            f"found: {[type(w).__name__ for w in non_info_label_children]}"
        )


# ---------------------------------------------------------------------------
# ProfileComparisonWindow tests
# ---------------------------------------------------------------------------

class TestProfileComparisonWindow:

    def test_comparison_window_opens_as_toplevel_child(self, app):
        """
        open_comparison_window() must create a ProfileComparisonWindow
        that is accessible as a child toplevel of the app.
        """
        win = None
        try:
            with patch(
                "ruff_studio.profile_manager.get_built_in_profiles",
                return_value=["standard", "strict"],
            ):
                app.open_comparison_window()
                app.update_idletasks()

            # ProfileComparisonWindow is a CTkToplevel; find it among children
            toplevels = [
                w for w in app.winfo_children()
                if isinstance(w, ProfileComparisonWindow)
            ]
            assert len(toplevels) >= 1, (
                "Expected at least one ProfileComparisonWindow child toplevel"
            )
            win = toplevels[0]
        finally:
            if win is not None:
                win.destroy()

    def test_comparison_same_profile_shows_warning_in_textbox(self, app):
        """
        When both profile dropdowns are set to the same value and
        do_comparison() is called, the textbox must contain a 'Please select
        two different' message.
        """
        win = None
        try:
            with patch(
                "ruff_studio.profile_manager.get_built_in_profiles",
                return_value=["standard", "strict"],
            ):
                win = ProfileComparisonWindow(app)
                app.update_idletasks()

            # Set both profile vars to the same value
            win.profile1_var.set("standard")
            win.profile2_var.set("standard")

            win.do_comparison()
            app.update_idletasks()

            textbox_content = win.results_textbox.get("1.0", "end")
            assert "Please select two different" in textbox_content, (
                f"Expected warning text in textbox, got: {textbox_content!r}"
            )
        finally:
            if win is not None:
                win.destroy()

    def test_comparison_different_profiles_shows_rule_codes(self, app):
        """
        When two different profiles are compared and the mock diff contains
        'E501' in select_only_in_1, the textbox must render 'E501'.
        """
        win = None
        mock_diff = {
            "select_only_in_1": ["E501"],
            "select_only_in_2": [],
            "ignore_only_in_1": [],
            "ignore_only_in_2": [],
            "common_select": [],
            "common_ignore": [],
        }
        try:
            with patch(
                "ruff_studio.profile_manager.get_built_in_profiles",
                return_value=["standard", "strict"],
            ):
                win = ProfileComparisonWindow(app)
                app.update_idletasks()

            win.profile1_var.set("standard")
            win.profile2_var.set("strict")

            with patch(
                "ruff_studio.profile_manager.compare_profiles",
                return_value=mock_diff,
            ):
                win.do_comparison()
                app.update_idletasks()

            textbox_content = win.results_textbox.get("1.0", "end")
            assert "E501" in textbox_content, (
                f"Expected 'E501' in textbox content, got: {textbox_content!r}"
            )
        finally:
            if win is not None:
                win.destroy()
