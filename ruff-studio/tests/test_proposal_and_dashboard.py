"""
Tests for ProposalWindow (proposal_window.py) and ProposalsView (dashboard_window.py).

Coverage targets:
  - proposal_window.py: currently ~10%; these tests drive it well above 80%.
  - dashboard_window.py: currently ~46%; these tests cover the previously untested paths.

Fixture pattern mirrors test_main_ui.py and test_ui_panels.py: a real App instance
with all blocking background tasks, dialogs, and DB calls mocked out.
"""

import pytest
import customtkinter as ctk
import tomlkit
from unittest.mock import patch, MagicMock

from ruff_studio.main import App
from ruff_studio.controller import StudioController
from ruff_studio.ui.proposal_window import ProposalWindow


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

MOCK_RULES = {
    "Error": {
        "prefix": "E",
        "rules": [
            {"code": "E501", "name": "LineTooLong", "summary": "S", "status": "stable"},
        ],
    },
}

_SAMPLE_PROPOSAL = {
    "id": "1",
    "title": "My Proposal",
    "status": "pending",
    "author": "Me",
    "created_at": "2024-01-01",
    "branch_name": None,
    "rationale": "R",
    "config_before": "B",
    "config_after": "A",
    "impact_simulation": "[]",
}


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """
    Creates a real App instance with all blocking background tasks mocked.
    Mirrors the fixture in test_main_ui.py so tests are consistent.
    """
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
        app_instance = App(headless=False)
        app_instance.controller.all_rules = MOCK_RULES
        app_instance.controller.current_directory = "/fake/dir"
        app_instance.controller.pyproject_path = "/fake/dir/pyproject.toml"
        app_instance.controller.pyproject_data = tomlkit.parse("dummy = true")
        app_instance.controller.analyzer.conn = MagicMock()
        app_instance.populate_rules_initial()
        app_instance.update_idletasks()
        yield app_instance
        app_instance.destroy()


# ---------------------------------------------------------------------------
# ProposalWindow tests
# ---------------------------------------------------------------------------

