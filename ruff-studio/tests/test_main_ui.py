import pytest
import os
from ruff_studio.main import App
from ruff_studio.controller import StudioController
from unittest.mock import patch, MagicMock, mock_open
import tomlkit

# MOCK_RULES is now intentionally non-alphabetical to test display order.
MOCK_RULES = {
    "Error": {
        "prefix": "E",
        "rules": [
            {
                "code": "E501", "name": "LineTooLong", 
                "summary": "Line too long.", "fix": False, "status": "stable"
            },
        ],
    },

    "Pyflakes": {
        "prefix": "F",
        "rules": [
            {
                "code": "F401", "name": "UnusedImport", 
                "summary": "An imported module is not used.", 
                "fix": True, "status": "stable"
            },
            {
                "code": "F841", "name": "UnusedLocalVariable", 
                "summary": "A local variable is assigned but never used.", 
                "fix": False, "status": "stable"
            },
        ],
    },
    "Pylint: Convention": {
        "prefix": "C",
        "rules": [
            {
                "code": "C0103", "name": "invalid-name", 
                "summary": "Invalid name for variable.", 
                "fix": False, "status": "stable"
            },
        ],
    },
}

@pytest.fixture
def app():
    """
    Pytest fixture to create a fully initialized App instance for UI testing.
    Note: This fixture requires a virtual display (like xvfb) to run.
    """
    # Patch the `run_in_thread` method to prevent background tasks from
    # running during the test and interfering with our mock data.
    with patch.object(App, 'run_in_thread', return_value=None):
        with patch.object(StudioController, 'run_in_thread', return_value=None):
            app_instance = App()

    # Manually set the rules data via controller
    app_instance.controller.all_rules = MOCK_RULES
    app_instance.controller.current_directory = "/fake/dir"
    app_instance.controller.pyproject_path = "/fake/dir/pyproject.toml"
    app_instance.controller.pyproject_data = tomlkit.parse("dummy = true")
    app_instance.controller.analyzer.conn = MagicMock()

    # Manually call the UI population method to create the widgets
    # This also populates controller.navigable_items
    app_instance.populate_rules_initial()

    # Process any pending events to ensure the UI is fully drawn and ready
    app_instance.update_idletasks()

    yield app_instance

    # Teardown the app window after the test completes
    app_instance.destroy()

def test_toggle_category_rules(app):
    """
    Tests that the expand/collapse button for a rule category works correctly.
    """
    category_name = "Pyflakes"

    # Get the relevant widgets from the app instance
    toggle_button = app.rules_panel.rule_widgets[category_name]['toggle_button']
    rules_container = app.rules_panel.rule_widgets[category_name]['rules_container']

    # --- 1. Initial State ---
    # The container for the rules should be visible by default after initialization.
    # The button text should indicate it can be collapsed (e.g., "▼").
    assert rules_container.winfo_viewable() == 1
    assert toggle_button.cget("text") == "▼"

    # --- 2. First Click: Collapse the view ---
    # Simulate a user click on the toggle button.
    toggle_button.invoke()
    app.update_idletasks() # Process the UI event

    # The container should now be hidden.
    assert rules_container.winfo_viewable() == 0
    assert toggle_button.cget("text") == "▶"

    # --- 3. Second Click: Expand the view ---
    # Simulate a second click on the same button.
    toggle_button.invoke()
    app.update_idletasks() # Process the UI event

    # The container should be visible again, restoring the initial state.
    assert rules_container.winfo_viewable() == 1
    assert toggle_button.cget("text") == "▼"

