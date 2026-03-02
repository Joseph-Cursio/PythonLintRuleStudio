import unittest
import sqlite3
from unittest.mock import patch, MagicMock
from ruff_studio.workspace_analyzer import WorkspaceAnalyzer, UnifiedViolationModel
from ruff_studio import database_manager

class TestWorkspaceAnalyzer(unittest.TestCase):

    def setUp(self):
        self.db_path = ":memory:"
        self.analyzer = WorkspaceAnalyzer(self.db_path)
        self.conn = sqlite3.connect(self.db_path)
        database_manager.create_tables(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_clear_violations(self):
        # Add a dummy violation
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO violations (id, rule_id, file_path) VALUES ('1', 'E501', 'f.py')")
        self.conn.commit()
        
        # Clear it
        self.analyzer._clear_violations(self.conn)
        
        cursor.execute("SELECT count(*) FROM violations")
        self.assertEqual(cursor.fetchone()[0], 0)

    def test_store_violations(self):
        v = UnifiedViolationModel(
            rule_id="F401",
            file_path="test.py",
            line_number=1,
            column=1,
            message="msg",
            author="John",
            commit_hash="abc"
        )
        self.analyzer._store_violations(self.conn, [v])
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT rule_id, author FROM violations")
        row = cursor.fetchone()
        self.assertEqual(row[0], "F401")
        self.assertEqual(row[1], "John")

    @patch('ruff_studio.git_adapter.get_line_blame')
    @patch('ruff_studio.git_adapter.get_current_branch')
    @patch('ruff_studio.pylint_adapter.run_scan')
    @patch('ruff_studio.ruff_adapter.run_scan')
    @patch('ruff_studio.database_manager.setup_database')
    def test_run_full_scan_pylint_and_attribution(
        self, mock_setup_database, mock_run_ruff, mock_run_pylint,
        mock_get_branch, mock_get_blame
    ):
        mock_setup_database.return_value = self.conn
        mock_get_branch.return_value = "main"
        mock_get_blame.return_value = {"author": "Tester", "commit": "sha123"}
        
        mock_run_ruff.return_value = []
        mock_run_pylint.return_value = [
            {
                "message-id": "C0103",
                "path": "test.py",
                "line": 10,
                "column": 5,
                "symbol": "invalid-name",
                "message": "Invalid name"
            }
        ]
        
        violations = self.analyzer.run_full_scan("/dir")
        
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].rule_id, "C0103")
        self.assertEqual(violations[0].author, "Tester")

    @patch('ruff_studio.database_manager.setup_database')
    def test_run_full_scan_db_error(self, mock_setup):
        mock_setup.return_value = None
        results = self.analyzer.run_full_scan("/dir")
        self.assertEqual(results, [])

if __name__ == '__main__':
    unittest.main()
