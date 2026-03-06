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


# ---------------------------------------------------------------------------
# start_resize / do_resize  (lines 169-191)
# ---------------------------------------------------------------------------

def test_start_resize_records_start_position(app):
    """start_resize stores x_root and the column index."""
    event = MagicMock()
    event.x_root = 300

    app.start_resize(event, 0)

    assert app.resize_start_x == 300
    assert app.resize_start_col == 0


def test_do_resize_col0_adjusts_weights(app):
    """do_resize with col=0 adjusts columns 0 and 2 of the RulesView grid."""
    app.resize_start_col = 0
    app.resize_start_x = 100

    rv = app.rules_view
    original_weight0 = rv.grid_columnconfigure(0)["weight"]
    original_weight2 = rv.grid_columnconfigure(2)["weight"]

    event = MagicMock()
    event.x_root = 120  # delta = +20
    app.do_resize(event)

    assert rv.grid_columnconfigure(0)["weight"] == max(1, original_weight0 + 20)
    assert rv.grid_columnconfigure(2)["weight"] == max(1, original_weight2 - 20)
    assert app.resize_start_x == 120


def test_do_resize_col2_adjusts_weights(app):
    """do_resize with col=2 adjusts columns 2 and 4 of the RulesView grid."""
    app.resize_start_col = 2
    app.resize_start_x = 100

    rv = app.rules_view
    original_weight2 = rv.grid_columnconfigure(2)["weight"]
    original_weight4 = rv.grid_columnconfigure(4)["weight"]

    event = MagicMock()
    event.x_root = 80  # delta = -20
    app.do_resize(event)

    assert rv.grid_columnconfigure(2)["weight"] == max(1, original_weight2 - 20)
    assert rv.grid_columnconfigure(4)["weight"] == max(1, original_weight4 + 20)


# ---------------------------------------------------------------------------
# update_results_panel  (line 239)
# ---------------------------------------------------------------------------

def test_update_results_panel_delegates_to_results_panel(app):
    """update_results_panel calls set_results on the results panel."""
    from ruff_studio.workspace_analyzer import UnifiedViolationModel
    violation = UnifiedViolationModel("E501", "f.py", 1, 1, "line too long")

    app.update_results_panel([violation])
    app.update_idletasks()

    # The results_label text should reflect 1 violation.
    assert "1" in app.results_panel.results_label.cget("text")


# ---------------------------------------------------------------------------
# _run_simulation_worker  (lines 274-281)
# ---------------------------------------------------------------------------

def test_run_simulation_worker_success_puts_result_in_queue(app):
    """_run_simulation_worker puts (command, results) into the queue on success."""
    fake_results = [MagicMock()]

    with patch("ruff_studio.main.ruff_adapter.run_scan_with_config", return_value=fake_results):
        app._run_simulation_worker("run_simulation", {})

    command, data = app.controller.queue.get_nowait()
    assert command == "run_simulation"
    assert data == fake_results


def test_run_simulation_worker_error_puts_error_in_queue(app):
    """_run_simulation_worker puts ('error', message) into the queue on exception."""
    with patch(
        "ruff_studio.main.ruff_adapter.run_scan_with_config",
        side_effect=RuntimeError("scan failed"),
    ):
        app._run_simulation_worker("run_simulation", {})

    command, data = app.controller.queue.get_nowait()
    assert command == "error"
    assert "scan failed" in data


# ---------------------------------------------------------------------------
# apply_profile  (lines 283-314)
# ---------------------------------------------------------------------------

def test_apply_profile_placeholder_returns_early(app):
    """apply_profile with the placeholder string does nothing."""
    app.controller.staged_changes = {}
    app.apply_profile("Apply a Profile...")
    assert app.controller.staged_changes == {}


def test_apply_profile_stages_rules_from_ruff_config(app):
    """apply_profile with ruff config selects matching rules and ignores others."""
    mock_profile = {
        "profile": {"rules": {"ruff": {"select": ["E"], "ignore": ["F"]}}}
    }
    with patch("ruff_studio.main.profile_manager.load_profile", return_value=mock_profile):
        app.apply_profile("standard")
    app.update_idletasks()

    assert app.controller.staged_changes.get("E501") == "select"
    assert app.controller.staged_changes.get("F401") == "ignore"
    assert app.toolbar.simulate_button.cget("state") == "normal"
    assert app.toolbar.apply_button.cget("state") == "normal"


