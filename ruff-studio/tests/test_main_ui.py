import pytest
from src.ruff_studio.main import App
from unittest.mock import patch, MagicMock

MOCK_RULES = {
    "Pyflakes": {
        "prefix": "F",
        "rules": [
            {"code": "F401", "name": "UnusedImport", "summary": "An imported module is not used.", "fix": True, "status": "stable"},
            {"code": "F841", "name": "UnusedLocalVariable", "summary": "A local variable is assigned to but never used.", "fix": False, "status": "stable"},
        ],
    },
    "pycodestyle": {
        "prefix": "E",
        "rules": [
            {"code": "E501", "name": "LineTooLong", "summary": "Line too long.", "fix": False, "status": "stable"},
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
    # The navigable list should contain categories and their rules in order.
    # Mock data is sorted by category name ("Pyflakes", "pycodestyle"),
    # and rules within are sorted by code ("F401", "F841").
    nav_item_reprs = []
    for item in app.navigable_items:
        if item['type'] == 'category':
            nav_item_reprs.append(f"CAT:{item['name']}")
        else:
            nav_item_reprs.append(f"RULE:{item['data']['code']}")

    expected_order = [
        "CAT:Pyflakes", "RULE:F401", "RULE:F841",
        "CAT:pycodestyle", "RULE:E501"
    ]
    assert nav_item_reprs == expected_order

    up_event = MagicMock()
    up_event.keysym = "Up"
    down_event = MagicMock()
    down_event.keysym = "Down"

    # --- 2. Start Selection ---
    # Start by selecting the first rule, F401.
    app.show_rule_info(app.navigable_items[1]['data'], app.navigable_items[1]['category_name'])
    app.update_idletasks()
    assert app.selected_item['data']['code'] == 'F401'

    # --- 3. Navigate Up to Category ---
    # Pressing Up from the first rule should select its category header.
    app.navigate_items(up_event)
    app.update_idletasks()
    assert app.selected_item['type'] == 'category'
    assert app.selected_item['name'] == 'Pyflakes'

    # --- 4. Boundary Check (Top) ---
    # Pressing Up again should not change the selection.
    app.navigate_items(up_event)
    app.update_idletasks()
    assert app.selected_item['name'] == 'Pyflakes'

    # --- 5. Navigate Down to First Rule ---
    app.navigate_items(down_event)
    app.update_idletasks()
    assert app.selected_item['data']['code'] == 'F401'

    # --- 6. Navigate Down to Second Rule ---
    app.navigate_items(down_event)
    app.update_idletasks()
    assert app.selected_item['data']['code'] == 'F841'

    # --- 7. Navigate Down to Next Category ---
    # Pressing Down from the last rule in a category should select the next category.
    app.navigate_items(down_event)
    app.update_idletasks()
    assert app.selected_item['type'] == 'category'
    assert app.selected_item['name'] == 'pycodestyle'

    # --- 8. Navigate Down to Rule in New Category ---
    app.navigate_items(down_event)
    app.update_idletasks()
    assert app.selected_item['data']['code'] == 'E501'

    # --- 9. Boundary Check (Bottom) ---
    # Pressing Down at the very end should not change the selection.
    app.navigate_items(down_event)
    app.update_idletasks()
    assert app.selected_item['data']['code'] == 'E501'

    # --- 10. Navigate Up to Category from Rule ---
    app.navigate_items(up_event)
    app.update_idletasks()
    assert app.selected_item['type'] == 'category'
    assert app.selected_item['name'] == 'pycodestyle'
