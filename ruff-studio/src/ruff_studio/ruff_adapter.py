import subprocess
import json
import logging
import tomlkit
import tempfile
import os
import re
import requests
from bs4 import BeautifulSoup

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


def get_ruff_version():
    """Gets the current ruff version."""
    output = _run_ruff_command(["--version"])
    return output.strip().split(" ")[1]


def scrape_rule_documentation(rule_name):
    """Scrapes the documentation for a given rule from the ruff website."""
    url = f"https://docs.astral.sh/ruff/rules/{rule_name}/"
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        content_div = soup.find("article", class_="md-content__inner")
        if not content_div:
            return None

        sections = ["What it does", "Why is this bad?", "Example"]
        doc_parts = []
        for section in sections:
            header = content_div.find("h2", string=section)
            if header:
                doc_parts.append(f"### {section}")
                next_node = header.find_next_sibling()
                while next_node and next_node.name != "h2":
                    doc_parts.append(next_node.get_text())
                    next_node = next_node.find_next_sibling()

        return "\n".join(doc_parts)

    except requests.RequestException as e:
        logging.warning(f"Could not fetch documentation for rule {rule_name}: {e}")
        return None


def discover_rules():
    """Discovers and categorizes all ruff rules, with caching."""
    version = get_ruff_version()
    cache_dir = os.path.expanduser("~/.cache/ruff-studio")
    cache_file = os.path.join(cache_dir, f"rules-v{version}.json")

    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Could not read cache file {cache_file}: {e}")

    output = _run_ruff_command(["rule", "--all", "--output-format", "json"])
    rules = json.loads(output)

    categorized_rules = {}
    for rule in rules:
        rule['documentation'] = scrape_rule_documentation(rule['name'])
        if rule.get("deprecated"):
            rule["status"] = "deprecated"
        elif rule.get("removed"):
            rule["status"] = "removed"
        elif rule.get("preview"):
            rule["status"] = "preview"
        else:
            rule["status"] = "stable"

        category_name = rule.get("linter", "Unknown")
        if category_name not in categorized_rules:
            match = re.match(r"[A-Z]+", rule["code"])
            prefix = match.group(0) if match else ""
            categorized_rules[category_name] = {"prefix": prefix, "rules": []}

        categorized_rules[category_name]["rules"].append(rule)

    try:
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(categorized_rules, f)
    except IOError as e:
        logging.warning(f"Could not write cache file {cache_file}: {e}")

    return categorized_rules

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
