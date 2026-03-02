"""
This module handles all database operations for Ruff Studio, including
creating the database and tables, and storing violation data.
"""
import sqlite3
import logging

def create_connection(db_file):
    """Create a database connection to the SQLite database."""
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        logging.info(f"Successfully connected to SQLite database: {db_file}")
    except sqlite3.Error as e:
        logging.error(f"Error connecting to SQLite database: {e}")
    return conn

def create_tables(conn):
    """Create the necessary tables if they don't exist."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_runs (
                id TEXT PRIMARY KEY,
                timestamp TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                directory TEXT NOT NULL,
                branch TEXT,
                total_violations INTEGER,
                config_snapshot TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS violations (
                id TEXT PRIMARY KEY,
                run_id TEXT,
                rule_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                line_number INTEGER,
                column INTEGER,
                message TEXT,
                timestamp TEXT,
                author TEXT,
                commit_hash TEXT,
                FOREIGN KEY (run_id) REFERENCES scan_runs(id)
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                type TEXT,
                rationale TEXT,
                author TEXT,
                created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                status TEXT DEFAULT 'pending',
                impact_simulation TEXT,
                config_before TEXT,
                config_after TEXT,
                implemented_at TEXT,
                branch_name TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                timestamp TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                user TEXT,
                details TEXT
            );
        """)
        conn.commit()
        logging.info("All required tables created or already exist.")
    except sqlite3.Error as e:
        logging.error(f"Error creating tables: {e}")

def setup_database(db_file):
    """Setup the database: create connection and tables."""
    conn = create_connection(db_file)
    if conn is not None:
        create_tables(conn)
    return conn
