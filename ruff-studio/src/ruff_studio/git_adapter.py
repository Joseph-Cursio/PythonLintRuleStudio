"""
Provides an interface for Git operations required by the proposal workflow.
"""
import subprocess
import logging

def is_repo_clean(repo_path):
    """Checks if the git repository has any uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return len(result.stdout.strip()) == 0
    except subprocess.CalledProcessError as e:
        logging.error(f"Error checking git status: {e}")
        return False

def create_branch(repo_path, branch_name):
    """Creates and switches to a new git branch."""
    try:
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=repo_path,
            check=True,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error creating branch {branch_name}: {e.stderr.decode()}")
        return False

def commit_changes(repo_path, message, files=None):
    """Stages and commits changes to the repository."""
    try:
        if files:
            for file in files:
                subprocess.run(["git", "add", file], cwd=repo_path, check=True)
        else:
            subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
            
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo_path,
            check=True,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error committing changes: {e.stderr.decode()}")
        return False

def get_current_branch(repo_path):
    """Returns the name of the current active branch."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

def switch_branch(repo_path, branch_name):
    """Switches to an existing git branch."""
    try:
        subprocess.run(
            ["git", "checkout", branch_name],
            cwd=repo_path,
            check=True,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error switching to branch {branch_name}: {e.stderr.decode()}")
        return False