class TestProposalWindow:
    """Tests for ruff_studio.ui.proposal_window.ProposalWindow."""

    # ------------------------------------------------------------------
    # Test 1: basic construction
    # ------------------------------------------------------------------

    def test_proposal_window_opens(self, app):
        """
        ProposalWindow can be constructed and exposes the expected UI attributes.
        """
        win = None
        try:
            win = ProposalWindow(app, "before", "after", [])
            app.update_idletasks()

            assert hasattr(win, "title_entry"), "ProposalWindow must expose title_entry"
            assert hasattr(win, "create_btn"), "ProposalWindow must expose create_btn"
        finally:
            if win is not None:
                win.destroy()

    # ------------------------------------------------------------------
    # Test 2: _get_data with empty title shows warning
    # ------------------------------------------------------------------

    def test_get_data_empty_title_shows_warning(self, app):
        """
        _get_data() with no title text calls showwarning and returns (None, None).
        """
        win = None
        try:
            win = ProposalWindow(app, "before", "after", [])
            app.update_idletasks()

            # No title entered — title_entry is empty by default
            with patch("ruff_studio.ui.proposal_window.messagebox") as mock_mb:
                result = win._get_data()

            mock_mb.showwarning.assert_called_once()
            assert result == (None, None)
        finally:
            if win is not None:
                win.destroy()

    # ------------------------------------------------------------------
    # Test 3: _get_data with valid title returns data
    # ------------------------------------------------------------------

    def test_get_data_valid_title_returns_data(self, app):
        """
        _get_data() returns the (title, rationale) tuple when both fields are filled.
        """
        win = None
        try:
            win = ProposalWindow(app, "before", "after", [])
            app.update_idletasks()

            win.title_entry.insert(0, "My Title")
            win.rationale_text.insert("1.0", "My Rationale")

            title, rationale = win._get_data()

            assert title == "My Title"
            assert rationale == "My Rationale"
        finally:
            if win is not None:
                win.destroy()

    # ------------------------------------------------------------------
    # Test 4: create_only returns early when no title is provided
    # ------------------------------------------------------------------

    def test_create_only_no_title_returns_early(self, app):
        """
        create_only() must not call proposal_manager.create_proposal when
        the title field is empty.
        """
        win = None
        try:
            win = ProposalWindow(app, "before", "after", [])
            app.update_idletasks()

            with (
                patch("ruff_studio.ui.proposal_window.messagebox"),
                patch("ruff_studio.ui.proposal_window.proposal_manager") as mock_pm,
            ):
                win.create_only()

            mock_pm.create_proposal.assert_not_called()
        finally:
            if win is not None:
                win.destroy()

    # ------------------------------------------------------------------
    # Test 5: create_only with a valid title calls create_proposal
    # ------------------------------------------------------------------

    def test_create_only_with_title_creates_proposal(self, app):
        """
        create_only() calls proposal_manager.create_proposal exactly once
        when a title has been provided.
        """
        win = None
        try:
            win = ProposalWindow(app, "before", "after", [])
            app.update_idletasks()

            win.title_entry.insert(0, "New Proposal")

            with (
                patch("ruff_studio.ui.proposal_window.messagebox") as mock_mb,
                patch(
                    "ruff_studio.ui.proposal_window.proposal_manager"
                ) as mock_pm,
            ):
                mock_pm.create_proposal.return_value = "fake-uuid"
                win.create_only()

            mock_pm.create_proposal.assert_called_once()
            mock_mb.showinfo.assert_called_once()
        finally:
            # win.destroy() is already called by create_only() on success;
            # calling it again on a destroyed toplevel is harmless but we
            # guard to be safe.
            try:
                if win is not None:
                    win.destroy()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Test 6: create_and_commit with a clean repo succeeds
    # ------------------------------------------------------------------

    def test_create_and_commit_clean_repo_success(self, app):
        """
        create_and_commit() creates a branch and commits when the repo is clean.
        """
        win = None
        try:
            win = ProposalWindow(app, "before", "after", [])
            app.update_idletasks()

            win.title_entry.insert(0, "Clean Repo Proposal")

            with (
                patch("ruff_studio.ui.proposal_window.messagebox") as mock_mb,
                patch(
                    "ruff_studio.ui.proposal_window.proposal_manager"
                ) as mock_pm,
                patch(
                    "ruff_studio.ui.proposal_window.git_adapter"
                ) as mock_git,
                patch.object(app, "apply_changes"),
            ):
                mock_git.is_repo_clean.return_value = True
                mock_git.create_branch.return_value = True
                mock_pm.create_proposal.return_value = "fake-id"
                mock_pm.generate_impact_report.return_value = "report text"

                win.create_and_commit()

            mock_git.create_branch.assert_called_once()
            mock_git.commit_changes.assert_called_once()
            mock_mb.showinfo.assert_called_once()
        finally:
            try:
                if win is not None:
                    win.destroy()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Test 7: create_and_commit with dirty repo and user cancelling
    # ------------------------------------------------------------------

    def test_create_and_commit_dirty_repo_user_cancels(self, app):
        """
        create_and_commit() aborts branch creation when the repo is dirty and
        the user answers No to the confirmation dialog.
        """
        win = None
        try:
            win = ProposalWindow(app, "before", "after", [])
            app.update_idletasks()

            win.title_entry.insert(0, "Dirty Repo Proposal")

            with (
                patch("ruff_studio.ui.proposal_window.messagebox") as mock_mb,
                patch(
                    "ruff_studio.ui.proposal_window.git_adapter"
                ) as mock_git,
            ):
                mock_git.is_repo_clean.return_value = False
                mock_mb.askyesno.return_value = False

                win.create_and_commit()

            mock_git.create_branch.assert_not_called()
        finally:
            if win is not None:
                win.destroy()

    # ------------------------------------------------------------------
    # Test 8: create_and_commit when branch creation fails
    # ------------------------------------------------------------------

    def test_create_and_commit_branch_creation_fails(self, app):
        """
        create_and_commit() calls messagebox.showerror when create_branch
        returns False.
        """
        win = None
        try:
            win = ProposalWindow(app, "before", "after", [])
            app.update_idletasks()

            win.title_entry.insert(0, "Branch Fail Proposal")

            with (
                patch("ruff_studio.ui.proposal_window.messagebox") as mock_mb,
                patch(
                    "ruff_studio.ui.proposal_window.proposal_manager"
                ) as mock_pm,
                patch(
                    "ruff_studio.ui.proposal_window.git_adapter"
                ) as mock_git,
            ):
                mock_git.is_repo_clean.return_value = True
                mock_git.create_branch.return_value = False
                mock_pm.generate_impact_report.return_value = "report"

                win.create_and_commit()

            mock_mb.showerror.assert_called_once()
        finally:
            if win is not None:
                win.destroy()


# ---------------------------------------------------------------------------
# ProposalsView (dashboard) tests
# ---------------------------------------------------------------------------

