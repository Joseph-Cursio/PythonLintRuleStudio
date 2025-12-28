import subprocess
import json
import logging
import tomlkit
import tempfile
import os

def _run_ruff_command(args):
    """Utility to run a ruff command and handle common errors."""
    is_check_command = "check" in args

    try:
        process = subprocess.run(
            ["ruff", *args, "--quiet"],
            capture_output=True,
            text=True,
            check=not is_check_command,  # Don't raise for 'check' command
            encoding='utf-8'
        )
        # For check command, a non-zero exit code can mean violations were found
        if is_check_command and process.returncode != 0 and process.stdout:
             return process.stdout

        # If check is True and command failed, CalledProcessError would have been raised
        if process.returncode == 0:
            return process.stdout

        # Handle other non-zero exit codes if needed
        logging.error(f"Ruff command failed unexpectedly with exit code {process.returncode}")
        logging.error(f"Ruff stderr: {process.stderr}")
        raise RuntimeError(f"Ruff command failed: {process.stderr}")

    except FileNotFoundError:
        logging.error("Ruff command not found. Is ruff installed and in your PATH?")
        raise
    except subprocess.CalledProcessError as e:
        logging.error(f"Ruff command failed with exit code {e.returncode}")
        logging.error(f"Ruff stdout: {e.stdout}")
        logging.error(f"Ruff stderr: {e.stderr}")
        raise RuntimeError(f"Ruff command failed: {e.stderr}") from e
    except UnicodeDecodeError as e:
        logging.error(f"Unicode decode error from ruff command: {e}")
        raise RuntimeError(f"Unicode decode error from ruff command: {e}") from e

def discover_rules():
    """Discovers all available ruff rules and their statuses."""
    output = _run_ruff_command(["rule", "--all", "--output-format", "json"])
    rules = json.loads(output)

    for rule in rules:
        if rule.get("deprecated"):
            rule["status"] = "deprecated"
        elif rule.get("removed"):
            rule["status"] = "removed"
        elif rule.get("preview"):
            rule["status"] = "preview"
        else:
            rule["status"] = "stable"

    return rules

def run_scan(directory):
    """Runs a ruff scan on the given directory and returns the results as JSON."""
    try:
        output = _run_ruff_command(["check", directory, "--output-format", "json", "--force-exclude", "--no-respect-gitignore"])
        return json.loads(output)
    except (RuntimeError, json.JSONDecodeError):
        return []

def run_scan_with_config(directory, config_data):
    """Runs a ruff scan with a temporary configuration."""
    scan_dir = os.path.dirname(directory) if not os.path.isdir(directory) else directory

    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".toml", dir=scan_dir) as temp_config:
        toml_string = tomlkit.dumps(config_data)
        temp_config.write(toml_string)
        temp_config_path = temp_config.name

    try:
        output = _run_ruff_command([
            "check",
            directory,
            "--output-format", "json",
            "--force-exclude",
            "--no-respect-gitignore",
            "--config", temp_config_path
        ])
        return json.loads(output)
    except (RuntimeError, json.JSONDecodeError):
        return []
    finally:
        os.unlink(temp_config_path)
