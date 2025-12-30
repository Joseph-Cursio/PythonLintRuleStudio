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
from . import ruff_adapter, database_manager

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
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.utcnow)
    # TODO: Add other fields from PRD, such as severity, git context, etc.

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
                    INSERT INTO violations (id, rule_id, file_path, line_number, column, message, timestamp)
                    VALUES (:id, :rule_id, :file_path, :line_number, :column, :message, :timestamp)
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

        try:
            raw_results = ruff_adapter.run_scan(directory)
            violations = []
            for result in raw_results:
                violation = UnifiedViolationModel(
                    rule_id=result["code"],
                    file_path=result["filename"],
                    line_number=result["location"]["row"],
                    column=result["location"]["column"],
                    message=result["message"],
                )
                violations.append(violation)

            self._clear_violations(conn)
            self._store_violations(conn, violations)
            return violations
        finally:
            conn.close()
