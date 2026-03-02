import unittest
from unittest.mock import patch, MagicMock
from ruff_studio.workspace_analyzer import WorkspaceAnalyzer, UnifiedViolationModel

class TestWorkspaceAnalyzer(unittest.TestCase):

    @patch('ruff_studio.git_adapter.get_line_blame')
    @patch('ruff_studio.git_adapter.get_current_branch')
    @patch('ruff_studio.pylint_adapter.run_scan')
    @patch('ruff_studio.ruff_adapter.run_scan')
    @patch('ruff_studio.database_manager.setup_database')
    def test_run_full_scan_and_store(
        self, mock_setup_database, mock_run_ruff, mock_run_pylint,
        mock_get_branch, mock_get_blame
    ):
        # Arrange
        mock_db_conn = MagicMock()
        mock_setup_database.return_value = mock_db_conn
        mock_get_branch.return_value = "main"
        mock_get_blame.return_value = {"author": "Tester", "commit": "sha123"}

        mock_run_ruff.return_value = [
            {
                "code": "F401",
                "filename": "/path/to/file1.py",
                "location": {"row": 1, "column": 1},
                "message": "Unused import"
            }
        ]
        mock_run_pylint.return_value = []

        analyzer = WorkspaceAnalyzer("test.db")
        analyzer._clear_violations = MagicMock()
        analyzer._store_violations = MagicMock()

        # Act
        violations = analyzer.run_full_scan("/fake/directory")

        # Assert
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].author, "Tester")
        self.assertEqual(violations[0].commit_hash, "sha123")

        analyzer._clear_violations.assert_called_once()
        analyzer._store_violations.assert_called_once_with(mock_db_conn, violations)
        mock_run_ruff.assert_called_once_with("/fake/directory")

if __name__ == '__main__':
    unittest.main()
