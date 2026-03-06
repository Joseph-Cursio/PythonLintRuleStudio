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
        # Enable test_mode so rebuild_navigable_items doesn't require winfo_ismapped
        app_instance.rules_panel.test_mode = True
        app_instance.rules_panel.rebuild_navigable_items()

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


# ---------------------------------------------------------------------------
# process_queue command handlers
# ---------------------------------------------------------------------------

def test_process_queue_discover_rules(app):
    """process_queue dispatches discover_rules: all_rules and rule_widgets are set."""
    # Wipe state set by the fixture so we can verify it is restored by process_queue.
    app.controller.all_rules = {}
    app.rules_panel.rule_widgets = {}

    app.controller.queue.put(("discover_rules", MOCK_RULES))
    app.process_queue()
    app.update_idletasks()

    assert app.controller.all_rules == MOCK_RULES
    assert len(app.rules_panel.rule_widgets) > 0


def test_process_queue_run_full_scan(app):
    """process_queue dispatches run_full_scan: base_scan_results is populated."""
    from ruff_studio.workspace_analyzer import UnifiedViolationModel

    violations = [
        UnifiedViolationModel("E501", "a.py", 10, 1, "line too long"),
        UnifiedViolationModel("F401", "b.py", 3, 1, "unused import"),
    ]
    app.controller.queue.put(("run_full_scan", violations))
    app.process_queue()
    app.update_idletasks()

    assert app.controller.base_scan_results == violations


def test_process_queue_run_simulation(app):
    """process_queue dispatches run_simulation: results_label mentions Simulation."""
    from ruff_studio.workspace_analyzer import UnifiedViolationModel

    # base_scan_results must be set for set_simulation_results to compute a delta.
    app.controller.base_scan_results = [
        UnifiedViolationModel("E501", "a.py", 1, 1, "msg")
    ]

    app.controller.queue.put(("run_simulation", []))
    app.process_queue()
    app.update_idletasks()

    assert "Simulation" in app.results_panel.results_label.cget("text")


def test_process_queue_error(app):
    """process_queue dispatches error: messagebox.showerror is called."""
    import ruff_studio.main as main_module

    app.controller.queue.put(("error", "something failed"))
    app.process_queue()
    app.update_idletasks()

    main_module.messagebox.showerror.assert_called()


def test_process_queue_fetch_docs(app):
    """process_queue dispatches fetch_docs: rule dict gets documentation set."""
    rule = {"code": "E501", "name": "LineTooLong", "summary": "S", "status": "stable", "documentation": None}

    app.controller.queue.put(("fetch_docs", (rule, "some docs")))
    app.process_queue()
    app.update_idletasks()

    assert rule["documentation"] == "some docs"


# ---------------------------------------------------------------------------
# App.run_in_thread (real implementation, bypassing the fixture patch)
# ---------------------------------------------------------------------------

def test_run_in_thread_disables_select_button_and_sets_status(app):
    """Calling the real App.run_in_thread disables the select button and sets status."""
    import ruff_studio.main as main_module
    from unittest.mock import patch as _patch

    # Ensure we start from a known normal state.
    app.toolbar.select_button.configure(state="normal")
    app.toolbar.set_status("")

    # Patch StudioController.run_in_thread to a no-op so no real thread is spawned.
    with _patch.object(app.controller.__class__, "run_in_thread", return_value=None):
        # Call the *real* App.run_in_thread directly (bypassing the fixture's patch).
        main_module.App.run_in_thread(app, MagicMock(), "test_cmd")

    app.update_idletasks()

    assert app.toolbar.select_button.cget("state") == "disabled"
    assert app.toolbar.status_label.cget("text") == "Running..."


# ---------------------------------------------------------------------------
# select_directory
# ---------------------------------------------------------------------------

def test_select_directory_sets_directory_label(app):
    """select_directory updates the toolbar directory label."""
    app.select_directory("/fake/dir")
    app.update_idletasks()

    assert app.toolbar.directory_label.cget("text") == "/fake/dir"


def test_select_directory_enables_profile_menu(app):
    """select_directory enables the profile menu."""
    app.select_directory()
    app.update_idletasks()

    assert app.toolbar.profile_menu.cget("state") == "normal"


def test_select_directory_enables_generate_pre_commit(app):
    """select_directory enables the generate pre-commit button in the sidebar."""
    app.select_directory()
    app.update_idletasks()

    assert app.sidebar.generate_pre_commit_button.cget("state") == "normal"


