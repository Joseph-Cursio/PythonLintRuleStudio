"""
Handles the logic for creating, retrieving, and updating linting configuration proposals.
"""
import uuid
import json
import logging
import sqlite3
from datetime import datetime

def create_proposal(conn, title, rationale, config_before, config_after, impact_simulation, author="User"):
    """Creates a new proposal in the database."""
    proposal_id = str(uuid.uuid4())
    impact_json = json.dumps(impact_simulation)
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO proposals (
                id, title, rationale, config_before, config_after, impact_simulation, author, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (proposal_id, title, rationale, config_before, config_after, impact_json, author, "pending"))
        
        # Log the event in audit_log
        log_event(conn, "proposal_created", author, {"proposal_id": proposal_id, "title": title})
        
        conn.commit()
        return proposal_id
    except sqlite3.Error as e:
        logging.error(f"Error creating proposal: {e}")
        return None

def get_proposals(conn, status=None):
    """Retrieves proposals from the database, optionally filtered by status."""
    try:
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM proposals WHERE status = ? ORDER BY created_at DESC", (status,))
        else:
            cursor.execute("SELECT * FROM proposals ORDER BY created_at DESC")
        
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Error fetching proposals: {e}")
        return []

def update_proposal_status(conn, proposal_id, status, user="User"):
    """Updates the status of a proposal (e.g., approved, implemented)."""
    try:
        cursor = conn.cursor()
        if status == "implemented":
            cursor.execute("""
                UPDATE proposals SET status = ?, implemented_at = ? WHERE id = ?
            """, (status, datetime.now().isoformat(), proposal_id))
        else:
            cursor.execute("""
                UPDATE proposals SET status = ? WHERE id = ?
            """, (status, proposal_id))
            
        log_event(conn, "proposal_status_updated", user, {"proposal_id": proposal_id, "new_status": status})
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Error updating proposal status: {e}")
        return False

def log_event(conn, event_type, user, details):
    """Logs an event to the audit_log table."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_log (id, event_type, user, details)
            VALUES (?, ?, ?, ?)
        """, (str(uuid.uuid4()), event_type, user, json.dumps(details)))
        # Note: No commit here as it's usually called within another transaction
    except sqlite3.Error as e:
        logging.error(f"Error logging event: {e}")
