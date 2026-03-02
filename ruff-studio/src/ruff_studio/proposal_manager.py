"""
Handles logic for creating, retrieving, and updating linting 
configuration proposals.
"""
import uuid
import json
import logging
import sqlite3
from datetime import datetime, timezone

def create_proposal(
    conn, title, rationale, config_before, config_after, 
    impact_simulation, author="User", branch_name=None
):
    """Creates a new proposal in the database."""
    proposal_id = str(uuid.uuid4())
    impact_json = json.dumps(impact_simulation)
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO proposals (
                id, title, rationale, config_before, config_after, 
                impact_simulation, author, status, branch_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            proposal_id, title, rationale, config_before, config_after, 
            impact_json, author, "pending", branch_name
        ))
        
        # Log the event in audit_log
        details = {"proposal_id": proposal_id, "title": title}
        log_event(conn, "proposal_created", author, details)
        
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
            cursor.execute(
                "SELECT * FROM proposals WHERE status = ? "
                "ORDER BY created_at DESC", (status,)
            )
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
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
                UPDATE proposals SET status = ?, implemented_at = ? WHERE id = ?
            """, (status, now_iso, proposal_id))
        else:
            cursor.execute("""
                UPDATE proposals SET status = ? WHERE id = ?
            """, (status, proposal_id))
            
        details = {"proposal_id": proposal_id, "new_status": status}
        log_event(conn, "proposal_status_updated", user, details)
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"Error updating proposal status: {e}")
        return False

def log_event(conn, event_type, user, details):
    """Logs an event to the audit_log table."""
    try:
        cursor = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO audit_log (id, event_type, timestamp, user, details)
            VALUES (?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), event_type, now_iso, user, json.dumps(details)))
        # Note: No commit here as it's usually called within another transaction
    except sqlite3.Error as e:
        logging.error(f"Error logging event: {e}")

def generate_impact_report(
    config_before, config_after, impact_simulation, 
    base_violations=None
):
    """Generates a professional Markdown report of the changes."""
    report = []
    report.append("# Linting Configuration Proposal")
    report.append("\n## Summary of Changes")
    
    # Simple heuristic to find diff in rules (very basic)
    report.append("This proposal modifies the project's linting configuration to align with updated quality standards.")
    
    report.append("\n## Impact Analysis")
    sim_count = len(impact_simulation)
    base_count = len(base_violations) if base_violations is not None else "N/A"
    
    report.append(f"- **Current Violations:** {base_count}")
    report.append(f"- **Projected Violations:** {sim_count}")
    
    if base_violations is not None:
        delta = sim_count - len(base_violations)
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        report.append(f"- **Net Change:** {delta_str} violations")

    if impact_simulation:
        report.append("\n### Top Affected Rules (Simulation)")
        hotspots = {}
        for v in impact_simulation:
            code = v.get("code") or v.get("rule_id") # Handle different formats
            hotspots[code] = hotspots.get(code, 0) + 1
        
        sorted_hotspots = sorted(
            hotspots.items(), key=lambda x: x[1], reverse=True
        )[:5]
        for code, count in sorted_hotspots:
            report.append(f"- **{code}:** {count} violations")

    report.append("\n## Configuration Diff")
    report.append("```toml")
    # In a real scenario, we might use a library to diff the TOML
    # For now, we just indicate it's updated.
    report.append("# pyproject.toml updated")
    report.append("```")
    
    report.append("\n---")
    report.append("*Generated by Ruff Studio*")
    
    return "\n".join(report)