def test_visual_keyboard_navigation(app):
    """
    Tests that keyboard navigation follows the visual order of the UI,
    including navigating between rules and category headers.
    """
    # --- 1. Verify Navigation Order ---
    # The navigable list should contain categories and their rules in their
    # natural (non-alphabetical) display order.
    nav_item_reprs = []
    for item in app.controller.navigable_items:
        if item['type'] == 'category':
            nav_item_reprs.append(f"CAT:{item['name']}")
        else:
            nav_item_reprs.append(f"RULE:{item['data']['code']}")

    expected_order = [
        "CAT:Error", "RULE:E501",
        "CAT:Pyflakes", "RULE:F401", "RULE:F841",
        "CAT:Pylint: Convention", "RULE:C0103",
    ]
    assert nav_item_reprs == expected_order

    up_event = MagicMock()
    up_event.keysym = "Up"
    down_event = MagicMock()
    down_event.keysym = "Down"

    # --- 2. Start Selection ---
    # Start by selecting the first rule, E501.
    target_rule = app.controller.navigable_items[1]['data']
    target_cat = app.controller.navigable_items[1]['category_name']
    app.show_rule_info(target_rule, target_cat)
    app.update_idletasks()
    assert app.controller.selected_item['data']['code'] == 'E501'

    # --- 3. Navigate Up to Category ---
    # Pressing Up from the first rule should select its category header.
    app.navigate_items(up_event)
    app.update_idletasks()
    assert app.controller.selected_item['type'] == 'category'
    assert app.controller.selected_item['name'] == 'Error'

    # --- 4. Boundary Check (Top) ---
    # Pressing Up again should not change the selection.
    app.navigate_items(up_event)
    app.update_idletasks()
    assert app.controller.selected_item['name'] == 'Error'

    # --- 5. Navigate Down to First Rule ---
    app.navigate_items(down_event)
    app.update_idletasks()
    assert app.controller.selected_item['data']['code'] == 'E501'

    # --- 6. Navigate Down to Next Category ---
    # Pressing Down from the last rule in a category should select the next category.
    app.navigate_items(down_event)
    app.update_idletasks()
    assert app.controller.selected_item['type'] == 'category'
    assert app.controller.selected_item['name'] == 'Pyflakes'

def test_pylint_configuration_workflow(app, tmp_path):
    """
    Tests the full workflow for configuring pylint rules, including loading,
    staging, and applying changes.
    """
    # --- 1. Setup: Create a mock pyproject.toml with pylint config ---
    pyproject_content = """
[tool.pylint]
disable = ["C0103"]
"""
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(pyproject_content)

    # --- 2. Load the project and verify initial state ---
    # Patch `run_full_scan_worker` to prevent real scanning
    with patch.object(app.controller, 'run_full_scan_worker', return_value=None):
        app.select_directory(str(tmp_path))
    app.update_idletasks()

    # Check that the C0103 rule is correctly identified as "ignore"
    pylint_rule_widget = app.rules_panel.rule_widgets["Pylint: Convention"]['rules']['C0103']
    assert pylint_rule_widget['radio_variable'].get() == "ignore"

    # Check that a ruff rule is "default"
    ruff_rule_widget = app.rules_panel.rule_widgets["Pyflakes"]['rules']['F401']
    assert ruff_rule_widget['radio_variable'].get() == "default"

    # --- 3. Stage a change: Enable the pylint rule ---
    # Simulate clicking the "default" radio button for C0103
    pylint_rule_widget['radio_variable'].set("default")
    app.stage_rule_change("C0103", "default")
    app.update_idletasks()

    # The radio button should now be "default"
    assert pylint_rule_widget['radio_variable'].get() == "default"
    assert "C0103" in app.controller.staged_changes

    # --- 4. Apply the changes ---
    # This should write the changes back to the pyproject.toml
    # Disable proposal window for tests to apply immediately
    with patch.object(app.controller, 'run_full_scan_worker', return_value=None):
        app.apply_changes(show_proposal_window=False)
    app.update_idletasks()

    # --- 5. Verify the pyproject.toml was updated correctly ---
    updated_data = tomlkit.parse(pyproject_path.read_text())

    # The `disable` list should now be empty or not present
    pylint_config = updated_data.get("tool", {}).get("pylint", {})
    assert "C0103" not in pylint_config.get("disable", [])

