import sqlite3
import pytest
import json
from ruff_studio import database_manager, proposal_manager

@pytest.fixture
def db_conn():
    """Fixture to provide an in-memory database with tables created."""
    conn = sqlite3.connect(":memory:")
    database_manager.create_tables(conn)
    yield conn
    conn.close()

def test_create_proposal(db_conn):
    """Tests that a proposal is correctly created in the database."""
    title = "Enable Ruff security rules"
    rationale = "We need to catch more security anti-patterns early."
    config_before = """[tool.ruff.lint]
select = ["E", "F"]"""
    config_after = """[tool.ruff.lint]
select = ["E", "F", "S"]"""
    impact = {"violations_found": 12, "files_affected": 3}
    
    proposal_id = proposal_manager.create_proposal(
        db_conn, title, rationale, config_before, config_after, impact
    )
    
    assert proposal_id is not None
    
    # Check that it exists in the database
    proposals = proposal_manager.get_proposals(db_conn)
    assert len(proposals) == 1
    assert proposals[0]["id"] == proposal_id
    assert proposals[0]["title"] == title
    assert proposals[0]["status"] == "pending"
    assert json.loads(proposals[0]["impact_simulation"]) == impact

def test_get_proposals_by_status(db_conn):
    """Tests filtering proposals by status."""
    proposal_manager.create_proposal(db_conn, "P1", "R1", "B1", "A1", {})
    proposal_manager.create_proposal(db_conn, "P2", "R2", "B2", "A2", {})
    
    # Approve one
    proposals = proposal_manager.get_proposals(db_conn)
    p1_id = proposals[1]["id"]
    proposal_manager.update_proposal_status(db_conn, p1_id, "approved")
    
    pending = proposal_manager.get_proposals(db_conn, status="pending")
    approved = proposal_manager.get_proposals(db_conn, status="approved")
    
    assert len(pending) == 1
    assert len(approved) == 1
    assert approved[0]["id"] == p1_id

def test_update_proposal_implemented(db_conn):
    """Tests updating a proposal to 'implemented' status."""
    proposal_id = proposal_manager.create_proposal(
        db_conn, "Test", "Rationale", "Before", "After", {}
    )
    
    success = proposal_manager.update_proposal_status(
        db_conn, proposal_id, "implemented"
    )
    assert success is True
    
    proposals = proposal_manager.get_proposals(db_conn, status="implemented")
    assert len(proposals) == 1
    assert proposals[0]["implemented_at"] is not None

def test_audit_log_entry(db_conn):
    """Tests that events are logged in the audit_log table."""
    proposal_manager.create_proposal(db_conn, "Log Test", "Rationale", "B", "A", {})
    
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM audit_log")
    logs = cursor.fetchall()
    
    assert len(logs) >= 1
    # Check if the event type is correct
    # Logged as: (id, event_type, timestamp, user, details)
    event_types = [log[1] for log in logs]
    assert "proposal_created" in event_types

def test_create_proposal_error(db_conn):
    """Tests error handling when creating a proposal fails (e.g. invalid connection)."""
    # Close the connection to trigger an error
    db_conn.close()
    result = proposal_manager.create_proposal(db_conn, "T", "R", "B", "A", {})
    assert result is None

def test_get_proposals_error(db_conn):
    """Tests error handling when fetching proposals fails."""
    db_conn.close()
    result = proposal_manager.get_proposals(db_conn)
    assert result == []

def test_update_status_error(db_conn):
    """Tests error handling when updating status fails."""
    db_conn.close()
    result = proposal_manager.update_proposal_status(db_conn, "id", "approved")
    assert result is False
