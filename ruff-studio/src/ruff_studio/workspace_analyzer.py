"""
This module contains the WorkspaceAnalyzer class, which is responsible for
scanning the codebase, processing linting results, and storing them in the
database.
"""

import json
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
    run_id: str = None
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
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
        self.conn = None

    def _clear_violations(self, conn):
        """Clears all violations and scan runs from the database."""
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM violations")
            cursor.execute("DELETE FROM scan_runs")
            conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Error clearing violations: {e}")

    def _create_scan_run(self, conn, directory, branch, count, config):
        """Creates a new record in scan_runs."""
        run_id = str(uuid.uuid4())
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO scan_runs (
                    id, timestamp, directory, branch, 
                    total_violations, config_snapshot
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (run_id, now_iso, directory, branch, count, json.dumps(config)),
            )
            conn.commit()
            return run_id
        except sqlite3.Error as e:
            logging.error(f"Error creating scan run: {e}")
            return None

    def _store_violations(self, conn, violations: list[UnifiedViolationModel]):
        """
        Stores a list of violation objects in the database.

        Args:
            violations (list[UnifiedViolationModel]): The violations to store.
        """
        try:
            cursor = conn.cursor()
            for violation in violations:
                cursor.execute(
                    """
                    INSERT INTO violations (
                        id, run_id, rule_id, file_path, line_number, column, 
                        message, timestamp, author, commit_hash
                    )
                    VALUES (
                        :id, :run_id, :rule_id, :file_path, :line_number, :column, 
                        :message, :timestamp, :author, :commit_hash
                    )
                """,
                    asdict(violation),
                )
            conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Error storing violations: {e}")

    def get_scan_history(self, limit=10):
        """Returns the most recent scan runs."""
        conn = database_manager.create_connection(self.db_path)
        if not conn:
            return []
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, timestamp, branch, total_violations 
                FROM scan_runs 
                ORDER BY timestamp DESC LIMIT ?
            """,
                (limit,),
            )
            return cursor.fetchall()
        finally:
            conn.close()

    def get_author_stats(self):
        """Aggregates violations by author from the latest run."""
        conn = database_manager.create_connection(self.db_path)
        if not conn:
            return {}
        try:
            cursor = conn.cursor()
            # Get latest run ID
            cursor.execute("SELECT id FROM scan_runs ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return {}
            run_id = row[0]

            cursor.execute(
                """
                SELECT author, COUNT(*) as count 
                FROM violations 
                WHERE run_id = ? 
                GROUP BY author 
                ORDER BY count DESC
            """,
                (run_id,),
            )
            return dict(cursor.fetchall())
        finally:
            conn.close()

    def get_rule_hotspots(self):
        """Identifies the most frequent rule violations in the latest run."""
        conn = database_manager.create_connection(self.db_path)
        if not conn:
            return {}
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM scan_runs ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return {}
            run_id = row[0]

            cursor.execute(
                """
                SELECT rule_id, COUNT(*) as count 
                FROM violations 
                WHERE run_id = ? 
                GROUP BY rule_id 
                ORDER BY count DESC LIMIT 5
            """,
                (run_id,),
            )
            return dict(cursor.fetchall())
        finally:
            conn.close()

    def get_total_violations_trend(self, limit=30):
        """Returns violation counts over the last N scans."""
        conn = database_manager.create_connection(self.db_path)
        if not conn:
            return []
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT timestamp, total_violations 
                FROM scan_runs 
                ORDER BY timestamp ASC LIMIT ?
            """,
                (limit,),
            )
            return cursor.fetchall()
        finally:
            conn.close()

    def run_full_scan(
        self, directory: str, config: dict = None
    ) -> list[UnifiedViolationModel]:
        """
        Runs a full scan of the workspace, stores the results, and returns them.

        Args:
            directory (str): The directory to scan.
            config (dict): The configuration snapshot (optional).

        Returns:
            list[UnifiedViolationModel]: A list of violation objects.
        """
        conn = database_manager.setup_database(self.db_path)
        self.conn = conn
        if conn is None:
            return []

        # Check if it's a git repo
        branch = git_adapter.get_current_branch(directory)
        is_git = branch is not None

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

            # Create scan run record
            run_id = self._create_scan_run(
                conn, directory, branch, len(violations), config or {}
            )
            if run_id:
                for v in violations:
                    v.run_id = run_id
                self._store_violations(conn, violations)

            return violations
        finally:
            conn.close()