def test_select_directory_cancelled(app):
    """When the file dialog is cancelled (returns ''), the directory is not changed."""
    from unittest.mock import patch as _patch

    original_directory = app.controller.current_directory

    with _patch("ruff_studio.main.filedialog") as mock_filedialog:
        mock_filedialog.askdirectory.return_value = ""
        app.select_directory()

    app.update_idletasks()

    assert app.controller.current_directory == original_directory


# ---------------------------------------------------------------------------
# stage_rule_change and stage_category_change
# ---------------------------------------------------------------------------

def test_stage_rule_change_enables_buttons(app):
    """stage_rule_change records the staged change and enables action buttons."""
    app.stage_rule_change("E501", "select")
    app.update_idletasks()

    assert app.controller.staged_changes["E501"] == "select"
    assert app.toolbar.simulate_button.cget("state") == "normal"
    assert app.toolbar.apply_button.cget("state") == "normal"


def test_stage_category_change(app):
    """stage_category_change stores the prefix-level staged change."""
    app.stage_category_change("E", "ignore")
    app.update_idletasks()

    assert app.controller.staged_changes["E"] == "ignore"


def test_stage_category_change_clears_rule_overrides(app):
    """stage_category_change removes per-rule staged changes within the same prefix."""
    # Stage a per-rule override first.
    app.controller.staged_changes["E501"] = "select"

    # Staging the whole category must sweep out the per-rule entry.
    app.stage_category_change("E", "ignore")
    app.update_idletasks()

    assert "E501" not in app.controller.staged_changes
    assert app.controller.staged_changes["E"] == "ignore"


# ---------------------------------------------------------------------------
# navigate_items
# ---------------------------------------------------------------------------

def test_navigate_items_down(app):
    """Pressing Down increments the navigable_index."""
    app.populate_rules_initial()
    app.update_idletasks()

    # Start at the beginning.
    app.controller.navigable_index = 0

    app.navigate_items(MagicMock(keysym="Down"))
    app.update_idletasks()

    assert app.controller.navigable_index > 0


def test_navigate_items_up_at_zero(app):
    """Pressing Up when already at index 0 clamps the index to 0."""
    app.populate_rules_initial()
    app.update_idletasks()

    app.controller.navigable_index = 0
    app.navigate_items(MagicMock(keysym="Up"))
    app.update_idletasks()

    assert app.controller.navigable_index == 0


def test_navigate_items_empty(app):
    """navigate_items is a no-op and does not raise when navigable_items is empty."""
    app.controller.navigable_items = []
    # Should not raise.
    app.navigate_items(MagicMock(keysym="Down"))
    app.update_idletasks()


# ---------------------------------------------------------------------------
# select_category and show_rule_info
# ---------------------------------------------------------------------------

def test_select_category(app):
    """select_category records the selected item and highlights the category frame."""
    app.select_category("Error")
    app.update_idletasks()

    assert app.controller.selected_item is not None
    assert app.controller.selected_item["name"] == "Error"
    assert app.selected_category_frame is not None


def test_show_rule_info(app):
    """show_rule_info sets the info panel label and marks the rule frame as selected."""
    rule = MOCK_RULES["Error"]["rules"][0]  # E501

    app.show_rule_info(rule, "Error")
    app.update_idletasks()

    assert app.info_panel.info_label.cget("text") == "Rule: E501"
    assert app.selected_rule_frame is not None


# ---------------------------------------------------------------------------
# toggle_category_rules
# ---------------------------------------------------------------------------

def test_toggle_category_rules_collapses_then_expands(app):
    """toggle_category_rules collapses an expanded category and re-expands it."""
    # The fixture calls populate_rules_initial(), so categories start expanded.
    assert app.rules_panel.rule_widgets["Error"]["is_expanded"] is True

    # First toggle: collapse.
    app.toggle_category_rules("Error")
    app.update_idletasks()
    assert app.rules_panel.rule_widgets["Error"]["is_expanded"] is False

    # Second toggle: expand.
    app.toggle_category_rules("Error")
    app.update_idletasks()
    assert app.rules_panel.rule_widgets["Error"]["is_expanded"] is True


# ---------------------------------------------------------------------------
# open_proposals_dashboard and open_analytics
# ---------------------------------------------------------------------------

