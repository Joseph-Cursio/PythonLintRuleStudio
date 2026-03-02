"""
Adapter for running pylint and parsing its output.
"""
import subprocess
import json
import sys
import logging
import re
from . import cache_manager

def get_pylint_version():
    """
    Retrieves the current pylint version.
    """
    try:
        python_executable = sys.executable
        result = subprocess.run(
            [python_executable, "-m", "pylint", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        # Pylint's version string is something like: "pylint 2.17.4"
        match = re.search(r"pylint (\d+\.\d+\.\d+)", result.stdout)
        if match:
            return match.group(1)
        return None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

def discover_rules():
    """
    Discovers available pylint rules, using a cache to speed up subsequent runs.
    """
    version = get_pylint_version()
    cache_key = "pylint_rules"
    cached_data = cache_manager.get_cache(cache_key)

    if cached_data and cached_data.get("version") == version:
        logging.info(f"Loaded pylint rules from cache for version {version}.")
        return cached_data.get("rules", {})

    logging.info("No valid cache found for pylint rules. Discovering from scratch.")

    try:
        python_executable = sys.executable
        result = subprocess.run(
            [python_executable, "-m", "pylint", "--list-msgs-json"],
            capture_output=True,
            text=True,
            check=True,
        )
        rules_json = json.loads(result.stdout)

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
                        "fix": "no",
                        "status": "stable",
                        "documentation": rule.get("description", "")
                    })
                    break

        categorized_rules = {
            name: data for name, data in categories.items() if data["rules"]
        }

        cache_manager.set_cache(
            cache_key, {"version": version, "rules": categorized_rules}
        )
        logging.info(f"Pylint rules for version {version} have been cached.")

        return categorized_rules

    except (
        subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError
    ) as e:
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
