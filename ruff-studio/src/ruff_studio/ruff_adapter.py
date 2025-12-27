import subprocess
import json

def discover_rules():
    """
    Discovers all available ruff rules.
    """
    result = subprocess.run(["ruff", "rule", "--all", "--output-format", "json"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to discover ruff rules: {result.stderr}")
    return json.loads(result.stdout)

def run_scan(path: str):
    """
    Runs a ruff scan on a given path.
    """
    result = subprocess.run(["ruff", "check", path, "--output-format", "json"], capture_output=True, text=True)
    # Ruff exits with 1 if it finds issues, so we can't just check for 0
    if result.returncode != 0 and result.returncode != 1:
        raise RuntimeError(f"Failed to run ruff scan: {result.stderr}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        # If there are no issues, ruff may not output valid json
        return []