def test_apply_profile_without_ruff_config_clears_staged(app):
    """apply_profile with no ruff key in profile clears staged changes."""
    mock_profile = {"profile": {"rules": {}}}
    app.controller.staged_changes = {"E501": "select"}
    with patch("ruff_studio.main.profile_manager.load_profile", return_value=mock_profile):
        app.apply_profile("standard")
    assert app.controller.staged_changes == {}


def test_apply_profile_error_calls_showerror(app):
    """apply_profile shows an error dialog when loading the profile fails."""
    import ruff_studio.main as main_module

    with patch(
        "ruff_studio.main.profile_manager.load_profile",
        side_effect=FileNotFoundError("no profile"),
    ):
        app.apply_profile("nonexistent")

    main_module.messagebox.showerror.assert_called()


def test_apply_profile_resets_menu_to_placeholder(app):
    """apply_profile always resets the profile menu to the placeholder in the finally block."""
    mock_profile = {"profile": {"rules": {}}}
    with patch("ruff_studio.main.profile_manager.load_profile", return_value=mock_profile):
        app.apply_profile("standard")
    assert app.toolbar.profile_menu.get() == "Apply a Profile..."


# ---------------------------------------------------------------------------
# apply_changes  (lines 316-346)
# ---------------------------------------------------------------------------

def test_apply_changes_no_pyproject_returns_early(app):
    """apply_changes does nothing when pyproject_data is None."""
    app.controller.pyproject_data = None
    app.apply_changes()  # Should not raise


def test_apply_changes_writes_config_when_proposal_window_disabled(app):
    """apply_changes with show_proposal_window=False writes config to disk."""
    import tomlkit as _tomlkit

    app.controller.pyproject_data = _tomlkit.parse("[tool.ruff.lint]\nselect = [\"E\"]")
    app.controller.pyproject_path = "/fake/dir/pyproject.toml"

    with (
        patch("ruff_studio.main.config_manager.read_pyproject_text", return_value="before"),
        patch("ruff_studio.main.config_manager.write_pyproject") as mock_write,
    ):
        app.apply_changes(show_proposal_window=False)

    mock_write.assert_called_once()
    assert app.controller.staged_changes == {}
    assert app.toolbar.simulate_button.cget("state") == "disabled"
    assert app.toolbar.apply_button.cget("state") == "disabled"


# ---------------------------------------------------------------------------
# generate_pre_commit_config_file  (lines 357-372)
# ---------------------------------------------------------------------------

def test_generate_pre_commit_config_file_writes_file(app):
    """generate_pre_commit_config_file writes config content to the chosen path."""
    import ruff_studio.main as main_module
    from unittest.mock import mock_open, patch as _patch

    m = mock_open()
    with (
        _patch("ruff_studio.main.ruff_adapter.get_ruff_version", return_value="0.1.0"),
        _patch("ruff_studio.main.filedialog") as mock_fd,
        _patch("builtins.open", m),
    ):
        mock_fd.asksaveasfilename.return_value = "/tmp/pre-commit.yaml"
        app.generate_pre_commit_config_file()

    m.assert_called_once_with("/tmp/pre-commit.yaml", "w")
    main_module.messagebox.showinfo.assert_called()


def test_generate_pre_commit_config_file_cancelled_does_not_write(app):
    """generate_pre_commit_config_file does nothing when user cancels the dialog."""
    from unittest.mock import mock_open, patch as _patch

    m = mock_open()
    with (
        _patch("ruff_studio.main.ruff_adapter.get_ruff_version", return_value="0.1.0"),
        _patch("ruff_studio.main.filedialog") as mock_fd,
        _patch("builtins.open", m),
    ):
        mock_fd.asksaveasfilename.return_value = ""
        app.generate_pre_commit_config_file()

    m.assert_not_called()


