import pytest
import os
import customtkinter as ctk
from ruff_studio.main import App
from ruff_studio.controller import StudioController
from unittest.mock import patch, MagicMock, ANY
import tomlkit

# MOCK_RULES for testing
MOCK_RULES = {
    "Error": {
        "prefix": "E",
        "rules": [
            {"code": "E501", "name": "LineTooLong", "summary": "S", "status": "stable"},
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

@pytest.fixture
def app():
    """
    Creates a real App instance but mocks blocking background tasks and dialogs.
    """
    # 1. Mock background threads and blocking dialogs
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
        # Use a real App but with headless=False (assuming local display is available)
        # If it still hangs, we can switch back to headless and mock specific components.
        app_instance = App(headless=False)
        
        # Setup mock data
        app_instance.controller.all_rules = MOCK_RULES
        app_instance.controller.current_directory = "/fake/dir"
        app_instance.controller.pyproject_path = "/fake/dir/pyproject.toml"
        app_instance.controller.pyproject_data = tomlkit.parse("dummy = true")
        app_instance.controller.analyzer.conn = MagicMock()

        # Initialize the rule list UI
        app_instance.populate_rules_initial()
        app_instance.update_idletasks()

        yield app_instance
        app_instance.destroy()

def test_ui_initialization(app):
    """Verify core components exist."""
    assert app.sidebar is not None
    assert app.rules_view is not None
    assert app.analytics_view is not None
    assert app.proposals_view is not None

def test_switch_view(app):
    """Test navigation rail switching."""
    app.switch_view("analytics")
    app.update_idletasks()
    # Check if analytics view is mapped
    assert app.analytics_view.winfo_ismapped()

def test_search_filtering(app):
    """Test the new search feature logic."""
    rp = app.rules_panel
    # Initial state: both visible
    assert "Error" in rp.rule_widgets
    
    # Filter for Pyflakes
    rp.filter_rules("Pyflakes")
    app.update_idletasks()
    
    # Category frames should have their visibility managed by pack/pack_forget
    # We can check the internal is_expanded or mapped status
    assert rp.rule_widgets["Pyflakes"]["category_frame"].winfo_ismapped()
    # Error should NOT be mapped (filtered out)
    assert not rp.rule_widgets["Error"]["category_frame"].winfo_ismapped()

def test_visual_hierarchy_colors(app):
    """Verify that rules get the correct colors based on prefix."""
    rp = app.rules_panel
    # E501 is an Error (reddish)
    e_color = app.controller.get_color_for_prefix("E")
    e501_label = None
    # Look for the label in the E501 widget
    for child in rp.rule_widgets["Error"]["rules"]["E501"]["frame"].winfo_children():
        if isinstance(child, ctk.CTkLabel) and "E501" in child.cget("text"):
            e501_label = child
            break
    
    assert e501_label is not None
    # CustomTkinter returns colors as a tuple or string, check if it matches our controller
    assert e501_label.cget("text_color") == e_color

def test_apply_profile_staging(app):
    """Verify that applying a profile stages changes correctly."""
    mock_profile = {
        "profile": {
            "rules": {
                "ruff": {"select": ["E"], "ignore": ["F"]}
            }
        }
    }
    with patch('ruff_studio.profile_manager.load_profile', return_value=mock_profile):
        app.apply_profile("test-profile")
    
    assert app.controller.staged_changes.get("E501") == "select"
    assert app.controller.staged_changes.get("F401") == "ignore"

def test_results_simulation_diff(app):
    """Verify simulation results show the delta."""
    results_panel = app.results_panel
    # Mock base results (1 violation)
    from ruff_studio.workspace_analyzer import UnifiedViolationModel
    app.controller.base_scan_results = [
        UnifiedViolationModel("E501", "f.py", 1, 1, "msg")
    ]
    
    # Simulate scan with NO results (delta -1)
    results_panel.set_simulation_results([])
    assert "(-1)" in results_panel.results_label.cget("text")
    
    # Check if 'FIXED/IGNORED' header appeared
    found_fixed = any("FIXED" in str(w.cget("text")) for w in results_panel.winfo_children() if isinstance(w, ctk.CTkLabel))
    assert found_fixed