def test_open_proposals_dashboard(app):
    """open_proposals_dashboard switches the view so proposals_view is visible."""
    app.open_proposals_dashboard()
    app.update_idletasks()

    assert app.proposals_view.winfo_ismapped()


def test_open_analytics(app):
    """open_analytics switches the view so analytics_view is visible."""
    app.open_analytics()
    app.update_idletasks()

    assert app.analytics_view.winfo_ismapped()


# ---------------------------------------------------------------------------
# Property accessors (lines 58-114)
# ---------------------------------------------------------------------------

def test_app_property_accessors(app):
    """All convenience properties defined on App resolve to a non-None value."""
    # Controller-backed properties
    assert app.analyzer is not None
    assert app.current_directory is not None
    assert app.pyproject_path is not None
    assert app.pyproject_data is not None
    assert app.staged_changes is not None

    # Toolbar-backed properties
    assert app.select_button is not None
    assert app.apply_button is not None
    assert app.simulate_button is not None
    assert app.profile_menu is not None
    assert app.status_label is not None

    # Sidebar-backed property
    assert app.generate_pre_commit_button is not None

    # results_panel-backed property
    assert app.results_label is not None

    # rules_panel-backed property
    assert app.rules_frame is not None

    # toolbar aliases
    assert app.top_frame is not None
    assert app.action_frame is not None


# ---------------------------------------------------------------------------
# simulate_changes (lines 267-272)
# ---------------------------------------------------------------------------

def test_simulate_changes_sets_status_simulating(app):
    """simulate_changes sets the status label to 'Simulating...' before delegating to a thread."""
    import tomlkit as _tomlkit

    # Provide pyproject_data so get_effective_configs() returns a usable config.
    app.controller.pyproject_data = _tomlkit.parse("[tool.ruff.lint]\nselect = [\"E\"]")

    # StudioController.run_in_thread is already patched to a no-op by the fixture,
    # so no real thread is spawned.  simulate_changes must set the status label
    # *before* it calls run_in_thread.
    app.simulate_changes()
    app.update_idletasks()

    assert app.toolbar.status_label.cget("text") == "Simulating..."


def test_simulate_changes_does_not_raise_without_pyproject(app):
    """simulate_changes is safe to call when pyproject_data is None (empty config)."""
    app.controller.pyproject_data = None

    # get_effective_configs() returns ({}, {}) when pyproject_data is None,
    # so simulate_changes should still proceed without raising.
    app.simulate_changes()
    app.update_idletasks()

    # Status was set to "Simulating..." before the (mocked) thread call.
    assert app.toolbar.status_label.cget("text") == "Simulating..."


# ---------------------------------------------------------------------------
# fetch_rule_docs (lines 433-435)
# ---------------------------------------------------------------------------

def test_fetch_rule_docs_sets_status_fetching(app):
    """fetch_rule_docs sets the toolbar status to 'Fetching Docs...' and delegates to a thread."""
    rule = {"code": "E501", "name": "LineTooLong", "summary": "S", "status": "stable"}

    # App.run_in_thread is patched to a no-op by the fixture, so no real thread
    # is spawned.  We only verify the synchronous side-effect: the status label.
    app.fetch_rule_docs(rule)
    app.update_idletasks()

    assert app.toolbar.status_label.cget("text") == "Fetching Docs..."


def test_fetch_rule_docs_calls_run_in_thread(app):
    """fetch_rule_docs passes the correct command name to controller.run_in_thread."""
    from unittest.mock import patch as _patch

    rule = {"code": "F401", "name": "UnusedImport", "summary": "An imported module is not used.", "status": "stable"}

    captured = {}

    def _fake_run_in_thread(self_inner, worker, command_name, *args):
        captured["command"] = command_name
        captured["rule"] = args[0] if args else None

    with _patch.object(StudioController, "run_in_thread", _fake_run_in_thread):
        app.fetch_rule_docs(rule)

    assert captured.get("command") == "fetch_docs"
    assert captured.get("rule") == rule


# ---------------------------------------------------------------------------
# process_queue — additional command variants not yet covered
# ---------------------------------------------------------------------------

def test_process_queue_run_full_scan_empty_list(app):
    """process_queue with run_full_scan and an empty list resets base_scan_results to []."""
    app.controller.base_scan_results = None  # dirty state

    app.controller.queue.put(("run_full_scan", []))
    app.process_queue()
    app.update_idletasks()

    assert app.controller.base_scan_results == []