def test_apply_profile(app):
    """Tests that applying a profile correctly stages changes."""
    mock_profile = {
        "profile": {
            "name": "test-profile",
            "rules": {
                "ruff": {"select": ["E"], "ignore": ["F"]},
                "pylint": {"disable": ["C0103"]}
            }
        }
    }
    
    with patch('ruff_studio.profile_manager.load_profile', return_value=mock_profile):
        app.apply_profile("test-profile")
    
    # Check that changes are staged
    # Ruff: E select, F ignore (F401, F841 are under Pyflakes/F)
    assert app.controller.staged_changes.get("F401") == "ignore"
    assert app.controller.staged_changes.get("F841") == "ignore"
    # Pylint: C0103 ignore
    assert app.controller.staged_changes.get("C0103") == "ignore"

def test_stage_category_change(app):
    """Tests that staging a change for a whole category works."""
    # Pyflakes has prefix 'F'
    app.stage_category_change("F", "select")
    assert app.controller.staged_changes["F"] == "select"
    # Individual rules should be cleared from staged if category is changed
    app.controller.staged_changes["F401"] = "ignore"
    app.stage_category_change("F", "default")
    assert "F401" not in app.controller.staged_changes

@patch('ruff_studio.proposal_manager.create_proposal')
def test_proposal_window_logic(mock_create, app):
    """Tests the logic inside ProposalWindow."""
    from ruff_studio.ui.proposal_window import ProposalWindow
    
    win = ProposalWindow(app, "before", "after", {"impact": "low"})
    win.title_entry.insert(0, "Test Proposal")
    win.rationale_text.insert("1.0", "Some rationale")
    
    win.create_only()
    
    mock_create.assert_called_once_with(
        app.controller.analyzer.conn, "Test Proposal", "Some rationale",
        "before", "after", {"impact": "low"}
    )

@patch('ruff_studio.proposal_manager.update_proposal_status', return_value=True)
@patch('ruff_studio.proposal_manager.get_proposals')
def test_proposals_dashboard(mock_get, mock_update, app):
    """Tests that the ProposalsDashboard can load and approve proposals."""
    from ruff_studio.ui.dashboard_window import ProposalsDashboard
    
    mock_p = {
        "id": "123", "title": "P1", "status": "pending", 
        "author": "A", "created_at": "now", "rationale": "R",
        "impact_simulation": "[]", "config_before": "", "config_after": ""
    }
    mock_get.return_value = [mock_p]
    
    dash = ProposalsDashboard(app)
    # Selection logic is triggered by clicking button in list
    dash.show_detail(mock_p)
    assert dash.detail_title.cget("text") == "P1"
    
    dash.approve()
    mock_update.assert_called_once_with(app.controller.analyzer.conn, "123", "approved")

@patch('ruff_studio.proposal_manager.update_proposal_status', return_value=True)
@patch('ruff_studio.proposal_manager.get_proposals')
def test_proposals_dashboard_reject(mock_get, mock_update, app):
    """Tests rejecting a proposal from the dashboard."""
    from ruff_studio.ui.dashboard_window import ProposalsDashboard
    mock_p = {"id": "1", "title": "T", "status": "pending", "author": "A", 
              "created_at": "N", "rationale": "R", "impact_simulation": "{}",
              "config_before": "", "config_after": ""}
    mock_get.return_value = [mock_p]
    
    with patch('tkinter.messagebox.showinfo'):
        dash = ProposalsDashboard(app)
        dash.current_proposal = mock_p
        dash.reject()
        mock_update.assert_called_once_with(app.controller.analyzer.conn, "1", "rejected")

def test_select_directory_no_config(app, tmp_path):
    """Tests select_directory when no pyproject.toml exists."""
    with patch('customtkinter.filedialog.askdirectory', return_value=str(tmp_path)):
        with patch('os.path.exists', return_value=False):
            with patch.object(app.controller, 'run_in_thread'):
                app.select_directory()
                assert app.controller.current_directory == str(tmp_path)
                assert app.controller.pyproject_path == os.path.join(str(tmp_path), "pyproject.toml")

