"""
Tests for ProposalWindow (proposal_window.py) and ProposalsView (dashboard_window.py).

Uses the same app fixture pattern as test_main_ui.py and test_ui_panels.py.
A real in-memory SQLite DB is used for ProposalsView tests so that actual DB
operations can be verified end-to-end without relying on mocks for storage.
"""

import sqlite3
import pytest
import customtkinter as ctk
import tomlkit
from unittest.mock import patch, MagicMock

from ruff_studio.main import App
from ruff_studio.controller import StudioController
from ruff_studio import database_manager, proposal_manager
from ruff_studio.ui.proposal_window import ProposalWindow

# Capture real functions at module level (before any fixture patches are applied).
_real_get_proposals = proposal_manager.get_proposals
_real_update_proposal_status = proposal_manager.update_proposal_status


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
}

# A realistic proposal dict that covers every key read by ProposalsView.
SAMPLE_PROPOSAL = {
    "id": "test-id-001",
    "title": "Enable Security Rules",
    "rationale": "Improves security posture.",
    "status": "pending",
    "author": "User",
    "created_at": "2024-01-01T00:00:00",
    "branch_name": None,
    "impact_simulation": "[]",
    "config_before": "before",
    "config_after": "after",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Creates a real App instance with all blocking background tasks mocked."""
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


@pytest.fixture
def db_conn():
    """Real in-memory SQLite connection with all tables created."""
    conn = sqlite3.connect(":memory:")
    database_manager.create_tables(conn)
    return conn


@pytest.fixture
def app_with_db(app, db_conn):
    """App fixture wired to a real in-memory DB instead of a MagicMock conn."""
    app.controller.analyzer.conn = db_conn
    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_window(app):
    """Create a ProposalWindow with minimal valid arguments."""
    return ProposalWindow(app, "config_before", "config_after", [])


def _scrollable_children(scrollable_frame):
    """
    Return the user-packed children of a CTkScrollableFrame.

    CustomTkinter 5.x stores user widgets in an internal ``_scrollable_frame``
    attribute (a plain CTkFrame).  If that attribute is absent (e.g. a future
    version or a mock), fall back to winfo_children() on the outer frame.
    """
    inner = getattr(scrollable_frame, "_scrollable_frame", None)
    if inner is not None:
        return inner.winfo_children()
    return scrollable_frame.winfo_children()


# ---------------------------------------------------------------------------
# ProposalWindow tests
# ---------------------------------------------------------------------------

class TestProposalWindow:

    def test_proposal_window_opens(self, app):
        """ProposalWindow is a CTkToplevel instance and initialises without error."""
        win = None
        try:
            win = _make_window(app)
            app.update_idletasks()
            assert isinstance(win, ctk.CTkToplevel)
        finally:
            if win is not None:
                win.destroy()

    def test_get_data_no_title_shows_warning(self, app):
        """_get_data() with an empty title_entry returns (None, None) and shows a warning."""
        win = None
        try:
            win = _make_window(app)
            app.update_idletasks()

            with patch("ruff_studio.ui.proposal_window.messagebox") as mock_mb:
                title, rationale = win._get_data()

            assert title is None
            assert rationale is None
            mock_mb.showwarning.assert_called_once()
        finally:
            if win is not None:
                win.destroy()

    def test_get_data_with_title(self, app):
        """_get_data() returns the entered title and rationale when title is set."""
        win = None
        try:
            win = _make_window(app)
            win.title_entry.insert(0, "My Proposal")
            win.rationale_text.insert("1.0", "Some rationale")
            app.update_idletasks()

            title, rationale = win._get_data()

            assert title == "My Proposal"
            assert rationale == "Some rationale"
        finally:
            if win is not None:
                win.destroy()

    def test_create_only_no_title_does_not_destroy_window(self, app):
        """create_only() with no title returns early; the window is not destroyed."""
        win = None
        try:
            win = _make_window(app)
            app.update_idletasks()

            with patch("ruff_studio.ui.proposal_window.messagebox"):
                win.create_only()

            # If the window were destroyed, winfo_exists() would return 0.
            assert win.winfo_exists()
        finally:
            if win is not None and win.winfo_exists():
                win.destroy()

    def test_create_only_success_calls_create_proposal(self, app):
        """create_only() with a valid title calls proposal_manager.create_proposal."""
        win = None
        try:
            win = _make_window(app)
            win.title_entry.insert(0, "Security Rules")
            app.update_idletasks()

            with (
                patch("ruff_studio.ui.proposal_window.messagebox") as mock_mb,
                patch(
                    "ruff_studio.ui.proposal_window.proposal_manager.create_proposal",
                    return_value="new-uuid-123",
                ) as mock_create,
            ):
                win.create_only()

            mock_create.assert_called_once()
            # showinfo is called on success
            mock_mb.showinfo.assert_called_once()
        finally:
            # Window may have been destroyed by create_only on success — guard accordingly.
            if win is not None and win.winfo_exists():
                win.destroy()

    def test_create_only_proposal_fails_does_not_show_info(self, app):
        """create_only() does not call showinfo when create_proposal returns None."""
        win = None
        try:
            win = _make_window(app)
            win.title_entry.insert(0, "Security Rules")
            app.update_idletasks()

            with (
                patch("ruff_studio.ui.proposal_window.messagebox") as mock_mb,
                patch(
                    "ruff_studio.ui.proposal_window.proposal_manager.create_proposal",
                    return_value=None,
                ),
            ):
                win.create_only()

            mock_mb.showinfo.assert_not_called()
        finally:
            if win is not None and win.winfo_exists():
                win.destroy()

    def test_create_and_commit_no_title_skips_git(self, app):
        """create_and_commit() with no title returns before touching git_adapter."""
        win = None
        try:
            win = _make_window(app)
            app.update_idletasks()

            with (
                patch("ruff_studio.ui.proposal_window.messagebox"),
                patch("ruff_studio.ui.proposal_window.git_adapter") as mock_git,
            ):
                win.create_and_commit()

            mock_git.is_repo_clean.assert_not_called()
        finally:
            if win is not None and win.winfo_exists():
                win.destroy()

    def test_create_and_commit_dirty_repo_user_cancels(self, app):
        """
        create_and_commit() with a dirty repo and the user declining the
        confirmation dialog does not proceed to create a git branch.
        """
        win = None
        try:
            win = _make_window(app)
            win.title_entry.insert(0, "Security Rules")
            app.update_idletasks()

            with (
                patch("ruff_studio.ui.proposal_window.messagebox") as mock_mb,
                patch("ruff_studio.ui.proposal_window.git_adapter") as mock_git,
            ):
                mock_git.is_repo_clean.return_value = False
                mock_mb.askyesno.return_value = False

                win.create_and_commit()

            mock_git.create_branch.assert_not_called()
        finally:
            if win is not None and win.winfo_exists():
                win.destroy()

    def test_create_and_commit_dirty_repo_user_continues(self, app):
        """
        create_and_commit() with a dirty repo and the user accepting the
        confirmation dialog proceeds to create a git branch.
        """
        win = None
        try:
            win = _make_window(app)
            win.title_entry.insert(0, "Security Rules")
            app.controller.base_scan_results = []
            app.update_idletasks()

            with (
                patch("ruff_studio.ui.proposal_window.messagebox") as mock_mb,
                patch("ruff_studio.ui.proposal_window.git_adapter") as mock_git,
                patch(
                    "ruff_studio.ui.proposal_window.proposal_manager.create_proposal",
                    return_value="some-uuid",
                ),
                patch.object(app, "apply_changes", return_value=None),
            ):
                mock_git.is_repo_clean.return_value = False
                mock_mb.askyesno.return_value = True
                mock_git.create_branch.return_value = True
                mock_git.commit_changes.return_value = True

                win.create_and_commit()

            mock_git.create_branch.assert_called_once()
        finally:
            if win is not None and win.winfo_exists():
                win.destroy()

    def test_create_and_commit_clean_repo_calls_commit_changes(self, app):
        """
        create_and_commit() with a clean repo creates a branch, applies
        changes, and calls commit_changes.
        """
        win = None
        try:
            win = _make_window(app)
            win.title_entry.insert(0, "Enable Checks")
            app.controller.base_scan_results = []
            app.update_idletasks()

            with (
                patch("ruff_studio.ui.proposal_window.messagebox"),
                patch("ruff_studio.ui.proposal_window.git_adapter") as mock_git,
                patch(
                    "ruff_studio.ui.proposal_window.proposal_manager.create_proposal",
                    return_value="some-uuid",
                ),
                patch.object(app, "apply_changes", return_value=None),
            ):
                mock_git.is_repo_clean.return_value = True
                mock_git.create_branch.return_value = True
                mock_git.commit_changes.return_value = True

                win.create_and_commit()

            mock_git.commit_changes.assert_called_once()
        finally:
            if win is not None and win.winfo_exists():
                win.destroy()

    def test_create_and_commit_branch_fails_shows_error(self, app):
        """create_and_commit() shows showerror when create_branch returns False."""
        win = None
        try:
            win = _make_window(app)
            win.title_entry.insert(0, "Risky Change")
            app.controller.base_scan_results = []
            app.update_idletasks()

            with (
                patch("ruff_studio.ui.proposal_window.messagebox") as mock_mb,
                patch("ruff_studio.ui.proposal_window.git_adapter") as mock_git,
            ):
                mock_git.is_repo_clean.return_value = True
                mock_git.create_branch.return_value = False

                win.create_and_commit()

            mock_mb.showerror.assert_called_once()
        finally:
            if win is not None and win.winfo_exists():
                win.destroy()

    def test_create_and_commit_with_push_success_calls_push_branch(self, app):
        """
        create_and_commit() with push_var=True and a successful push calls
        git_adapter.push_branch.
        """
        win = None
        try:
            win = _make_window(app)
            win.title_entry.insert(0, "Pushed Proposal")
            win.push_var.set(True)
            app.controller.base_scan_results = []
            app.update_idletasks()

            with (
                patch("ruff_studio.ui.proposal_window.messagebox"),
                patch("ruff_studio.ui.proposal_window.git_adapter") as mock_git,
                patch(
                    "ruff_studio.ui.proposal_window.proposal_manager.create_proposal",
                    return_value="some-uuid",
                ),
                patch.object(app, "apply_changes", return_value=None),
            ):
                mock_git.is_repo_clean.return_value = True
                mock_git.create_branch.return_value = True
                mock_git.commit_changes.return_value = True
                mock_git.push_branch.return_value = True

                win.create_and_commit()

            mock_git.push_branch.assert_called_once()
        finally:
            if win is not None and win.winfo_exists():
                win.destroy()

    def test_create_and_commit_with_push_fail_still_shows_info(self, app):
        """
        create_and_commit() with push_var=True and a failed push still shows
        the success info dialog (the push failure is embedded in the message).
        """
        win = None
        try:
            win = _make_window(app)
            win.title_entry.insert(0, "Pushed Proposal Fail")
            win.push_var.set(True)
            app.controller.base_scan_results = []
            app.update_idletasks()

            with (
                patch("ruff_studio.ui.proposal_window.messagebox") as mock_mb,
                patch("ruff_studio.ui.proposal_window.git_adapter") as mock_git,
                patch(
                    "ruff_studio.ui.proposal_window.proposal_manager.create_proposal",
                    return_value="some-uuid",
                ),
                patch.object(app, "apply_changes", return_value=None),
            ):
                mock_git.is_repo_clean.return_value = True
                mock_git.create_branch.return_value = True
                mock_git.commit_changes.return_value = True
                mock_git.push_branch.return_value = False

                win.create_and_commit()

            # The code path still reaches showinfo (branch was created); the push
            # failure is noted in the message body, not via showerror.
            mock_mb.showinfo.assert_called_once()
            call_args = mock_mb.showinfo.call_args
            # The message body should mention the push failure.
            assert "Failed to push" in call_args[0][1] or "Failed to push" in str(call_args)
        finally:
            if win is not None and win.winfo_exists():
                win.destroy()


# ---------------------------------------------------------------------------
# ProposalsView tests
# ---------------------------------------------------------------------------

class TestProposalsView:

    def test_proposals_view_load_empty(self, app_with_db):
        """load_proposals() with an empty DB renders no proposal buttons."""
        view = app_with_db.proposals_view

        with patch(
            "ruff_studio.ui.dashboard_window.proposal_manager.get_proposals",
            side_effect=lambda conn, **kw: _real_get_proposals(conn, **kw),
        ):
            view.load_proposals()
            app_with_db.update_idletasks()

        # CTkScrollableFrame keeps user widgets in an inner frame.
        buttons = [
            w for w in _scrollable_children(view.list_frame)
            if isinstance(w, ctk.CTkButton)
        ]
        assert len(buttons) == 0

    def test_proposals_view_load_with_proposals(self, app_with_db):
        """load_proposals() renders one button per proposal returned from the DB."""
        view = app_with_db.proposals_view
        conn = app_with_db.controller.analyzer.conn

        # Insert a real proposal into the in-memory DB.
        proposal_manager.create_proposal(
            conn,
            "Test Proposal",
            "Because tests matter.",
            "before_cfg",
            "after_cfg",
            [],
        )

        with patch(
            "ruff_studio.ui.dashboard_window.proposal_manager.get_proposals",
            side_effect=lambda conn, **kw: _real_get_proposals(conn, **kw),
        ):
            view.load_proposals()
            app_with_db.update_idletasks()

        buttons = [
            w for w in _scrollable_children(view.list_frame)
            if isinstance(w, ctk.CTkButton)
        ]
        assert len(buttons) == 1

    def test_proposals_view_show_detail_pending_shows_approve_reject(self, app):
        """show_detail() with status='pending' packs approve and reject buttons."""
        view = app.proposals_view

        view.show_detail(SAMPLE_PROPOSAL)
        app.update_idletasks()

        assert view.detail_title.cget("text") == "Enable Security Rules"
        assert view.approve_btn.winfo_manager() == "pack"
        assert view.reject_btn.winfo_manager() == "pack"

    def test_proposals_view_show_detail_approved_hides_approve_reject(self, app):
        """show_detail() with status='approved' hides the approve/reject buttons."""
        view = app.proposals_view

        approved_proposal = {**SAMPLE_PROPOSAL, "status": "approved"}
        view.show_detail(approved_proposal)
        app.update_idletasks()

        assert view.approve_btn.winfo_manager() == ""
        assert view.reject_btn.winfo_manager() == ""

    def test_proposals_view_copy_report_no_proposal_is_noop(self, app):
        """copy_report() with current_proposal=None returns without raising."""
        view = app.proposals_view
        view.current_proposal = None

        # Should not raise.
        view.copy_report()

    def test_proposals_view_copy_report_with_proposal_shows_info(self, app):
        """copy_report() with a valid current_proposal calls messagebox.showinfo."""
        view = app.proposals_view
        view.current_proposal = SAMPLE_PROPOSAL

        with patch("ruff_studio.ui.dashboard_window.messagebox") as mock_mb:
            view.copy_report()

        mock_mb.showinfo.assert_called_once()

    def test_proposals_view_approve_updates_db_status(self, app_with_db):
        """approve() changes the proposal's status to 'approved' in the real DB."""
        view = app_with_db.proposals_view
        conn = app_with_db.controller.analyzer.conn

        # Insert a pending proposal directly into the DB.
        p_id = proposal_manager.create_proposal(
            conn,
            "Approve Me",
            "Good reason.",
            "before",
            "after",
            [],
        )

        # Wire current_proposal so approve() knows which row to update.
        view.current_proposal = {**SAMPLE_PROPOSAL, "id": p_id}

        with (
            patch("ruff_studio.ui.dashboard_window.messagebox"),
            patch(
                "ruff_studio.ui.dashboard_window.proposal_manager.get_proposals",
                side_effect=lambda conn, **kw: _real_get_proposals(conn, **kw),
            ),
            patch(
                "ruff_studio.ui.dashboard_window.proposal_manager.update_proposal_status",
                side_effect=lambda conn, pid, status, **kw: _real_update_proposal_status(conn, pid, status, **kw),
            ),
        ):
            view.approve()
            app_with_db.update_idletasks()

        # Verify the DB was updated.
        rows = _real_get_proposals(conn, status="approved")
        assert any(r["id"] == p_id for r in rows)

    def test_proposals_view_reject_updates_db_status(self, app_with_db):
        """reject() changes the proposal's status to 'rejected' in the real DB."""
        view = app_with_db.proposals_view
        conn = app_with_db.controller.analyzer.conn

        p_id = proposal_manager.create_proposal(
            conn,
            "Reject Me",
            "Bad reason.",
            "before",
            "after",
            [],
        )

        view.current_proposal = {**SAMPLE_PROPOSAL, "id": p_id}

        with (
            patch("ruff_studio.ui.dashboard_window.messagebox"),
            patch(
                "ruff_studio.ui.dashboard_window.proposal_manager.get_proposals",
                side_effect=lambda conn, **kw: _real_get_proposals(conn, **kw),
            ),
            patch(
                "ruff_studio.ui.dashboard_window.proposal_manager.update_proposal_status",
                side_effect=lambda conn, pid, status, **kw: _real_update_proposal_status(conn, pid, status, **kw),
            ),
        ):
            view.reject()
            app_with_db.update_idletasks()

        rows = _real_get_proposals(conn, status="rejected")
        assert any(r["id"] == p_id for r in rows)