def test_process_queue_discover_rules_updates_controller(app):
    """process_queue with discover_rules replaces all_rules with the supplied dict."""
    minimal_rules = {
        "Error": {
            "prefix": "E",
            "rules": [
                {"code": "E501", "name": "LineTooLong", "summary": "S", "status": "stable"}
            ],
        }
    }
    app.controller.all_rules = {}

    app.controller.queue.put(("discover_rules", minimal_rules))
    app.process_queue()
    app.update_idletasks()

    assert app.controller.all_rules == minimal_rules


def test_process_queue_error_calls_showerror(app):
    """process_queue with an error command invokes messagebox.showerror with the message."""
    import ruff_studio.main as main_module

    app.controller.queue.put(("error", "something broke"))
    app.process_queue()
    app.update_idletasks()

    main_module.messagebox.showerror.assert_called()
    call_args = main_module.messagebox.showerror.call_args
    # The second positional arg is the formatted error string.
    assert "something broke" in call_args[0][1]


# ---------------------------------------------------------------------------
# select_directory — with explicit directory argument (bypasses filedialog)
# ---------------------------------------------------------------------------

def test_select_directory_with_explicit_path(app):
    """Passing a directory directly to select_directory skips the file dialog."""
    app.select_directory("/explicit/path")
    app.update_idletasks()

    assert app.controller.current_directory == "/explicit/path"
    assert app.toolbar.profile_menu.cget("state") == "normal"
    assert app.sidebar.generate_pre_commit_button.cget("state") == "normal"


# ---------------------------------------------------------------------------
# stage_rule_change — simulate_button and apply_button both enabled
# ---------------------------------------------------------------------------

def test_stage_rule_change_enables_both_action_buttons(app):
    """stage_rule_change enables both the simulate and apply buttons."""
    # Ensure both start disabled so the test is meaningful.
    app.toolbar.simulate_button.configure(state="disabled")
    app.toolbar.apply_button.configure(state="disabled")

    app.stage_rule_change("E501", "ignore")
    app.update_idletasks()

    assert app.controller.staged_changes["E501"] == "ignore"
    assert app.toolbar.simulate_button.cget("state") == "normal"
    assert app.toolbar.apply_button.cget("state") == "normal"


# ---------------------------------------------------------------------------
# navigate_items — round-trip Down then Up
# ---------------------------------------------------------------------------

def test_navigate_items_down_then_up_returns_to_start(app):
    """Navigating Down then Up returns the navigable_index to its original position."""
    app.populate_rules_initial()
    app.update_idletasks()

    app.controller.navigable_index = 0
    app.navigate_items(MagicMock(keysym="Down"))
    app.update_idletasks()
    assert app.controller.navigable_index == 1

    app.navigate_items(MagicMock(keysym="Up"))
    app.update_idletasks()
    assert app.controller.navigable_index == 0


# ---------------------------------------------------------------------------
# select_category — selected_item type is "category"
# ---------------------------------------------------------------------------

def test_select_category_selected_item_type_is_category(app):
    """select_category stores a selected_item dict with type == 'category'."""
    app.select_category("Error")
    app.update_idletasks()

    assert app.controller.selected_item is not None
    assert app.controller.selected_item["type"] == "category"
    assert app.controller.selected_item["name"] == "Error"


# ---------------------------------------------------------------------------
# show_rule_info — selected_item type is "rule" and info_label is updated
# ---------------------------------------------------------------------------

def test_show_rule_info_selected_item_type_is_rule(app):
    """show_rule_info stores a selected_item dict with type == 'rule'."""
    rule = {"code": "E501", "name": "LineTooLong", "summary": "S", "status": "stable"}

    app.show_rule_info(rule, "Error")
    app.update_idletasks()

    assert app.controller.selected_item is not None
    assert app.controller.selected_item["type"] == "rule"


def test_show_rule_info_updates_info_label(app):
    """show_rule_info updates the info panel label to 'Rule: <code>'."""
    rule = {"code": "E501", "name": "LineTooLong", "summary": "S", "status": "stable"}

    app.show_rule_info(rule, "Error")
    app.update_idletasks()

    assert app.info_panel.info_label.cget("text") == "Rule: E501"
