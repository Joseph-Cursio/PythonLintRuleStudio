import pytest
import os
import customtkinter as ctk
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
    # Also patch messagebox globally for all UI tests to prevent blocking.
    with patch.object(App, 'run_in_thread', return_value=None), \
         patch.object(StudioController, 'run_in_thread', return_value=None), \
         patch('ruff_studio.main.messagebox'), \
         patch('ruff_studio.ui.proposal_window.messagebox'), \
         patch('ruff_studio.ui.dashboard_window.messagebox'), \
         patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showerror'), \
         patch('tkinter.messagebox.showwarning'), \
         patch('tkinter.messagebox.askyesno', return_value=True):
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
    pylint_rule_widget = \
        app.rules_panel.rule_widgets["Pylint: Convention"]['rules']['C0103']
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
    
    dash = ProposalsDashboard(app)
    dash.current_proposal = mock_p
    dash.reject()
    mock_update.assert_called_once_with(
        app.controller.analyzer.conn, "1", "rejected"
    )

def test_select_directory_no_config(app, tmp_path):
    """Tests select_directory when no pyproject.toml exists."""
    with patch('ruff_studio.main.filedialog.askdirectory', return_value=str(tmp_path)):
        with patch('os.path.exists', return_value=False):
            with patch.object(app.controller, 'run_in_thread'):
                app.select_directory()
                assert app.controller.current_directory == str(tmp_path)
                expected_path = os.path.join(str(tmp_path), "pyproject.toml")
                assert app.controller.pyproject_path == expected_path

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
    mock_p2 = {
        "profile": {"rules": {"ruff": {"select": ["F"], "ignore": ["E"]}}}
    }
    
    with patch(
        'ruff_studio.profile_manager.get_built_in_profiles',
        return_value=["p1", "p2"]
    ):
        with patch(
            'ruff_studio.profile_manager.load_profile',
            side_effect=[mock_p1, mock_p2]
        ):
            win = ProfileComparisonWindow(app)
            win.profile1_var.set("p1")
            win.profile2_var.set("p2")
            
            diff = {
                "select_only_in_1": ["E"], "select_only_in_2": ["F"],
                "ignore_only_in_1": ["F"], "ignore_only_in_2": ["E"],
                "common_select": [], "common_ignore": []
            }
            with patch(
                'ruff_studio.profile_manager.compare_profiles',
                return_value=diff
            ):
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
    mock_data = {
        "CAT": {
            "prefix": "C",
            "rules": [
                {
                    "code": "C01", "name": "N", "summary": "S",
                    "fix": False, "status": "stable"
                }
            ]
        }
    }
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
        with patch(
            'ruff_studio.ci_integration.generate_pre_commit_config',
            return_value="yaml"
        ):
            filename_mock = patch(
                'ruff_studio.main.filedialog.asksaveasfilename',
                return_value=str(tmp_path / "pre.yaml")
            )
            with filename_mock:
                with patch('builtins.open', mock_open()) as m:
                    app.generate_pre_commit_config_file()
                    m.assert_called_once_with(str(tmp_path / "pre.yaml"), "w")

def test_update_results_panel(app):
    """Tests that update_results_panel correctly displays violations."""
    from ruff_studio.workspace_analyzer import UnifiedViolationModel
    import customtkinter as ctk
    
    mock_violation = UnifiedViolationModel(
        rule_id="E501", file_path="f.py", line_number=1, column=1, 
        message="Too long", author="Dev"
    )
    
    app.update_results_panel([mock_violation])
    labels = [
        w for w in app.results_frame.winfo_children()
        if isinstance(w, ctk.CTkLabel)
    ]
    violation_labels = [
        label for label in labels
        if "E501" in label.cget("text")
    ]
    assert len(violation_labels) == 1
    assert "Author: Dev" in violation_labels[0].cget("text")

