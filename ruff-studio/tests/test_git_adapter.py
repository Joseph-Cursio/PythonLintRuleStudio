from unittest.mock import patch, MagicMock
from ruff_studio import git_adapter
import subprocess


@patch("subprocess.run")
def test_is_repo_clean_true(mock_run):
    """Tests identifying a clean repository."""
    mock_run.return_value = MagicMock(stdout="", returncode=0)
    assert git_adapter.is_repo_clean("/path/to/repo") is True


@patch("subprocess.run")
def test_is_repo_clean_false(mock_run):
    """Tests identifying a dirty repository."""
    mock_run.return_value = MagicMock(stdout=" M file.py\n", returncode=0)
    assert git_adapter.is_repo_clean("/path/to/repo") is False


@patch("subprocess.run")
def test_create_branch_success(mock_run):
    """Tests successful branch creation."""
    mock_run.return_value = MagicMock(returncode=0)
    assert git_adapter.create_branch("/path/to/repo", "new-branch") is True
    mock_run.assert_called_with(
        ["git", "checkout", "-b", "new-branch"],
        cwd="/path/to/repo",
        check=True,
        capture_output=True,
    )


@patch("subprocess.run")
def test_commit_changes_success(mock_run):
    """Tests staging and committing changes."""
    mock_run.return_value = MagicMock(returncode=0)
    result = git_adapter.commit_changes(
        "/path/to/repo", "Commit Message", files=["file1.py"]
    )
    assert result is True

    # Check that add was called
    mock_run.assert_any_call(
        ["git", "add", "file1.py"], cwd="/path/to/repo", check=True
    )
    # Check that commit was called
    mock_run.assert_any_call(
        ["git", "commit", "-m", "Commit Message"],
        cwd="/path/to/repo",
        check=True,
        capture_output=True,
    )


@patch("subprocess.run")
def test_get_current_branch(mock_run):
    """Tests retrieving current branch name."""
    mock_run.return_value = MagicMock(stdout="main\n", returncode=0)
    assert git_adapter.get_current_branch("/path/to/repo") == "main"


@patch("subprocess.run")
def test_git_error_handling(mock_run):
    """Tests that errors in git commands are caught and handled."""
    # Simulate a failed command
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd="git checkout -b fail", stderr=b"fatal: branch already exists"
    )
    assert git_adapter.create_branch("/path/to/repo", "fail") is False
    assert git_adapter.is_repo_clean("/path/to/repo") is False
    assert git_adapter.commit_changes("/path/to/repo", "msg") is False


@patch("subprocess.run")
def test_switch_branch_success(mock_run):
    """Tests successful branch switching."""
    mock_run.return_value = MagicMock(returncode=0)
    assert git_adapter.switch_branch("/path/to/repo", "existing-branch") is True


@patch("subprocess.run")
def test_switch_branch_error(mock_run):
    """Tests error handling for switching branch."""
    mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr=b"error")
    assert git_adapter.switch_branch("/path/to/repo", "fail") is False


@patch("subprocess.run")
def test_get_line_blame_success(mock_run):
    """Tests that git blame output is correctly parsed."""
    mock_stdout = (
        "abc123sha 1 1 1\nauthor John Doe\nauthor-time 1700000000\nfilename file.py\n"
    )
    mock_run.return_value = MagicMock(stdout=mock_stdout, returncode=0)

    info = git_adapter.get_line_blame("/path", "file.py", 10)

    assert info["commit"] == "abc123sha"
    assert info["author"] == "John Doe"
    assert "2023-11-" in info["timestamp"]  # Roughly checking date conversion


# ---------------------------------------------------------------------------
# Missing-branch coverage
# ---------------------------------------------------------------------------


@patch("subprocess.run")
def test_get_current_branch_failure(mock_run):
    """When git rev-parse raises CalledProcessError, get_current_branch returns None."""
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=128, cmd=["git", "rev-parse", "--abbrev-ref", "HEAD"]
    )
    result = git_adapter.get_current_branch("/path/to/repo")
    assert result is None


@patch("subprocess.run")
def test_push_branch_success(mock_run):
    """When git push succeeds, push_branch returns True."""
    mock_run.return_value = MagicMock(returncode=0)
    result = git_adapter.push_branch("/path/to/repo", "feature-branch")
    assert result is True
    mock_run.assert_called_once_with(
        ["git", "push", "-u", "origin", "feature-branch"],
        cwd="/path/to/repo",
        check=True,
        capture_output=True,
    )


@patch("subprocess.run")
def test_push_branch_failure(mock_run):
    """When git push raises CalledProcessError, push_branch returns False."""
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd=["git", "push", "-u", "origin", "feature-branch"],
        stderr=b"error: remote rejected",
    )
    result = git_adapter.push_branch("/path/to/repo", "feature-branch")
    assert result is False


@patch("subprocess.run")
def test_get_line_blame_empty_output(mock_run):
    """When git blame produces no output, get_line_blame returns None."""
    mock_run.return_value = MagicMock(stdout="", returncode=0)
    result = git_adapter.get_line_blame("/path", "file.py", 1)
    assert result is None


@patch("subprocess.run")
def test_get_line_blame_exception(mock_run):
    """When subprocess.run raises an unexpected exception, get_line_blame returns None."""
    mock_run.side_effect = Exception("unexpected failure")
    result = git_adapter.get_line_blame("/path", "file.py", 1)
    assert result is None