def test_ui_initialization(app):
    """Tests that all expected UI components are created."""
    assert app.top_frame is not None
    assert app.action_frame is not None
    assert app.rules_frame is not None
    assert app.info_frame is not None
    assert app.results_frame is not None
    # Check some buttons
    assert app.apply_button.cget("text") == "Apply Changes"
    assert app.simulate_button.cget("text") == "Simulate Changes"

def test_profile_comparison_logic(app):
    """Tests that ProfileComparisonWindow correctly finds differences."""
    from ruff_studio.ui.comparison_window import ProfileComparisonWindow
    
    mock_p1 = {"profile": {"rules": {"ruff": {"select": ["E"], "ignore": ["F"]}}}}
    mock_p2 = {"profile": {"rules": {"ruff": {"select": ["F"], "ignore": ["E"]}}}}
    
    with patch('ruff_studio.profile_manager.get_built_in_profiles', return_value=["p1", "p2"]):
        with patch('ruff_studio.profile_manager.load_profile', side_effect=[mock_p1, mock_p2]):
            win = ProfileComparisonWindow(app)
            win.profile1_var.set("p1")
            win.profile2_var.set("p2")
            
            # Patch the compare_profiles to avoid real file logic if needed, 
            # or rely on the fact that we mocked get_built_in_profiles
            diff = {
                "select_only_in_1": ["E"], "select_only_in_2": ["F"],
                "ignore_only_in_1": ["F"], "ignore_only_in_2": ["E"],
                "common_select": [], "common_ignore": []
            }
            with patch('ruff_studio.profile_manager.compare_profiles', return_value=diff):
                win.do_comparison()
                report = win.results_textbox.get("1.0", "end")
                assert "Only in 'p1':" in report
                assert "- E" in report

@patch('ruff_studio.git_adapter.commit_changes')
@patch('ruff_studio.git_adapter.create_branch', return_value=True)
@patch('ruff_studio.git_adapter.is_repo_clean', return_value=True)
@patch('ruff_studio.proposal_manager.create_proposal')
def test_proposal_window_commit(mock_create, mock_clean, mock_branch, mock_commit, app):
    """Tests the create_and_commit path in ProposalWindow."""
    from ruff_studio.ui.proposal_window import ProposalWindow
    
    with patch('tkinter.messagebox.showinfo'):
        with patch('ruff_studio.config_manager.read_pyproject_text', return_value=""):
            with patch('ruff_studio.config_manager.write_pyproject'):
                win = ProposalWindow(app, "b", "a", {})
                win.title_entry.insert(0, "Title")
                win.create_and_commit()
        
        mock_branch.assert_called_once()
        mock_commit.assert_called_once()
        assert mock_create.call_count == 1

def test_discover_rules_worker(app):
    """Tests that the discover_rules_worker puts results in the queue."""
    with patch('ruff_studio.ruff_adapter.discover_rules', return_value={"R": {}}):
        with patch('ruff_studio.pylint_adapter.discover_rules', return_value={"P": {}}):
            app.controller.discover_rules_worker("discover_rules")
            command, data = app.controller.queue.get()
            assert command == "discover_rules"
            assert "R" in data
            assert "Pylint: P" in data

def test_run_full_scan_worker(app):
    """Tests that the run_full_scan_worker puts results in the queue."""
    with patch.object(app.controller.analyzer, 'run_full_scan', return_value=["v1"]):
        app.controller.run_full_scan_worker("run_full_scan", "/dir")
        command, data = app.controller.queue.get()
        assert command == "run_full_scan"
        assert data == ["v1"]

def test_process_queue_discover(app):
    """Tests that process_queue correctly handles discover_rules command."""
    mock_data = {"CAT": {"prefix": "C", "rules": [{"code": "C01", "name": "N", "summary": "S", "fix": False, "status": "stable"}]}}
    app.controller.queue.put(("discover_rules", mock_data))
    
    # process_queue calls populate_rules_initial
    app.process_queue()
    
    assert app.controller.all_rules == mock_data
    assert "CAT" in app.rules_panel.rule_widgets

