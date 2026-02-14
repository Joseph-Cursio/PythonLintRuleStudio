import subprocess
import json
import logging
import tomlkit
import tempfile
import os
import re
import requests
from bs4 import BeautifulSoup
from . import cache_manager

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
        logging.error(
            f"Ruff command failed unexpectedly with exit code {process.returncode}"
        )
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
                # Add a blank line for separation if content already exists
                if doc_parts:
                    doc_parts.append("")
                doc_parts.append(f"--- {section.upper()} ---")
                next_node = header.find_next_sibling()
                while next_node and next_node.name != "h2":
                    text_content = next_node.get_text().strip()
                    if text_content:
                        doc_parts.append(text_content)
                    next_node = next_node.find_next_sibling()

        return "\n".join(doc_parts)

    except requests.RequestException as e:
        logging.warning(f"Could not fetch documentation for rule {rule_name}: {e}")
        return None

def discover_rules():
    """
    Discovers and categorizes all ruff rules, using a cache to speed up
    subsequent runs.
    """
    version = get_ruff_version()
    cache_key = "ruff_rules"
    cached_data = cache_manager.get_cache(cache_key)

    if cached_data and cached_data.get("version") == version:
        logging.info(f"Loaded ruff rules from cache for version {version}.")
        return cached_data.get("rules", {})

    logging.info("No valid cache found for ruff rules. Discovering from scratch.")

    # Get the definitive list of all rules directly from ruff
    ruff_args = ["rule", "--all", "--output-format", "json"]
    all_rules_raw = json.loads(_run_ruff_command(ruff_args))

    categorized_rules = {}
    for i, rule_data in enumerate(all_rules_raw):
        logging.info(
            f"Processing ruff rule '{rule_data['name']}' ({i+1}/{len(all_rules_raw)})..."
        )
        # Add status field
        if rule_data.get("deprecated"):
            rule_data["status"] = "deprecated"
        elif rule_data.get("removed"):
            rule_data["status"] = "removed"
        elif rule_data.get("preview"):
            rule_data["status"] = "preview"
        else:
            rule_data["status"] = "stable"

        # Documentation scraping is removed for performance.
        # This could be added back as a background process or on-demand.
        rule_data['documentation'] = None

        category_name = rule_data.get("linter", "Unknown")
        if category_name not in categorized_rules:
            match = re.match(r"[A-Z]+", rule_data["code"])
            prefix = match.group(0) if match else ""
            categorized_rules[category_name] = {"prefix": prefix, "rules": []}

        categorized_rules[category_name]["rules"].append(rule_data)

    # Store the newly discovered rules in the cache
    cache_manager.set_cache(cache_key, {"version": version, "rules": categorized_rules})
    logging.info(f"Ruff rules for version {version} have been cached.")

    return categorized_rules

def run_scan(directory):
    """Runs a ruff scan on the given directory and returns the results as JSON."""
    try:
        ruff_args = [
            "check", directory, "--output-format", "json",
            "--force-exclude", "--no-respect-gitignore"
        ]
        output = _run_ruff_command(ruff_args)
        return json.loads(output)
    except (RuntimeError, json.JSONDecodeError):
        return []

def run_scan_with_config(directory, config_data):
    """Runs a ruff scan with a temporary configuration."""
    scan_dir = os.path.dirname(directory) if not os.path.isdir(directory) else directory

    with tempfile.NamedTemporaryFile(
        mode="w+", delete=False, suffix=".toml", dir=scan_dir
    ) as temp_config:
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

def get_default_rules():
    """
    Determines the default set of enabled rules by running ruff on a dummy file.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        dummy_file = os.path.join(temp_dir, "dummy.py")
        with open(dummy_file, "w") as f:
            f.write("import os")

        try:
            output = _run_ruff_command(["check", dummy_file, "--show-settings"])

            # Use regex to find the linter.rules.enabled list
            match = re.search(r"linter\.rules\.enabled = \[\s*([^]]+?)\s*\]", output, re.DOTALL)
            if not match:
                return set()

            # Extract the content of the list
            rules_content = match.group(1)

            # Find all rule codes within the content
            rule_codes = re.findall(r"\b([A-Z]{1,4}[0-9]{3,4})\b", rules_content)

            return set(rule_codes)

        except (RuntimeError, FileNotFoundError):
            return set()
