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
            CREATE TABLE IF NOT EXISTS violations (
                id TEXT PRIMARY KEY,
                rule_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                line_number INTEGER,
                column INTEGER,
                message TEXT,
                timestamp DATETIME
            );
        """)
        conn.commit()
        logging.info("Table 'violations' created or already exists.")
    except sqlite3.Error as e:
        logging.error(f"Error creating tables: {e}")

def setup_database(db_file):
    """Setup the database: create connection and tables."""
    conn = create_connection(db_file)
    if conn is not None:
        create_tables(conn)
    return conn
