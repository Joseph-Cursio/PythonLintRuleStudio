import unittest
from unittest.mock import patch, MagicMock
from ruff_studio.workspace_analyzer import WorkspaceAnalyzer, UnifiedViolationModel

class TestWorkspaceAnalyzer(unittest.TestCase):

    @patch('ruff_studio.ruff_adapter.run_scan')
    @patch('ruff_studio.database_manager.setup_database')
    def test_run_full_scan_and_store(self, mock_setup_database, mock_run_scan):
        # Arrange
        mock_db_conn = MagicMock()
        mock_setup_database.return_value = mock_db_conn

        mock_run_scan.return_value = [
            {
                "code": "F401",
                "filename": "/path/to/file1.py",
                "location": {"row": 1, "column": 1},
                "message": "Unused import"
            },
            {
                "code": "E501",
                "filename": "/path/to/file2.py",
                "location": {"row": 2, "column": 81},
                "message": "Line too long"
            }
        ]

        analyzer = WorkspaceAnalyzer("test.db")
        analyzer._clear_violations = MagicMock()
        analyzer._store_violations = MagicMock()

        # Act
        violations = analyzer.run_full_scan("/fake/directory")

        # Assert
        self.assertEqual(len(violations), 2)

        self.assertIsInstance(violations[0], UnifiedViolationModel)
        self.assertEqual(violations[0].rule_id, "F401")
        self.assertEqual(violations[0].file_path, "/path/to/file1.py")

        self.assertIsInstance(violations[1], UnifiedViolationModel)
        self.assertEqual(violations[1].rule_id, "E501")
        self.assertEqual(violations[1].file_path, "/path/to/file2.py")

        analyzer._clear_violations.assert_called_once()
        analyzer._store_violations.assert_called_once_with(violations)
        mock_run_scan.assert_called_once_with("/fake/directory")

if __name__ == '__main__':
    unittest.main()
