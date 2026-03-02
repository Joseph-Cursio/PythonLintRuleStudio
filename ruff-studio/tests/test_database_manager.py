import sqlite3
import pytest
from ruff_studio import database_manager
import os

def test_create_connection(tmp_path):
    """Tests creating a connection to a database file."""
    db_file = tmp_path / "test.db"
    conn = database_manager.create_connection(str(db_file))
    assert isinstance(conn, sqlite3.Connection)
    conn.close()

def test_create_tables(tmp_path):
    """Tests creating tables in the database."""
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    database_manager.create_tables(conn)
    
    # Check if table exists
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='violations';")
    assert cursor.fetchone() is not None
    conn.close()

def test_setup_database(tmp_path):
    """Tests the overall setup_database function."""
    db_file = tmp_path / "test.db"
    conn = database_manager.setup_database(str(db_file))
    assert isinstance(conn, sqlite3.Connection)
    
    # Check if table exists
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='violations';")
    assert cursor.fetchone() is not None
    conn.close()

def test_create_connection_error():
    """Tests error handling when connecting to an invalid path."""
    # Using an empty string for connection might fail or create an in-memory db depending on system,
    # but we can try to trigger an error with a directory path that doesn't exist as a parent.
    conn = database_manager.create_connection("/non_existent_dir/test.db")
    assert conn is None
