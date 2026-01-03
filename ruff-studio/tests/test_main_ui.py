import pytest
from src.ruff_studio.main import App
from unittest.mock import patch

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