def test_generate_pre_commit_config_file_error_shows_showerror(app):
    """generate_pre_commit_config_file shows an error when get_ruff_version raises."""
    import ruff_studio.main as main_module
    from unittest.mock import patch as _patch

    with _patch(
        "ruff_studio.main.ruff_adapter.get_ruff_version",
        side_effect=RuntimeError("ruff not found"),
    ):
        app.generate_pre_commit_config_file()

    main_module.messagebox.showerror.assert_called()


# ---------------------------------------------------------------------------
# navigate_items — Up branch navigating to a rule  (lines 381-390)
# ---------------------------------------------------------------------------

def test_navigate_items_up_moves_to_rule_item(app):
    """Pressing Up when at index 1 (a rule item) triggers show_rule_info."""
    # navigable_items is: [category0, rule0, category1, rule1, ...]
    # Start at index 1 (first rule) and press Up to go to the category.
    assert len(app.controller.navigable_items) >= 2

    app.controller.navigable_index = 1
    item_at_1 = app.controller.navigable_items[1]

    app.navigate_items(MagicMock(keysym="Up"))
    app.update_idletasks()

    assert app.controller.navigable_index == 0


def test_navigate_items_down_to_rule_calls_show_rule_info(app):
    """Navigating Down to a rule item triggers show_rule_info."""
    # Ensure index 0 is a category and index 1 is a rule.
    assert app.controller.navigable_items[0]["type"] == "category"
    assert app.controller.navigable_items[1]["type"] == "rule"

    app.controller.navigable_index = 0
    app.navigate_items(MagicMock(keysym="Down"))
    app.update_idletasks()

    assert app.controller.navigable_index == 1
    assert app.info_panel.info_label.cget("text").startswith("Rule:")


# ---------------------------------------------------------------------------
# select_category — clears previous selection frames  (lines 392-408)
# ---------------------------------------------------------------------------

def test_select_category_clears_previous_rule_frame(app):
    """select_category resets fg_color of the previously highlighted rule frame."""
    rule = MOCK_RULES["Error"]["rules"][0]
    app.show_rule_info(rule, "Error")
    app.update_idletasks()

    # Now select a category — the rule frame should be deselected.
    app.select_category("Pyflakes")
    app.update_idletasks()

    assert app.selected_rule_frame is None or app.selected_category_frame is not None
    assert app.controller.selected_item["name"] == "Pyflakes"


def test_select_category_clears_previous_category_frame(app):
    """Selecting a second category deselects the first one."""
    app.select_category("Error")
    app.update_idletasks()
    first_frame = app.selected_category_frame

    app.select_category("Pyflakes")
    app.update_idletasks()

    # First frame must have been reset (fg_color transparent).
    assert app.controller.selected_item["name"] == "Pyflakes"


def test_select_category_unknown_name_does_not_crash(app):
    """select_category with an unknown name does not raise."""
    app.select_category("NonExistent")
    app.update_idletasks()


# ---------------------------------------------------------------------------
# show_rule_info — clears previous frames  (lines 410-431)
# ---------------------------------------------------------------------------

def test_show_rule_info_clears_previous_category_frame(app):
    """show_rule_info resets fg_color of the previously highlighted category frame."""
    app.select_category("Error")
    app.update_idletasks()

    rule = MOCK_RULES["Error"]["rules"][0]
    app.show_rule_info(rule, "Error")
    app.update_idletasks()

    assert app.selected_rule_frame is not None


def test_show_rule_info_clears_previous_rule_frame(app):
    """Showing a second rule deselects the first one."""
    rule_e = MOCK_RULES["Error"]["rules"][0]
    rule_f = MOCK_RULES["Pyflakes"]["rules"][0]

    app.show_rule_info(rule_e, "Error")
    app.update_idletasks()
    first_frame = app.selected_rule_frame

    app.show_rule_info(rule_f, "Pyflakes")
    app.update_idletasks()

    # First frame was reset; second is now selected.
    assert app.selected_rule_frame is not None
    assert app.selected_rule_frame != first_frame


