import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from ruff_studio.main import App
from ruff_studio.controller import StudioController
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
            {"code": "F401", "name": "UnusedImport", "summary": "S", "status": "stable"},
        ],
    }
}

@pytest.fixture
def app():
    """
    Fully mocked App for business logic testing without Tcl/Tk.
    """
    with (
        patch("customtkinter.CTk", return_value=MagicMock()),
        patch("customtkinter.CTkFrame", return_value=MagicMock()),
        patch("customtkinter.CTkScrollableFrame", return_value=MagicMock()),
        patch("customtkinter.CTkButton", return_value=MagicMock()),
        patch("customtkinter.CTkLabel", return_value=MagicMock()),
        patch("customtkinter.CTkEntry", return_value=MagicMock()),
        patch("customtkinter.CTkTextbox", return_value=MagicMock()),
        patch("customtkinter.CTkRadioButton", return_value=MagicMock()),
        patch("customtkinter.CTkCheckBox", return_value=MagicMock()),
        patch("customtkinter.CTkFont", return_value=MagicMock()),
        patch("ruff_studio.main.messagebox"),
        patch("ruff_studio.main.filedialog"),
        patch("tkinter.messagebox.showinfo"),
        patch("tkinter.messagebox.showerror"),
        patch("tkinter.messagebox.showwarning"),
        patch("tkinter.messagebox.askyesno", return_value=True),
        patch("tkinter.filedialog.askdirectory", return_value="/fake/dir"),
        patch("tkinter.filedialog.asksaveasfilename", return_value="/fake/file"),
        patch.object(App, "run_in_thread", return_value=None),
        patch.object(StudioController, "run_in_thread", return_value=None),
    ):
        app_instance = App(headless=True)
        
        # Manually setup what we need
        app_instance.controller.all_rules = MOCK_RULES
        app_instance.controller.pyproject_data = tomlkit.parse("dummy = true")
        app_instance.controller.current_directory = "/fake"
        
        # Mock panels
        app_instance.rules_view = MagicMock()
        app_instance.rules_view.rules_panel = MagicMock()
        app_instance.rules_view.toolbar = MagicMock()
        
        yield app_instance

def test_apply_profile_logic(app):
    """Tests that apply_profile correctly stages changes in the controller."""
    mock_profile = {
        "profile": {
            "rules": {
                "ruff": {"select": ["E"], "ignore": ["F"]}
            }
        }
    }
    
    # We need to mock the rule_widgets structure that apply_profile iterates over
    app.rules_panel.rule_widgets = {
        "Error": {"rules": {"E501": {}}},
        "Pyflakes": {"rules": {"F401": {}}}
    }

    with patch('ruff_studio.profile_manager.load_profile', return_value=mock_profile):
        app.apply_profile("test-profile")

    # Verify staged changes in controller
    assert app.controller.staged_changes.get("E501") == "select"
    assert app.controller.staged_changes.get("F401") == "ignore"

def test_stage_rule_change(app):
    app.stage_rule_change("E501", "select")
    assert app.controller.staged_changes["E501"] == "select"
    app.rules_panel.update_panel.assert_called()

def test_stage_category_change(app):
    app.stage_category_change("F", "ignore")
    assert app.controller.staged_changes["F"] == "ignore"
    app.rules_panel.update_panel.assert_called()

def test_switch_view(app):
    app.views = {"v1": MagicMock()}
    app.switch_view("v1")
    app.views["v1"].grid.assert_called()

def test_process_queue_discover(app):
    app.controller.queue.put(("discover_rules", MOCK_RULES))
    app.process_queue()
    assert app.controller.all_rules == MOCK_RULES
    app.rules_panel.populate.assert_called()
