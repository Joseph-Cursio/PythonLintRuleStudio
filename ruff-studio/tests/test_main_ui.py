import pytest
import os
import customtkinter as ctk
from ruff_studio.main import App
from ruff_studio.controller import StudioController
from unittest.mock import patch, MagicMock, ANY
import tomlkit

# MOCK_RULES is now intentionally non-alphabetical to test display order.
MOCK_RULES = {
    "Error": {
        "prefix": "E",
        "rules": [
            {
                "code": "E501",
                "name": "LineTooLong",
                "summary": "Line too long.",
                "fix": False,
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
            {
                "code": "F841",
                "name": "UnusedLocalVariable",
                "summary": "A local variable is assigned but never used.",
                "fix": False,
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
    Pytest fixture to create a fully initialized App instance for UI testing.
    Note: This fixture requires a virtual display (like xvfb) to run.
    """
    with (
        patch.object(App, "run_in_thread", return_value=None),
        patch.object(StudioController, "run_in_thread", return_value=None),
        patch.object(StudioController, "get_scan_history", return_value=[]),
        patch.object(StudioController, "get_author_stats", return_value={}),
        patch.object(StudioController, "get_rule_hotspots", return_value={}),
        patch("ruff_studio.proposal_manager.get_proposals", return_value=[]),
        patch("ruff_studio.main.messagebox"),
        patch("ruff_studio.ui.proposal_window.messagebox"),
        patch("ruff_studio.ui.dashboard_window.messagebox"),
        patch("tkinter.messagebox.showinfo"),
        patch("tkinter.messagebox.showerror"),
        patch("tkinter.messagebox.showwarning"),
        patch("tkinter.messagebox.askyesno", return_value=True),
    ):
        app_instance = App(headless=True)

        app_instance.controller.all_rules = MOCK_RULES

        app_instance.controller.current_directory = "/fake/dir"
        app_instance.controller.pyproject_path = "/fake/dir/pyproject.toml"
        app_instance.controller.pyproject_data = tomlkit.parse("dummy = true")
        app_instance.controller.analyzer.conn = MagicMock()

        app_instance.populate_rules_initial()
        app_instance.update_idletasks()

        yield app_instance
        app_instance.destroy()


def test_toggle_category_rules(app):
    category_name = "Pyflakes"
    # Use is_expanded instead of winfo_viewable for more reliable testing
    assert app.rules_panel.rule_widgets[category_name]["is_expanded"] is True

    app.toggle_category_rules(category_name)
    assert app.rules_panel.rule_widgets[category_name]["is_expanded"] is False

    app.toggle_category_rules(category_name)
    assert app.rules_panel.rule_widgets[category_name]["is_expanded"] is True


def test_visual_keyboard_navigation(app):
    app.select_category("Pyflakes")
    initial_index = app.controller.navigable_index

    down_event = MagicMock(keysym="Down")
    app.navigate_items(down_event)

    assert app.controller.navigable_index == initial_index + 1
    assert app.controller.selected_item["type"] == "rule"
    assert app.controller.selected_item["data"]["code"] == "F401"


def test_pylint_configuration_workflow(app):
    """Tests toggling Pylint rules and ensuring they stay separate from Ruff."""
    rule_code = "C0103"
    app.stage_rule_change(rule_code, "select")
    assert app.controller.staged_changes[rule_code] == "select"

    ruff_cfg, pylint_cfg = app.controller.get_effective_configs()
    assert rule_code in pylint_cfg["enable"]
    assert rule_code not in ruff_cfg["select"]


def test_apply_profile(app):
    mock_profile = {
        "profile": {
            "name": "test-profile",
            "rules": {
                "ruff": {"select": ["E"], "ignore": ["F"]},
                "pylint": {"enable": ["C0103"]},
            },
        }
    }

    with patch("ruff_studio.profile_manager.load_profile", return_value=mock_profile):
        app.apply_profile("test-profile")

    # Only E501 starts with E, so it should be select. F rules should be ignore.
    assert app.controller.staged_changes.get("E501") == "select"
    assert app.controller.staged_changes.get("F401") == "ignore"
    assert app.controller.staged_changes.get("F841") == "ignore"


def test_stage_category_change(app):
    app.stage_category_change("F", "select")
    assert app.controller.staged_changes["F"] == "select"

    ruff_cfg, _ = app.controller.get_effective_configs()
    assert "F" in ruff_cfg["select"]


def test_proposal_window_logic(app, tmp_path):
    from ruff_studio.ui.proposal_window import ProposalWindow

    impact = [{"code": "E501"}]
    app.controller.current_directory = str(tmp_path)
    with patch("ruff_studio.git_adapter.is_repo_clean", return_value=True):
        with patch("ruff_studio.git_adapter.create_branch", return_value=True):
            with patch("ruff_studio.git_adapter.commit_changes", return_value=True):
                win = ProposalWindow(app, "config before", "config after", impact)
                win.title_entry.insert(0, "Fix E501")
                win.rationale_text.insert("1.0", "Rationale")
                with patch(
                    "ruff_studio.proposal_manager.create_proposal"
                ) as mock_create:
                    with patch.object(
                        app, "apply_changes"
                    ):  # Mock apply_changes to avoid file IO
                        win.create_and_commit()
                        mock_create.assert_called_once()


@patch("ruff_studio.proposal_manager.update_proposal_status", return_value=True)
@patch("ruff_studio.proposal_manager.get_proposals")
def test_proposals_dashboard(mock_get, mock_update, app):
    mock_p = {
        "id": "123",
        "title": "P1",
        "status": "pending",
        "author": "A",
        "created_at": "now",
        "rationale": "R",
        "impact_simulation": "[]",
        "config_before": "",
        "config_after": "",
    }
    mock_get.return_value = [mock_p]
    app.switch_view("proposals")
    app.proposals_view.refresh()
    app.proposals_view.show_detail(mock_p)
    app.proposals_view.approve()
    mock_update.assert_called_once_with(ANY, "123", "approved")


@patch("ruff_studio.proposal_manager.update_proposal_status", return_value=True)
@patch("ruff_studio.proposal_manager.get_proposals")
def test_proposals_dashboard_reject(mock_get, mock_update, app):
    mock_p = {
        "id": "1",
        "title": "T",
        "status": "pending",
        "author": "A",
        "created_at": "N",
        "rationale": "R",
        "impact_simulation": "{}",
        "config_before": "",
        "config_after": "",
    }
    mock_get.return_value = [mock_p]
    app.switch_view("proposals")
    app.proposals_view.refresh()
    app.proposals_view.current_proposal = mock_p
    app.proposals_view.reject()
    mock_update.assert_called_once_with(ANY, "1", "rejected")


def test_select_directory_no_config(app, tmp_path):
    with patch("ruff_studio.main.filedialog.askdirectory", return_value=str(tmp_path)):
        with patch("os.path.exists", return_value=False):
            app.select_directory()
            assert app.controller.current_directory == str(tmp_path)


def test_ui_initialization(app):
    assert app.sidebar is not None
    assert app.rules_view is not None
    assert app.analytics_view is not None
    assert app.proposals_view is not None


def test_profile_comparison_logic(app):
    from ruff_studio.ui.comparison_window import ProfileComparisonWindow

    mock_p1 = {"profile": {"rules": {"ruff": {"select": ["E"], "ignore": ["F"]}}}}
    mock_p2 = {"profile": {"rules": {"ruff": {"select": ["F"], "ignore": ["E"]}}}}
    with patch(
        "ruff_studio.profile_manager.get_built_in_profiles", return_value=["p1", "p2"]
    ):
        with patch(
            "ruff_studio.profile_manager.load_profile", side_effect=[mock_p1, mock_p2]
        ):
            win = ProfileComparisonWindow(app)
            win.profile1_var.set("p1")
            win.profile2_var.set("p2")
            diff = {
                "select_only_in_1": ["E"],
                "select_only_in_2": ["F"],
                "ignore_only_in_1": ["F"],
                "ignore_only_in_2": ["E"],
                "common_select": [],
                "common_ignore": [],
            }
            with patch(
                "ruff_studio.profile_manager.compare_profiles", return_value=diff
            ):
                win.do_comparison()
                assert "Only in 'p1':" in win.results_textbox.get("1.0", "end")


@patch("ruff_studio.git_adapter.commit_changes")
@patch("ruff_studio.git_adapter.create_branch", return_value=True)
@patch("ruff_studio.git_adapter.is_repo_clean", return_value=True)
@patch("ruff_studio.proposal_manager.create_proposal")
def test_proposal_window_commit(
    mock_create, mock_clean, mock_branch, mock_commit, app, tmp_path
):
    from ruff_studio.ui.proposal_window import ProposalWindow

    app.controller.current_directory = str(tmp_path)
    with patch("ruff_studio.config_manager.read_pyproject_text", return_value=""):
        with patch("ruff_studio.config_manager.write_pyproject"):
            with patch.object(app, "apply_changes"):
                win = ProposalWindow(app, "b", "a", {})
                win.title_entry.insert(0, "Title")
                win.create_and_commit()
                mock_branch.assert_called_once()
                mock_commit.assert_called_once()


def test_discover_rules_worker(app):
    with patch("ruff_studio.ruff_adapter.discover_rules", return_value={"R": {}}):
        app.controller.discover_rules_worker("cmd")
        assert app.controller.queue.get()[0] == "cmd"


def test_run_full_scan_worker(app):
    with patch(
        "ruff_studio.workspace_analyzer.WorkspaceAnalyzer.run_full_scan",
        return_value=[],
    ):
        app.controller.run_full_scan_worker("cmd", "/dir")
        assert app.controller.queue.get()[0] == "cmd"


def test_process_queue_discover(app):
    app.controller.queue.put(("discover_rules", MOCK_RULES))
    app.process_queue()
    assert "Pyflakes" in app.rules_panel.rule_widgets


def test_apply_changes_with_proposal(app, tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("dummy=1")
    app.controller.pyproject_path = str(pyproject)
    app.controller.pyproject_data = tomlkit.parse("dummy=1")
    with patch("ruff_studio.ruff_adapter.run_scan_with_config", return_value=[]):
        with patch("ruff_studio.ui.proposal_window.ProposalWindow"):
            app.apply_changes(show_proposal_window=True)


def test_apply_changes_direct(app, tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("dummy=1")
    app.controller.pyproject_path = str(pyproject)
    app.controller.pyproject_data = tomlkit.parse("dummy=1")
    with patch("ruff_studio.config_manager.write_pyproject") as mock_write:
        with patch.object(app.controller, "run_in_thread"):
            app.apply_changes(show_proposal_window=False)
            mock_write.assert_called_once()


def test_open_windows(app):
    with patch("ruff_studio.ui.comparison_window.ProfileComparisonWindow"):
        app.open_comparison_window()
    app.open_proposals_dashboard()
    app.open_analytics()


def test_generate_pre_commit(app, tmp_path):
    app.controller.current_directory = str(tmp_path)
    with patch("ruff_studio.ruff_adapter.get_ruff_version", return_value="0.1.0"):
        with patch(
            "ruff_studio.main.filedialog.asksaveasfilename",
            return_value=str(tmp_path / "pre.yaml"),
        ):
            app.generate_pre_commit_config_file()
            assert os.path.exists(tmp_path / "pre.yaml")


def test_update_results_panel(app):
    from ruff_studio.workspace_analyzer import UnifiedViolationModel

    mock_violation = UnifiedViolationModel(
        rule_id="E501",
        file_path="f.py",
        line_number=1,
        column=1,
        message="m",
        author="D",
    )
    app.update_results_panel([mock_violation])
    found = any(
        "E501" in str(w.cget("text"))
        for w in app.results_panel.winfo_children()
        if isinstance(w, ctk.CTkLabel)
    )
    assert found


def test_show_rule_info_with_scrape(app):
    rule = MOCK_RULES["Error"]["rules"][0].copy()
    rule["documentation"] = None
    app.show_rule_info(rule, "Error")
    found = any(
        "Fetch" in w.cget("text")
        for w in app.info_panel.winfo_children()
        if isinstance(w, ctk.CTkButton)
    )
    assert found


def test_analytics_window_loading(app):
    mock_history = [("id1", "2026-03-02 10:00:00", "main", 10)]
    with patch.object(app.controller, "get_scan_history", return_value=mock_history):
        with patch.object(
            app.controller, "get_author_stats", return_value={"Alice": 5}
        ):
            app.switch_view("analytics")
            app.analytics_view.refresh()
            found = False
            for widget in app.analytics_view.scroll_frame.winfo_children():
                for sub in widget.winfo_children():
                    if isinstance(sub, ctk.CTkLabel) and "Alice: 5" in sub.cget("text"):
                        found = True
            assert found


def test_proposal_window_with_push(app, tmp_path):
    from ruff_studio.ui.proposal_window import ProposalWindow

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("dummy=1")
    app.controller.current_directory = str(tmp_path)
    app.controller.pyproject_path = str(pyproject)
    app.controller.pyproject_data = tomlkit.parse("dummy=1")
    with patch("ruff_studio.git_adapter.is_repo_clean", return_value=True):
        with patch("ruff_studio.git_adapter.push_branch"):
            with patch("ruff_studio.git_adapter.commit_changes"):
                with patch("ruff_studio.git_adapter.create_branch", return_value=True):
                    with patch.object(app, "apply_changes"):
                        win = ProposalWindow(app, "b", "a", [])
                        win.title_entry.insert(0, "T")
                        win.push_var.set(True)
                        win.create_and_commit()


def test_dashboard_copy_report(app):
    mock_p = {
        "id": "1",
        "title": "T",
        "status": "pending",
        "author": "A",
        "created_at": "N",
        "rationale": "R",
        "impact_simulation": "[]",
        "config_before": "",
        "config_after": "",
        "branch_name": "br",
    }
    with patch("ruff_studio.proposal_manager.get_proposals", return_value=[mock_p]):
        app.switch_view("proposals")
        app.proposals_view.refresh()
        app.proposals_view.show_detail(mock_p)
        app.proposals_view.clipboard_clear = MagicMock()
        app.proposals_view.clipboard_append = MagicMock()
        app.proposals_view.copy_report()
        app.proposals_view.clipboard_append.assert_called_once()


def test_resize_panels(app):
    rv = app.rules_view
    w0 = rv.grid_columnconfigure(0)["weight"]
    app.start_resize(MagicMock(x_root=100), 0)
    app.do_resize(MagicMock(x_root=150))
    assert rv.grid_columnconfigure(0)["weight"] > w0


def test_keyboard_navigation_complex(app):
    app.select_category("Error")
    down = MagicMock(keysym="Down")
    app.navigate_items(down)
    assert app.controller.selected_item["data"]["code"] == "E501"


def test_process_queue_error_handling(app):
    with patch("ruff_studio.main.messagebox.showerror") as mock_error:
        app.controller.queue.put(("error", "Something went wrong"))
        app.process_queue()
        mock_error.assert_called_once()


def test_rule_status_tags_and_tooltips(app):
    preview_rule = {
        "code": "P1",
        "name": "PR",
        "summary": "S",
        "fix": False,
        "status": "preview",
    }
    app.controller.all_rules = {"P": {"prefix": "P", "rules": [preview_rule]}}
    app.populate_rules_initial()
    found = any(
        "preview" in w.cget("text")
        for cat in app.rules_panel.rule_widgets.values()
        for rule in cat["rules"].values()
        for w in rule["frame"].winfo_children()
        if isinstance(w, ctk.CTkLabel)
    )
    assert found


def test_navigable_items_resync_on_collapse(app):
    app.show_rule_info(MOCK_RULES["Pyflakes"]["rules"][0], "Pyflakes")
    app.toggle_category_rules("Pyflakes")
    assert app.controller.selected_item["type"] == "category"