def test_apply_changes_with_proposal(app, tmp_path):
    """Tests that apply_changes triggers ProposalWindow."""
    # Set attributes directly instead of calling select_directory
    app.controller.current_directory = str(tmp_path)
    app.controller.pyproject_path = str(tmp_path / "pyproject.toml")
    app.controller.pyproject_data = tomlkit.parse("test = true")
    
    with patch('ruff_studio.ruff_adapter.run_scan_with_config', return_value=[]):
        with patch('ruff_studio.config_manager.read_pyproject_text', return_value=""):
            with patch('ruff_studio.main.ProposalWindow') as mock_win:
                app.apply_changes(show_proposal_window=True)
                mock_win.assert_called_once()

def test_apply_changes_direct(app, tmp_path):
    """Tests applying changes directly without proposal."""
    app.controller.current_directory = str(tmp_path)
    app.controller.pyproject_path = str(tmp_path / "pyproject.toml")
    app.controller.pyproject_data = tomlkit.parse("dummy = true")
    
    with patch('ruff_studio.config_manager.write_pyproject') as mock_write:
        with patch('ruff_studio.config_manager.read_pyproject_text', return_value=""):
            app.apply_changes(show_proposal_window=False)
            mock_write.assert_called_once()


def test_open_windows(app):
    """Tests that opening other windows doesn't crash."""
    with patch('ruff_studio.ui.comparison_window.ProfileComparisonWindow'):
        app.open_comparison_window()
    with patch('ruff_studio.ui.dashboard_window.ProposalsDashboard'):
        app.open_proposals_dashboard()

def test_generate_pre_commit(app, tmp_path):
    """Tests pre-commit configuration generation."""
    app.controller.current_directory = str(tmp_path)
    with patch('ruff_studio.ruff_adapter.get_ruff_version', return_value="0.1.0"):
        with patch('ruff_studio.ci_integration.generate_pre_commit_config', return_value="yaml"):
            with patch('customtkinter.filedialog.asksaveasfilename', return_value=str(tmp_path/"pre.yaml")):
                with patch('builtins.open', mock_open()) as m:
                    app.generate_pre_commit_config_file()
                    m.assert_called_once_with(str(tmp_path/"pre.yaml"), "w")

def test_update_results_panel(app):
    """Tests that update_results_panel correctly displays violations."""
    from ruff_studio.workspace_analyzer import UnifiedViolationModel
    import customtkinter as ctk
    
    mock_violation = UnifiedViolationModel(
        rule_id="E501", file_path="f.py", line_number=1, column=1, 
        message="Too long", author="Dev"
    )
    
    app.update_results_panel([mock_violation])
    labels = [w for w in app.results_frame.winfo_children() if isinstance(w, ctk.CTkLabel)]
    violation_labels = [l for l in labels if "E501" in l.cget("text")]
    assert len(violation_labels) == 1
    assert "Author: Dev" in violation_labels[0].cget("text")

def test_show_rule_info_with_scrape(app):
    """Tests that show_rule_info triggers doc scraping button."""
    rule = MOCK_RULES["Error"]["rules"][0].copy()
    rule["documentation"] = None # Force scrape
    
    # Initialize widget structure for this rule to avoid UI errors
    app.rules_panel.rule_widgets["Error"] = {
        'prefix': 'E',
        'rules': {
            'E501': {
                'frame': MagicMock(),
                'effective_state_variable': MagicMock(),
                'radio_variable': MagicMock()
            }
        },
        'category_frame': MagicMock()
    }
    
    # Initialize selected_item to avoid NoneType error
    app.controller.selected_item = {
        'type': 'rule', 'data': rule, 'category_name': 'Error'
    }
    
    app.show_rule_info(rule, "Error")
        
    # Check if a button was created
    import customtkinter as ctk
    buttons = [
        w for w in app.info_frame.winfo_children() 
        if isinstance(w, ctk.CTkButton) and "Fetch" in w.cget("text")
    ]
    assert len(buttons) == 1
    
    # Trigger fetch
    with patch.object(app.controller, 'run_in_thread') as mock_run:
        buttons[0].invoke()
        mock_run.assert_called_once()
