import subprocess
import json
import tempfile
import os
import tomlkit

def discover_rules():
    """
    Discovers all available ruff rules.
    """
    result = subprocess.run(["ruff", "rule", "--all", "--output-format", "json"], capture_output=True, text=True, encoding='utf-8')
    if result.returncode != 0:
        raise RuntimeError(f"Failed to discover ruff rules: {result.stderr}")
    return json.loads(result.stdout)

def run_scan(path: str):
    """
    Runs a ruff scan on a given path.
    """
    result = subprocess.run(["ruff", "check", path, "--output-format", "json"], capture_output=True, text=True, encoding='utf-8')
    # Ruff exits with 1 if it finds issues, so we can't just check for 0
    if result.returncode != 0 and result.returncode != 1:
        raise RuntimeError(f"Failed to run ruff scan: {result.stderr}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        # If there are no issues, ruff may not output valid json
        return []

def run_scan_with_config(path: str, config_data: dict):
    """
    Runs a ruff scan on a given path using a temporary config file.
    """
    with tempfile.TemporaryDirectory() as tempdir:
        temp_config_path = os.path.join(tempdir, "pyproject.toml")

        # Create a full TOML structure for the temporary file
        full_toml = {"tool": {"ruff": config_data}}

        with open(temp_config_path, "w", encoding='utf-8') as f:
            tomlkit.dump(full_toml, f)

        command = [
            "ruff", "check", path,
            "--output-format", "json",
            "--config", temp_config_path
        ]

        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')

        if result.returncode != 0 and result.returncode != 1:
            raise RuntimeError(f"Failed to run ruff scan with custom config: {result.stderr}")

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return []
