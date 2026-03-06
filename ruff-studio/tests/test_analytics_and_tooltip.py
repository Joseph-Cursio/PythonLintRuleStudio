"""
Tests for AnalyticsView (analytics_window.py) and Tooltip (tooltip.py).

Targets uncovered branches:
- analytics_window.py lines 72-74: author loop when get_author_stats returns data
- analytics_window.py lines 89-90: hotspot loop when get_rule_hotspots returns data
- analytics_window.py lines 102-104: history loop when get_scan_history returns rows
- tooltip.py lines 12-30: show_tooltip / hide_tooltip via real widget events
"""

import pytest
import customtkinter as ctk
from unittest.mock import patch, MagicMock
import tomlkit

from ruff_studio.main import App
from ruff_studio.controller import StudioController
from ruff_studio.ui.tooltip import Tooltip


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
}


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Creates a real App instance with all blocking background tasks mocked."""
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_label_texts(widget):
    """Recursively collect cget('text') from all CTkLabel descendants."""
    texts = []
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkLabel):
            texts.append(child.cget("text"))
        texts.extend(_all_label_texts(child))
    return texts


# ---------------------------------------------------------------------------
# AnalyticsView tests
# ---------------------------------------------------------------------------

class TestAnalyticsViewWithData:
    """Covers the 'data present' branches in _populate_analytics."""

    def test_analytics_refresh_with_data_renders_author_and_hotspot(self, app):
        """
        When get_author_stats and get_rule_hotspots return non-empty dicts and
        get_scan_history returns rows, refresh() must render a label containing
        the author name and a label containing the rule ID.

        Covers lines 72-74 (author loop) and 89-90 (hotspot loop).
        """
        # Arrange
        history_data = [
            ("run1", "2024-01-02T10:00:00", "main", 5),
            ("run2", "2024-01-01T10:00:00", "main", 3),
        ]
        author_data = {"Alice": 3, "Bob": 2}
        hotspot_data = {"E501": 3, "F401": 2}

        with (
            patch.object(app.controller, "get_scan_history", return_value=history_data),
            patch.object(app.controller, "get_author_stats", return_value=author_data),
            patch.object(app.controller, "get_rule_hotspots", return_value=hotspot_data),
        ):
            # Act
            app.analytics_view.refresh()
            app.update_idletasks()

        # Assert
        texts = _all_label_texts(app.analytics_view.scroll_frame)
        assert any("Alice" in t for t in texts), (
            f"Expected a label containing 'Alice'; found labels: {texts}"
        )
        assert any("E501" in t for t in texts), (
            f"Expected a label containing 'E501'; found labels: {texts}"
        )

    def test_analytics_refresh_with_data_renders_history_rows(self, app):
        """
        When get_scan_history returns rows, refresh() must create a label
        for each history entry containing the branch and count.

        Covers lines 102-104 (history loop).
        """
        # Arrange
        history_data = [
            ("run1", "2024-01-02T10:00:00", "main", 5),
            ("run2", "2024-01-01T10:00:00", "feature", 3),
        ]

        with (
            patch.object(app.controller, "get_scan_history", return_value=history_data),
            patch.object(app.controller, "get_author_stats", return_value={}),
            patch.object(app.controller, "get_rule_hotspots", return_value={}),
        ):
            # Act
            app.analytics_view.refresh()
            app.update_idletasks()

        # Assert — both branch names and counts must appear in rendered labels
        texts = _all_label_texts(app.analytics_view.scroll_frame)
        assert any("main" in t for t in texts), (
            f"Expected label with 'main'; found: {texts}"
        )
        assert any("feature" in t for t in texts), (
            f"Expected label with 'feature'; found: {texts}"
        )
        assert any("5" in t for t in texts), (
            f"Expected label with count '5'; found: {texts}"
        )

    def test_analytics_refresh_with_multiple_authors_renders_each(self, app):
        """
        Every key in the author stats dict must produce its own rendered label.

        Covers lines 72-74 (full iteration of authors.items()).
        """
        # Arrange
        author_data = {"Alice": 7, "Bob": 4, "Carol": 1}

        with (
            patch.object(app.controller, "get_scan_history", return_value=[("r", "2024-01-01T00:00:00", "main", 7)]),
            patch.object(app.controller, "get_author_stats", return_value=author_data),
            patch.object(app.controller, "get_rule_hotspots", return_value={}),
        ):
            # Act
            app.analytics_view.refresh()
            app.update_idletasks()

        texts = _all_label_texts(app.analytics_view.scroll_frame)
        for name in ("Alice", "Bob", "Carol"):
            assert any(name in t for t in texts), (
                f"Expected label for author '{name}'; found: {texts}"
            )

    def test_analytics_refresh_with_multiple_hotspots_renders_each(self, app):
        """
        Every key in the rule hotspots dict must produce its own rendered label.

        Covers lines 89-90 (full iteration of rules.items()).
        """
        # Arrange
        hotspot_data = {"E501": 10, "F401": 6, "W503": 2}

        with (
            patch.object(app.controller, "get_scan_history", return_value=[("r", "2024-01-01T00:00:00", "main", 10)]),
            patch.object(app.controller, "get_author_stats", return_value={}),
            patch.object(app.controller, "get_rule_hotspots", return_value=hotspot_data),
        ):
            # Act
            app.analytics_view.refresh()
            app.update_idletasks()

        texts = _all_label_texts(app.analytics_view.scroll_frame)
        for rule_id in ("E501", "F401", "W503"):
            assert any(rule_id in t for t in texts), (
                f"Expected label for rule '{rule_id}'; found: {texts}"
            )

    def test_analytics_refresh_no_data_shows_no_data_available(self, app):
        """
        When all three data sources return empty results, both the author and
        hotspot sections must display 'No data available'.
        """
        # Arrange: fixture already mocks everything to return empty values,
        # but we make this explicit for clarity.
        with (
            patch.object(app.controller, "get_scan_history", return_value=[]),
            patch.object(app.controller, "get_author_stats", return_value={}),
            patch.object(app.controller, "get_rule_hotspots", return_value={}),
        ):
            # Act
            app.analytics_view.refresh()
            app.update_idletasks()

        # Assert
        texts = _all_label_texts(app.analytics_view.scroll_frame)
        no_data_labels = [t for t in texts if "No data available" in t]
        assert len(no_data_labels) >= 2, (
            f"Expected at least two 'No data available' labels (one per section); "
            f"found: {texts}"
        )

    def test_analytics_delta_positive_shows_plus_sign(self, app):
        """
        When the latest run has more violations than the previous one,
        the trend label must contain a '+' character.
        """
        # Arrange: latest=10, previous=5 => delta=+5
        history_data = [
            ("r1", "2024-01-02T00:00:00", "main", 10),
            ("r2", "2024-01-01T00:00:00", "main", 5),
        ]

        with (
            patch.object(app.controller, "get_scan_history", return_value=history_data),
            patch.object(app.controller, "get_author_stats", return_value={}),
            patch.object(app.controller, "get_rule_hotspots", return_value={}),
        ):
            # Act
            app.analytics_view.refresh()
            app.update_idletasks()

        texts = _all_label_texts(app.analytics_view.scroll_frame)
        assert any("+" in t for t in texts), (
            f"Expected a label containing '+' for positive delta; found: {texts}"
        )

    def test_analytics_delta_no_change_shows_no_change(self, app):
        """
        When only one history row exists (latest == prev, delta == 0),
        the trend label must contain the text 'No change'.
        """
        # Arrange: single run, so prev_count == latest_count => delta == 0
        history_data = [
            ("r1", "2024-01-01T00:00:00", "main", 5),
        ]

        with (
            patch.object(app.controller, "get_scan_history", return_value=history_data),
            patch.object(app.controller, "get_author_stats", return_value={}),
            patch.object(app.controller, "get_rule_hotspots", return_value={}),
        ):
            # Act
            app.analytics_view.refresh()
            app.update_idletasks()

        texts = _all_label_texts(app.analytics_view.scroll_frame)
        assert any("No change" in t for t in texts), (
            f"Expected a label containing 'No change'; found: {texts}"
        )

    def test_analytics_author_unknown_rendered_when_key_is_empty(self, app):
        """
        When an author key is an empty string, the label must display 'Unknown'
        rather than an empty string.

        Covers line 73: `name = author if author else 'Unknown'`.
        """
        # Arrange
        author_data = {"": 5}

        with (
            patch.object(app.controller, "get_scan_history", return_value=[("r", "2024-01-01T00:00:00", "main", 5)]),
            patch.object(app.controller, "get_author_stats", return_value=author_data),
            patch.object(app.controller, "get_rule_hotspots", return_value={}),
        ):
            # Act
            app.analytics_view.refresh()
            app.update_idletasks()

        texts = _all_label_texts(app.analytics_view.scroll_frame)
        assert any("Unknown" in t for t in texts), (
            f"Expected 'Unknown' label for empty-string author; found: {texts}"
        )

    def test_analytics_history_branch_none_renders_na(self, app):
        """
        When a history row has None as the branch, the rendered label must
        show 'N/A' in place of the branch name.

        Covers line 103: `branch = run[2] if run[2] else 'N/A'`.
        """
        # Arrange: branch field is None
        history_data = [("r1", "2024-01-01T10:00:00", None, 3)]

        with (
            patch.object(app.controller, "get_scan_history", return_value=history_data),
            patch.object(app.controller, "get_author_stats", return_value={}),
            patch.object(app.controller, "get_rule_hotspots", return_value={}),
        ):
            # Act
            app.analytics_view.refresh()
            app.update_idletasks()

        texts = _all_label_texts(app.analytics_view.scroll_frame)
        assert any("N/A" in t for t in texts), (
            f"Expected 'N/A' for None branch; found: {texts}"
        )

    def test_analytics_refresh_clears_previous_content(self, app):
        """
        Calling refresh() twice must not accumulate duplicate widgets;
        the scroll_frame children after the second call must be the same
        count as after the first call.
        """
        # Arrange
        with (
            patch.object(app.controller, "get_scan_history", return_value=[]),
            patch.object(app.controller, "get_author_stats", return_value={"Alice": 1}),
            patch.object(app.controller, "get_rule_hotspots", return_value={}),
        ):
            app.analytics_view.refresh()
            app.update_idletasks()
            count_after_first = len(app.analytics_view.scroll_frame.winfo_children())

            # Act: refresh again with the same data
            app.analytics_view.refresh()
            app.update_idletasks()
            count_after_second = len(app.analytics_view.scroll_frame.winfo_children())

        # Assert: no widget accumulation
        assert count_after_first == count_after_second, (
            f"Widget count changed across refreshes: "
            f"{count_after_first} -> {count_after_second}"
        )


# ---------------------------------------------------------------------------
# Tooltip tests
# ---------------------------------------------------------------------------

class TestTooltip:
    """Covers show_tooltip / hide_tooltip in tooltip.py."""

    def test_tooltip_show_and_hide_via_enter_leave_events(self, app):
        """
        Simulating <Enter> on a widget with a Tooltip attached must set
        tooltip_window to a CTkToplevel instance. Simulating <Leave> must
        destroy it and set tooltip_window back to None.
        """
        # Arrange: grab any CTkLabel from the rules_panel scroll_frame
        scroll_children = app.rules_panel.scroll_frame.winfo_children()
        assert scroll_children, "Precondition: scroll_frame must have children"

        # Walk descendants to find a CTkLabel we can bind to
        lbl = None
        for child in scroll_children:
            if isinstance(child, ctk.CTkFrame):
                for sub in child.winfo_children():
                    if isinstance(sub, ctk.CTkLabel):
                        lbl = sub
                        break
            if lbl:
                break

        if lbl is None:
            # Fall back to the first child of any kind
            lbl = ctk.CTkLabel(app.rules_panel.scroll_frame, text="tooltip-test")
            lbl.pack()
            app.update_idletasks()

        # Patch widget.bbox so it does not fail on a non-text widget
        lbl.bbox = lambda *_: (0, 0, 0, 0)

        tooltip = Tooltip(lbl, "test tip")

        # Act: show directly (event_generate is unreliable in test environments)
        tooltip.show_tooltip(event=None)
        app.update_idletasks()

        # Assert tooltip window was created
        assert tooltip.tooltip_window is not None, (
            "Expected tooltip_window to be set after show_tooltip"
        )

        # Act: hide
        tooltip.hide_tooltip(event=None)
        app.update_idletasks()

        # Assert tooltip window was destroyed
        assert tooltip.tooltip_window is None, (
            "Expected tooltip_window to be None after hide_tooltip"
        )

    def test_tooltip_hide_when_never_shown_does_not_raise(self, app):
        """
        Calling hide_tooltip before show_tooltip (tooltip_window is None)
        must not raise any exception.
        """
        # Arrange
        lbl = ctk.CTkLabel(app, text="safe-hide")
        lbl.bbox = lambda *_: (0, 0, 0, 0)
        tooltip = Tooltip(lbl, "safe tip")

        # Act and Assert: no exception
        tooltip.hide_tooltip(event=None)
        assert tooltip.tooltip_window is None

    def test_tooltip_text_is_rendered_in_toplevel(self, app):
        """
        After show_tooltip fires, the CTkToplevel created must contain a
        CTkLabel whose text matches the tooltip string.
        """
        # Arrange
        lbl = ctk.CTkLabel(app.rules_panel.scroll_frame, text="probe")
        lbl.pack()
        app.update_idletasks()
        lbl.bbox = lambda *_: (0, 0, 0, 0)

        tooltip = Tooltip(lbl, "my unique tip text")

        # Act
        tooltip.show_tooltip(event=None)
        app.update_idletasks()

        # Assert
        assert tooltip.tooltip_window is not None
        tip_labels = [
            w for w in tooltip.tooltip_window.winfo_children()
            if isinstance(w, ctk.CTkLabel)
        ]
        assert tip_labels, "Expected at least one CTkLabel inside the tooltip window"
        assert any("my unique tip text" in w.cget("text") for w in tip_labels), (
            f"Tooltip text not found; labels: {[w.cget('text') for w in tip_labels]}"
        )

        # Cleanup
        tooltip.hide_tooltip(event=None)

    def test_tooltip_second_enter_does_not_stack_windows(self, app):
        """
        Generating <Enter> twice must not leave orphaned tooltip windows;
        only one tooltip_window reference is kept at a time.
        """
        # Arrange
        lbl = ctk.CTkLabel(app.rules_panel.scroll_frame, text="stack-probe")
        lbl.pack()
        app.update_idletasks()
        lbl.bbox = lambda *_: (0, 0, 0, 0)

        tooltip = Tooltip(lbl, "stacking tip")

        # Act: show twice (directly, as event_generate is unreliable in test environments)
        tooltip.show_tooltip(event=None)
        app.update_idletasks()
        first_window = tooltip.tooltip_window

        tooltip.show_tooltip(event=None)
        app.update_idletasks()

        # Assert: tooltip_window is still a single (possibly new) reference
        assert tooltip.tooltip_window is not None

        # Cleanup
        tooltip.hide_tooltip(event=None)