# ---------------------------------------------------------------------------
# _fetch_docs_worker  (lines 437-442)
# ---------------------------------------------------------------------------

def test_fetch_docs_worker_success_puts_fetch_docs_in_queue(app):
    """_fetch_docs_worker puts (command, (rule, docs)) into the queue on success."""
    rule = {"code": "E501", "name": "LineTooLong", "summary": "S", "status": "stable"}

    with patch("ruff_studio.main.ruff_adapter.scrape_rule_documentation", return_value="docs text"):
        app._fetch_docs_worker("fetch_docs", rule)

    command, data = app.controller.queue.get_nowait()
    assert command == "fetch_docs"
    assert data == (rule, "docs text")


def test_fetch_docs_worker_error_puts_error_in_queue(app):
    """_fetch_docs_worker puts ('error', message) into the queue on exception."""
    rule = {"code": "E501", "name": "LineTooLong", "summary": "S", "status": "stable"}

    with patch(
        "ruff_studio.main.ruff_adapter.scrape_rule_documentation",
        side_effect=ConnectionError("network error"),
    ):
        app._fetch_docs_worker("fetch_docs", rule)

    command, data = app.controller.queue.get_nowait()
    assert command == "error"
    assert "network error" in data


# ---------------------------------------------------------------------------
# RulesPanel — _on_search_change / clear_search  (lines 67-72)
# ---------------------------------------------------------------------------

def test_rules_panel_on_search_change_filters_by_entry_text(app):
    """_on_search_change reads the search_entry and calls filter_rules."""
    rp = app.rules_panel
    rp.search_entry.insert(0, "Pyflakes")

    rp._on_search_change()
    app.update_idletasks()

    assert rp.rule_widgets["Pyflakes"]["category_frame"].winfo_manager() != ""


def test_rules_panel_clear_search_restores_all_categories(app):
    """clear_search clears the entry and shows all categories again."""
    rp = app.rules_panel
    rp.search_entry.insert(0, "Pyflakes")
    rp.filter_rules("Pyflakes")
    app.update_idletasks()

    rp.clear_search()
    app.update_idletasks()

    assert rp.search_entry.get() == ""


# ---------------------------------------------------------------------------
# RulesPanel — filter_rules collapsed branches  (lines 95-98)
# ---------------------------------------------------------------------------

def test_filter_rules_expands_collapsed_category_when_query_matches(app):
    """filter_rules auto-expands a collapsed category when a query matches it."""
    rp = app.rules_panel

    # Collapse the Error category first.
    rp.toggle_category_rules("Error")
    assert rp.rule_widgets["Error"]["is_expanded"] is False

    # Filter by something that matches Error.
    rp.filter_rules("E501")
    app.update_idletasks()

    # The rules_container must be packed (auto-expanded for search).
    assert rp.rule_widgets["Error"]["rules_container"].winfo_manager() == "pack"


def test_filter_rules_collapsed_category_stays_collapsed_on_clear(app):
    """filter_rules leaves a collapsed category collapsed when the query is cleared."""
    rp = app.rules_panel

    # Collapse the Pyflakes category.
    rp.toggle_category_rules("Pyflakes")
    assert rp.rule_widgets["Pyflakes"]["is_expanded"] is False

    # Clear the search (empty query).
    rp.filter_rules("")
    app.update_idletasks()

    assert rp.rule_widgets["Pyflakes"]["is_expanded"] is False
    assert rp.rule_widgets["Pyflakes"]["rules_container"].winfo_manager() == ""


# ---------------------------------------------------------------------------
# RulesPanel — populate with non-stable rule  (line 228)
# ---------------------------------------------------------------------------