def test_show_rule_info_with_scrape(app):
    """Tests that show_rule_info triggers doc scraping button."""
    rule = MOCK_RULES["Error"]["rules"][0].copy()
    rule["documentation"] = None # Force scrape
    
    # Initialize widget structure for this rule to avoid UI errors
    mock_frame = MagicMock()
    mock_frame.winfo_rooty.return_value = 100
    mock_frame.winfo_height.return_value = 20
    
    app.rules_panel.rule_widgets["Error"] = {
        'prefix': 'E',
        'rules': {
            'E501': {
                'frame': mock_frame,
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

def test_analytics_window_loading(app):
    """Tests that AnalyticsWindow populates correctly."""
    from ruff_studio.ui.analytics_window import AnalyticsWindow
    
    mock_history = [
        ("id1", "2026-03-02 10:00:00", "main", 10),
        ("id2", "2026-03-02 09:00:00", "main", 15)
    ]
    mock_authors = {"Alice": 5, "Bob": 5}
    mock_hotspots = {"E501": 8, "F401": 2}
    
    with patch.object(
        app.controller, 'get_scan_history', return_value=mock_history
    ):
        with patch.object(
            app.controller, 'get_author_stats', return_value=mock_authors
        ):
            with patch.object(
                app.controller, 'get_rule_hotspots', return_value=mock_hotspots
            ):
                win = AnalyticsWindow(app, app.controller)
                app.update_idletasks()
                
                # Check for key labels
                found_latest = False
                found_author = False
                for widget in win.scroll_frame.winfo_children():
                    for sub in widget.winfo_children():
                        if isinstance(sub, ctk.CTkLabel):
                            text = sub.cget("text")
                            if "Latest Scan: 10" in text:
                                found_latest = True
                            if "Alice: 5" in text:
                                found_author = True
                
                assert found_latest
                assert found_author
                win.destroy()

@patch('ruff_studio.git_adapter.push_branch')
@patch('ruff_studio.git_adapter.commit_changes')
@patch('ruff_studio.git_adapter.create_branch')
@patch('ruff_studio.git_adapter.is_repo_clean', return_value=True)
@patch('ruff_studio.proposal_manager.create_proposal')
def test_proposal_window_with_push(
    mock_create, mock_clean, mock_branch, mock_commit, mock_push, app
):
    """Tests the new 'Push branch' workflow in ProposalWindow."""
    from ruff_studio.ui.proposal_window import ProposalWindow
    
    app.controller.current_directory = "/fake"
    app.controller.base_scan_results = []
    
    with patch('ruff_studio.config_manager.read_pyproject_text', return_value=""):
        with patch('ruff_studio.config_manager.write_pyproject'):
            win = ProposalWindow(app, "b", "a", [])
            win.title_entry.insert(0, "Title")
            win.push_var.set(True) # Enable push
            
            # Mock clipboard methods
            win.clipboard_clear = MagicMock()
            win.clipboard_append = MagicMock()
            
            win.create_and_commit()
            
            mock_branch.assert_called_once()
            mock_commit.assert_called_once()
            mock_push.assert_called_once()
            assert mock_create.call_count == 1
            # Verify clipboard was used for impact report
            win.clipboard_append.assert_called_once()
            
            win.destroy()

def test_dashboard_copy_report(app):
    """Tests that ProposalsDashboard correctly copies reports to clipboard."""
    from ruff_studio.ui.dashboard_window import ProposalsDashboard
    
    mock_p = {
        "id": "1", "title": "T", "status": "pending", "author": "A", 
        "created_at": "N", "rationale": "R", "impact_simulation": "[]",
        "config_before": "", "config_after": "", "branch_name": "br"
    }
    
    with patch('ruff_studio.proposal_manager.get_proposals', return_value=[mock_p]):
        dash = ProposalsDashboard(app)
        dash.show_detail(mock_p)
        
        dash.clipboard_clear = MagicMock()
        dash.clipboard_append = MagicMock()
        
        dash.copy_report()
        
        dash.clipboard_append.assert_called_once()
        # Verify the report contains the rationale
        report_text = dash.clipboard_append.call_args[0][0]
        assert "Linting Configuration Proposal" in report_text
        dash.destroy()

def test_e2e_standard_workflow(app, tmp_path):
    """
    End-to-End test representing the primary user journey:
    Open -> Stage -> Simulate -> Proposal.
    """
    from ruff_studio.ui.proposal_window import ProposalWindow
    
    # 1. Setup workspace
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.ruff.lint]\nselect = ['E']\n")
    app.controller.current_directory = str(tmp_path)
    app.controller.pyproject_path = str(pyproject)
    app.controller.pyproject_data = tomlkit.parse(pyproject.read_text())
    
    # 2. Find a rule (F401) and stage it to 'select'
    # We'll use the radio variable directly to simulate the click
    rule_widget = app.rules_panel.rule_widgets["Pyflakes"]['rules']['F401']
    rule_widget['radio_variable'].set("select")
    app.stage_rule_change("F401", "select")
    
    assert "F401" in app.controller.staged_changes
    assert app.controller.staged_changes["F401"] == "select"
    
    # 3. Simulate changes
    # Mock the scan results
    mock_sim_results = [{"code": "F401", "filename": "test.py", 
                         "location": {"row": 1, "column": 1}, "message": "msg"}]
    
    with patch('ruff_studio.ruff_adapter.run_scan_with_config', 
               return_value=mock_sim_results):
        app.toolbar.simulate_button.invoke()
        # Manually put the result in the queue since run_in_thread is mocked
        app.controller.queue.put(("run_simulation", mock_sim_results))
        app.process_queue()
        app.update_idletasks()
        
        # Verify Results panel updated
        label_text = app.results_panel.results_label.cget("text")
        assert "Simulation Results" in label_text
        
    # 4. Apply changes (Open Proposal Window)
    with patch('ruff_studio.ruff_adapter.run_scan_with_config', 
               return_value=mock_sim_results):
        app.toolbar.apply_button.invoke()
        # No queue item needed for apply_changes as it opens the window directly
        app.update_idletasks()
        
        # Find the ProposalWindow (it's a child of app)
        prop_win = None
        for child in app.winfo_children():
            if isinstance(child, ProposalWindow):
                prop_win = child
                break
        
        assert prop_win is not None
        assert "F401" in prop_win.config_after
        prop_win.destroy()

def test_ui_persistence_across_navigation(app):
    """
    Ensures that staged changes are preserved in the UI even when
    navigating between different items.
    """
    # 1. Stage a change in Category A (Pyflakes)
    app.stage_rule_change("F401", "ignore")
    
    # 2. Navigate to Category B (Error)
    app.select_category("Error")
    app.update_idletasks()
    
    # 3. Navigate back to Category A
    app.select_category("Pyflakes")
    app.update_idletasks()
    
    # 4. Verify radio button state is still 'ignore'
    rule_widget = app.rules_panel.rule_widgets["Pyflakes"]['rules']['F401']
    assert rule_widget['radio_variable'].get() == "ignore"

def test_malformed_pyproject_handling(app, tmp_path):
    """
    Tests that the UI handles malformed pyproject.toml without crashing.
    """
    # 1. Create a malformed TOML file
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.ruff.lint\nselect = ['E']\n") # Missing closing bracket
    
    # 2. Select the directory
    # We expect it to show an error message (mocked in our app fixture)
    with patch('ruff_studio.main.filedialog.askdirectory', return_value=str(tmp_path)):
        app.select_directory()
        app.update_idletasks()
        
    # 3. Verify that the app is still functional and didn't crash
    # It should have reverted or cleared the pyproject_data
    assert app.controller.pyproject_data is None or \
           isinstance(app.controller.pyproject_data, MagicMock)
    assert app.toolbar.status_label.cget("text") != "Scanning..."

def test_keyboard_navigation_with_collapsed_categories(app):
    """
    Verifies that keyboard navigation works correctly even when 
    some categories are collapsed (changing the navigable items).
    """
    # 1. Expand first category (Pyflakes) and select first rule
    app.select_category("Pyflakes")
    app.update_idletasks()
    
    initial_index = app.controller.navigable_index
    
    # 2. Simulate 'Down' key to move to first rule
    mock_event = MagicMock()
    mock_event.keysym = "Down"
    app.navigate_items(mock_event)
    
    assert app.controller.navigable_index == initial_index + 1
    assert app.controller.selected_item['type'] == 'rule'
    
    # 3. Collapse the category
    app.toggle_category_rules("Pyflakes")
    app.update_idletasks()

    # 4. Navigate 'Down' again. Since Pyflakes is collapsed, 
    # it should skip all Pyflakes rules and go to the next category.
    # Note: navigable_items are rebuilt on toggle.
    app.navigate_items(mock_event)
    
    # The new selected item should be the next category
    # (Pylint: Convention in our MOCK_RULES after re-syncing to Pyflakes)
    assert app.controller.selected_item['type'] == 'category'
    assert app.controller.selected_item['name'] == 'Pylint: Convention'
