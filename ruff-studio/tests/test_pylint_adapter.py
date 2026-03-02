import json
import subprocess
from unittest.mock import patch, MagicMock
from ruff_studio import pylint_adapter

@patch('subprocess.run')
def test_get_pylint_version_success(mock_run):
    """Tests that the pylint version is correctly parsed."""
    mock_run.return_value = MagicMock(stdout="pylint 2.17.4\n", returncode=0)
    version = pylint_adapter.get_pylint_version()
    assert version == "2.17.4"

@patch('subprocess.run')
def test_get_pylint_version_failure(mock_run):
    """Tests error handling for get_pylint_version."""
    mock_run.side_effect = FileNotFoundError()
    assert pylint_adapter.get_pylint_version() is None
    
    mock_run.side_effect = subprocess.CalledProcessError(1, "pylint")
    assert pylint_adapter.get_pylint_version() is None

@patch('ruff_studio.cache_manager.get_cache')
@patch('ruff_studio.pylint_adapter.get_pylint_version')
def test_discover_rules_from_cache(mock_get_version, mock_get_cache):
    """Tests loading pylint rules from cache."""
    mock_get_version.return_value = "2.17.4"
    mock_get_cache.return_value = {
        "version": "2.17.4",
        "rules": {"Convention": {"prefix": "C", "rules": []}}
    }
    
    rules = pylint_adapter.discover_rules()
    assert "Convention" in rules
    mock_get_cache.assert_called_with("pylint_rules")

@patch('subprocess.run')
@patch('ruff_studio.cache_manager.set_cache')
@patch('ruff_studio.cache_manager.get_cache')
@patch('ruff_studio.pylint_adapter.get_pylint_version')
def test_discover_rules_fresh(
    mock_get_version, mock_get_cache, mock_set_cache, mock_run
):
    """Tests discovering pylint rules from scratch."""
    mock_get_version.return_value = "2.17.4"
    mock_get_cache.return_value = None
    mock_run.return_value = MagicMock(
        stdout=json.dumps([
            {
                "msgid": "C0103",
                "symbol": "invalid-name",
                "msg": "Invalid name",
                "description": "desc"
            },
            {
                "msgid": "E0001",
                "symbol": "syntax-error",
                "msg": "Syntax error",
                "description": "desc"
            }
        ]),
        returncode=0
    )
    
    rules = pylint_adapter.discover_rules()
    assert "Convention" in rules
    assert "Error" in rules
    assert rules["Convention"]["rules"][0]["code"] == "C0103"
    mock_set_cache.assert_called_once()

@patch('subprocess.run')
def test_discover_rules_error(mock_run):
    """Tests error handling in discover_rules."""
    mock_run.side_effect = subprocess.CalledProcessError(1, "pylint")
    # Patch get_pylint_version too to avoid it failing first
    with patch('ruff_studio.pylint_adapter.get_pylint_version', return_value="1.0.0"):
        with patch('ruff_studio.cache_manager.get_cache', return_value=None):
            rules = pylint_adapter.discover_rules()
            assert rules == {}

@patch('subprocess.run')
def test_run_scan_success(mock_run):
    """Tests running a pylint scan."""
    mock_results = [
        {
            "type": "convention",
            "module": "test",
            "obj": "",
            "line": 1,
            "column": 0,
            "path": "test.py",
            "symbol": "missing-docstring",
            "message": "Missing docstring",
            "message-id": "C0114"
        }
    ]
    mock_run.return_value = MagicMock(stdout=json.dumps(mock_results), returncode=0)
    
    results = pylint_adapter.run_scan("/some/dir")
    assert len(results) == 1
    assert results[0]["symbol"] == "missing-docstring"

@patch('subprocess.run')
def test_run_scan_error(mock_run):
    """Tests error handling in run_scan."""
    mock_run.side_effect = FileNotFoundError()
    results = pylint_adapter.run_scan("/some/dir")
    assert results == []