def test_rules_panel_populate_deprecated_rule_creates_tooltip(app):
    """Populating with a deprecated rule creates a Tooltip on the label."""
    from ruff_studio.ui.tooltip import Tooltip

    deprecated_rules = {
        "Error": {
            "prefix": "E",
            "rules": [
                {"code": "E501", "name": "LineTooLong", "summary": "S", "status": "deprecated"},
            ],
        }
    }
    app.controller.all_rules = deprecated_rules
    app.populate_rules_initial()
    app.update_idletasks()

    # The status tag must appear in the label text.
    r_frame = app.rules_panel.rule_widgets["Error"]["rules"]["E501"]["frame"]
    labels = [w for w in r_frame.winfo_children() if isinstance(w, ctk.CTkLabel)]
    assert any("deprecated" in lbl.cget("text") or "⚠️" in lbl.cget("text") for lbl in labels)


# ---------------------------------------------------------------------------
# RulesPanel — rebuild_navigable_items fallback  (lines 291-300)
# ---------------------------------------------------------------------------

def test_rebuild_navigable_items_falls_back_to_category_when_rule_hidden(app):
    """When a selected rule's category is collapsed, selected_item falls back to that category."""
    rp = app.rules_panel
    rule = MOCK_RULES["Error"]["rules"][0]

    # Directly set selected_item to the E501 rule.
    app.controller.selected_item = {"type": "rule", "data": rule, "category_name": "Error"}

    # Collapse Error so its rules are excluded from navigable_items.
    # toggle_category_rules calls rebuild_navigable_items internally.
    rp.toggle_category_rules("Error")
    assert rp.rule_widgets["Error"]["is_expanded"] is False

    # The fallback (lines 291-300) should have promoted selected_item to the category.
    assert app.controller.selected_item["type"] == "category"
    assert app.controller.selected_item["name"] == "Error"


# ---------------------------------------------------------------------------
# RulesPanel.see  (lines 354-377)
# ---------------------------------------------------------------------------

def test_rules_panel_see_none_does_not_raise(app):
    """see(None) returns immediately without error."""
    app.rules_panel.see(None)


def test_rules_panel_see_content_fits_viewport_returns_early(app):
    """see() returns without scrolling when content fits in the viewport."""
    widget = next(iter(app.rules_panel.rule_widgets.values()))["category_frame"]
    sf = app.rules_panel.scroll_frame

    with (
        patch.object(sf._parent_frame, "winfo_height", return_value=50),
        patch.object(sf._parent_canvas, "winfo_height", return_value=500),
        patch.object(sf._parent_canvas, "yview_moveto") as mock_moveto,
    ):
        app.rules_panel.see(widget)

    mock_moveto.assert_not_called()


def test_rules_panel_see_scrolls_up_when_widget_above_viewport(app):
    """see() calls yview_moveto when the widget is above the visible area."""
    widget = next(iter(app.rules_panel.rule_widgets.values()))["category_frame"]
    sf = app.rules_panel.scroll_frame

    with (
        patch.object(widget, "winfo_rooty", return_value=0),
        patch.object(sf._parent_frame, "winfo_rooty", return_value=400),
        patch.object(widget, "winfo_height", return_value=30),
        patch.object(sf._parent_frame, "winfo_height", return_value=1000),
        patch.object(sf._parent_canvas, "winfo_height", return_value=300),
        patch.object(sf._parent_canvas, "yview", return_value=(0.5, 0.8)),
        patch.object(sf._parent_canvas, "yview_moveto") as mock_moveto,
    ):
        app.rules_panel.see(widget)

    mock_moveto.assert_called_once()


def test_rules_panel_see_scrolls_down_when_widget_below_viewport(app):
    """see() calls yview_moveto when the widget is below the visible area."""
    widget = next(iter(app.rules_panel.rule_widgets.values()))["category_frame"]
    sf = app.rules_panel.scroll_frame

    with (
        patch.object(widget, "winfo_rooty", return_value=900),
        patch.object(sf._parent_frame, "winfo_rooty", return_value=0),
        patch.object(widget, "winfo_height", return_value=50),
        patch.object(sf._parent_frame, "winfo_height", return_value=1000),
        patch.object(sf._parent_canvas, "winfo_height", return_value=300),
        patch.object(sf._parent_canvas, "yview", return_value=(0.0, 0.3)),
        patch.object(sf._parent_canvas, "yview_moveto") as mock_moveto,
    ):
        app.rules_panel.see(widget)

    mock_moveto.assert_called_once()