class TestProposalsView:
    """Tests for ruff_studio.ui.dashboard_window.ProposalsView."""

    # ------------------------------------------------------------------
    # Test 9: load_proposals creates a button per proposal
    # ------------------------------------------------------------------

    def test_proposals_view_load_with_proposals(self, app):
        """
        load_proposals() creates a CTkButton in list_frame for each proposal
        returned by proposal_manager.get_proposals. The button text includes
        the proposal title.
        """
        proposals = [dict(_SAMPLE_PROPOSAL)]

        with patch(
            "ruff_studio.ui.dashboard_window.proposal_manager.get_proposals",
            return_value=proposals,
        ):
            app.proposals_view.load_proposals()

        app.update_idletasks()

        buttons = [
            w
            for w in app.proposals_view.list_frame.winfo_children()
            if isinstance(w, ctk.CTkButton)
        ]
        assert len(buttons) >= 1, "Expected at least one CTkButton in list_frame"
        button_texts = [b.cget("text") for b in buttons]
        assert any("My Proposal" in t for t in button_texts), (
            f"Expected button containing 'My Proposal', got: {button_texts}"
        )

    # ------------------------------------------------------------------
    # Test 10: show_detail with a pending proposal packs approve/reject btns
    # ------------------------------------------------------------------

    def test_proposals_view_show_detail_pending(self, app):
        """
        show_detail() for a pending proposal updates detail_title and packs
        the approve and reject buttons.
        """
        app.proposals_view.show_detail(dict(_SAMPLE_PROPOSAL))
        app.update_idletasks()

        assert app.proposals_view.detail_title.cget("text") == "My Proposal"
        assert app.proposals_view.approve_btn.winfo_manager() == "pack", (
            "approve_btn must be packed for a pending proposal"
        )

    # ------------------------------------------------------------------
    # Test 11: show_detail with an approved proposal hides approve/reject btns
    # ------------------------------------------------------------------

    def test_proposals_view_show_detail_approved(self, app):
        """
        show_detail() for an approved proposal removes the approve and reject
        buttons from the layout.
        """
        approved = dict(_SAMPLE_PROPOSAL)
        approved["status"] = "approved"

        app.proposals_view.show_detail(approved)
        app.update_idletasks()

        assert app.proposals_view.approve_btn.winfo_manager() == "", (
            "approve_btn must NOT be packed for an already-approved proposal"
        )

    # ------------------------------------------------------------------
    # Test 12: show_detail with a branch name includes it in detail_info
    # ------------------------------------------------------------------

    def test_proposals_view_show_detail_with_branch(self, app):
        """
        When a proposal has a branch_name, show_detail() includes that name
        in the detail_info label text.
        """
        proposal_with_branch = dict(_SAMPLE_PROPOSAL)
        proposal_with_branch["branch_name"] = "feature/test"

        app.proposals_view.show_detail(proposal_with_branch)
        app.update_idletasks()

        info_text = app.proposals_view.detail_info.cget("text")
        assert "feature/test" in info_text, (
            f"Expected 'feature/test' in detail_info text, got: {info_text!r}"
        )

    # ------------------------------------------------------------------
    # Test 13: copy_report does nothing and raises no error when no proposal
    # ------------------------------------------------------------------

    def test_proposals_view_copy_report_no_proposal(self, app):
        """
        copy_report() is a silent no-op when current_proposal is None.
        No exception should be raised.
        """
        app.proposals_view.current_proposal = None

        # Should not raise
        app.proposals_view.copy_report()
        app.update_idletasks()

    # ------------------------------------------------------------------
    # Test 14: approve calls update_proposal_status with "approved"
    # ------------------------------------------------------------------

    def test_proposals_view_approve(self, app):
        """
        approve() calls proposal_manager.update_proposal_status with the
        current proposal id and the status string "approved".
        """
        app.proposals_view.current_proposal = dict(_SAMPLE_PROPOSAL)
        app.proposals_view.current_proposal["id"] = "abc"

        with (
            patch(
                "ruff_studio.ui.dashboard_window.proposal_manager.update_proposal_status",
                return_value=True,
            ) as mock_update,
            patch(
                "ruff_studio.ui.dashboard_window.proposal_manager.get_proposals",
                return_value=[],
            ),
            patch("ruff_studio.ui.dashboard_window.messagebox"),
        ):
            app.proposals_view.approve()

        mock_update.assert_called_once_with(
            app.proposals_view.controller.analyzer.conn, "abc", "approved"
        )

    # ------------------------------------------------------------------
    # Test 15: reject calls update_proposal_status with "rejected"
    # ------------------------------------------------------------------

    def test_proposals_view_reject(self, app):
        """
        reject() calls proposal_manager.update_proposal_status with the
        current proposal id and the status string "rejected".
        """
        app.proposals_view.current_proposal = dict(_SAMPLE_PROPOSAL)
        app.proposals_view.current_proposal["id"] = "xyz"

        with (
            patch(
                "ruff_studio.ui.dashboard_window.proposal_manager.update_proposal_status",
                return_value=True,
            ) as mock_update,
            patch(
                "ruff_studio.ui.dashboard_window.proposal_manager.get_proposals",
                return_value=[],
            ),
            patch("ruff_studio.ui.dashboard_window.messagebox"),
        ):
            app.proposals_view.reject()

        mock_update.assert_called_once_with(
            app.proposals_view.controller.analyzer.conn, "xyz", "rejected"
        )
