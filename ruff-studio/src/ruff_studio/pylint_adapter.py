"""
Adapter for running pylint and parsing its output.
"""
import subprocess
import json
import sys
import logging

def discover_rules():
    """
    Discovers available pylint rules by running pylint with --list-msgs.
    """
    try:
        # It's better to use the same Python executable that's running the app
        # to ensure we're getting pylint from the correct environment.
        python_executable = sys.executable
        result = subprocess.run(
            [python_executable, "-m", "pylint", "--list-msgs-json"],
            capture_output=True,
            text=True,
            check=True,
        )
        rules_json = json.loads(result.stdout)

        # We will need to categorize these. Pylint messages are prefixed:
        # C: Convention
        # R: Refactor
        # W: Warning
        # E: Error
        # F: Fatal

        categories = {
            "Convention": {"prefix": "C", "rules": []},
            "Refactor": {"prefix": "R", "rules": []},
            "Warning": {"prefix": "W", "rules": []},
            "Error": {"prefix": "E", "rules": []},
            "Fatal": {"prefix": "F", "rules": []},
        }

        for rule in rules_json:
            category_prefix = rule["msgid"][0]
            for cat_name, cat_data in categories.items():
                if cat_data["prefix"] == category_prefix:
                    categories[cat_name]["rules"].append({
                        "code": rule["msgid"],
                        "name": rule["symbol"],
                        "summary": rule["msg"],
                        "fix": "no", # Pylint doesn't have a stable autofix mechanism like ruff
                        "status": "stable", # Assuming all pylint rules are stable
                        "documentation": rule.get("description", "")
                    })
                    break

        # Filter out empty categories
        return {name: data for name, data in categories.items() if data["rules"]}

    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Failed to discover pylint rules: {e}")
        return {}


def run_scan(directory):
    """
    Runs pylint on a given directory and returns the results as a list of dicts.
    """
    try:
        python_executable = sys.executable
        command = [
            python_executable,
            "-m",
            "pylint",
            directory,
            "-f",
            "json",
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )
        # Pylint exits with a non-zero status code if it finds issues,
        # so we can't use check=True. We'll parse stdout even if it fails.
        if result.stdout:
            return json.loads(result.stdout)
        return []
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Failed to run pylint scan: {e}")
        return []
