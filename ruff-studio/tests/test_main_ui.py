import pytest
from ruff_studio.main import App
from unittest.mock import patch, MagicMock
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
        app_instance = App()

    # Manually set the rules data, bypassing the threaded discovery
    app_instance.all_rules = MOCK_RULES

    # Manually call the UI population method to create the widgets
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
    toggle_button = app.rule_widgets[category_name]['toggle_button']
    rules_container = app.rule_widgets[category_name]['rules_container']

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
    # The button text should update to indicate it can be expanded (e.g., "►").
    assert rules_container.winfo_viewable() == 0
    assert toggle_button.cget("text") == "►"

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
    for item in app.navigable_items:
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
    target_rule = app.navigable_items[1]['data']
    target_cat = app.navigable_items[1]['category_name']
    app.show_rule_info(target_rule, target_cat)
    app.update_idletasks()
    assert app.selected_item['data']['code'] == 'E501'

    # --- 3. Navigate Up to Category ---
    # Pressing Up from the first rule should select its category header.
    app.navigate_items(up_event)
    app.update_idletasks()
    assert app.selected_item['type'] == 'category'
    assert app.selected_item['name'] == 'Error'

    # --- 4. Boundary Check (Top) ---
    # Pressing Up again should not change the selection.
    app.navigate_items(up_event)
    app.update_idletasks()
    assert app.selected_item['name'] == 'Error'

    # --- 5. Navigate Down to First Rule ---
    app.navigate_items(down_event)
    app.update_idletasks()
    assert app.selected_item['data']['code'] == 'E501'

    # --- 6. Navigate Down to Next Category ---
    # Pressing Down from the last rule in a category should select the next category.
    app.navigate_items(down_event)
    app.update_idletasks()
    assert app.selected_item['type'] == 'category'
    assert app.selected_item['name'] == 'Pyflakes'

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
    with patch.object(app, '_run_full_scan_worker', return_value=None):
        app.select_directory(str(tmp_path))
    app.update_idletasks()

    # Check that the C0103 rule is correctly identified as "ignore"
    pylint_rule_widget = app.rule_widgets["Pylint: Convention"]['rules']['C0103']
    assert pylint_rule_widget['radio_variable'].get() == "ignore"

    # Check that a ruff rule is "default"
    ruff_rule_widget = app.rule_widgets["Pyflakes"]['rules']['F401']
    assert ruff_rule_widget['radio_variable'].get() == "default"

    # --- 3. Stage a change: Enable the pylint rule ---
    # Simulate clicking the "default" radio button for C0103
    pylint_rule_widget['radio_variable'].set("default")
    app.stage_rule_change("C0103", "default")
    app.update_idletasks()

    # The radio button should now be "default"
    assert pylint_rule_widget['radio_variable'].get() == "default"
    assert "C0103" in app.staged_changes

    # --- 4. Apply the changes ---
    # This should write the changes back to the pyproject.toml
    # Disable proposal window for tests to apply immediately
    with patch.object(app, '_run_full_scan_worker', return_value=None):
        app.apply_changes(show_proposal_window=False)
    app.update_idletasks()

    # --- 5. Verify the pyproject.toml was updated correctly ---
    updated_data = tomlkit.parse(pyproject_path.read_text())

    # The `disable` list should now be empty or not present
    pylint_config = updated_data.get("tool", {}).get("pylint", {})
    assert "C0103" not in pylint_config.get("disable", [])
