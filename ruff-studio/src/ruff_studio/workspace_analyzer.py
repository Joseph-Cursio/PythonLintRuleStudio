"""
This module contains the WorkspaceAnalyzer class, which is responsible for
scanning the codebase, processing linting results, and storing them in the
database.
"""
import uuid
import datetime
import sqlite3
import logging
from dataclasses import dataclass, field, asdict
from . import ruff_adapter, database_manager, pylint_adapter, git_adapter

@dataclass
class UnifiedViolationModel:
    """
    A standardized data model for a single linting violation.
    """
    rule_id: str
    file_path: str
    line_number: int
    column: int
    message: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime.datetime = field(
        default_factory=datetime.datetime.utcnow
    )
    author: str = None
    commit_hash: str = None

class WorkspaceAnalyzer:
    """
    Analyzes the workspace for linting violations.
    """
    def __init__(self, db_path):
        """
        Initializes the WorkspaceAnalyzer.

        Args:
            db_path (str): The path to the SQLite database.
        """
        self.db_path = db_path

    def _clear_violations(self, conn):
        """Clears all violations from the database."""
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM violations")
            conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Error clearing violations: {e}")


    def _store_violations(self, conn, violations: list[UnifiedViolationModel]):
        """
        Stores a list of violation objects in the database.

        Args:
            violations (list[UnifiedViolationModel]): The violations to store.
        """
        try:
            cursor = conn.cursor()
            for violation in violations:
                cursor.execute("""
                    INSERT INTO violations (
                        id, rule_id, file_path, line_number, column, 
                        message, timestamp, author, commit_hash
                    )
                    VALUES (
                        :id, :rule_id, :file_path, :line_number, :column, 
                        :message, :timestamp, :author, :commit_hash
                    )
                """, asdict(violation))
            conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Error storing violations: {e}")

    def run_full_scan(self, directory: str) -> list[UnifiedViolationModel]:
        """
        Runs a full scan of the workspace, stores the results, and returns them.

        Args:
            directory (str): The directory to scan.

        Returns:
            list[UnifiedViolationModel]: A list of violation objects.
        """
        conn = database_manager.setup_database(self.db_path)
        if conn is None:
            return []

        # Check if it's a git repo
        is_git = git_adapter.get_current_branch(directory) is not None

        try:
            # --- Ruff Scan ---
            ruff_raw_results = ruff_adapter.run_scan(directory)
            violations = []
            for result in ruff_raw_results:
                v = UnifiedViolationModel(
                    rule_id=result["code"],
                    file_path=result["filename"],
                    line_number=result["location"]["row"],
                    column=result["location"]["column"],
                    message=result["message"],
                )
                if is_git:
                    blame = git_adapter.get_line_blame(
                        directory, v.file_path, v.line_number
                    )
                    if blame:
                        v.author = blame.get("author")
                        v.commit_hash = blame.get("commit")
                violations.append(v)

            # --- Pylint Scan ---
            pylint_raw_results = pylint_adapter.run_scan(directory)
            for result in pylint_raw_results:
                v = UnifiedViolationModel(
                    rule_id=result["message-id"],
                    file_path=result["path"],
                    line_number=result["line"],
                    column=result["column"],
                    message=f"({result['symbol']}) {result['message']}",
                )
                if is_git:
                    blame = git_adapter.get_line_blame(
                        directory, v.file_path, v.line_number
                    )
                    if blame:
                        v.author = blame.get("author")
                        v.commit_hash = blame.get("commit")
                violations.append(v)


            self._clear_violations(conn)
            self._store_violations(conn, violations)
            return violations
        finally:
            conn.close()
