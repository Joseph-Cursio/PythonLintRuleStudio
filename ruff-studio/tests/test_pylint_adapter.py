from ruff_studio import pylint_adapter
from unittest.mock import patch, MagicMock

@patch('subprocess.run')
def test_get_pylint_version(mock_run):
    """Tests that the pylint version is correctly parsed."""
    mock_run.return_value = MagicMock(stdout="pylint 2.17.4", returncode=0)
    version = pylint_adapter.get_pylint_version()
    assert version == "2.17.4"

@patch('subprocess.run')
def test_discover_rules(mock_run):
    """Tests that pylint rules are correctly discovered and categorized."""
    mock_run.return_value = MagicMock(
        stdout='''
        [
            {
                "msgid": "C0103",
                "symbol": "invalid-name",
                "msg": "Invalid name for variable",
                "description": "Some description"
            }
        ]
        ''',
        returncode=0
    )
    rules = pylint_adapter.discover_rules()
    assert "Convention" in rules
    assert len(rules["Convention"]["rules"]) == 1
    assert rules["Convention"]["rules"][0]["code"] == "C0103"
