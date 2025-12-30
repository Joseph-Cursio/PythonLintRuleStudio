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
    Discovers and categorizes all ruff rules, with incremental caching.

    This function fetches the complete list of rules from ruff and then
    incrementally scrapes and caches the documentation for each rule.
    If the process is interrupted, it can resume where it left off on the
    next run.
    """
    version = get_ruff_version()
    cache_dir = os.path.expanduser("~/.cache/ruff-studio")
    cache_file = os.path.join(cache_dir, f"rules-v{version}-with-docs.json")

    # Load existing cache or initialize a new one
    categorized_rules = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                categorized_rules = json.load(f)
                logging.info(
                    f"Loaded {len(categorized_rules)} categories from cache."
                )
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Could not read cache file {cache_file}: {e}")
            categorized_rules = {}

    # Get the definitive list of all rules directly from ruff
    ruff_args = ["rule", "--all", "--output-format", "json"]
    all_rules_raw = json.loads(_run_ruff_command(ruff_args))

    # Create a quick lookup for existing rules in the cache
    cached_rules_lookup = {
        rule['code']: rule
        for category in categorized_rules.values()
        for rule in category.get('rules', [])
    }

    cache_updated = False
    for i, rule_data in enumerate(all_rules_raw):
        # Check if rule is already cached and has documentation
        if (rule_data['code'] in cached_rules_lookup and
                cached_rules_lookup[rule_data['code']].get('documentation')):
            continue

        # If not, scrape documentation and update the rule data
        logging.info(
            f"Scraping docs for '{rule_data['name']}' ({i+1}/{len(all_rules_raw)})..."
        )
        rule_data['documentation'] = scrape_rule_documentation(rule_data['name'])

        # Add status field
        if rule_data.get("deprecated"):
            rule_data["status"] = "deprecated"
        elif rule_data.get("removed"):
            rule_data["status"] = "removed"
        elif rule_data.get("preview"):
            rule_data["status"] = "preview"
        else:
            rule_data["status"] = "stable"

        # Add the updated rule to the categorized dictionary
        category_name = rule_data.get("linter", "Unknown")
        if category_name not in categorized_rules:
            match = re.match(r"[A-Z]+", rule_data["code"])
            prefix = match.group(0) if match else ""
            categorized_rules[category_name] = {"prefix": prefix, "rules": []}

        # Avoid duplicating rules if they are already in the category list
        category_rules = categorized_rules[category_name]["rules"]
        if not any(r['code'] == rule_data['code'] for r in category_rules):
            category_rules.append(rule_data)

        cache_updated = True

        # Write to cache after each new rule is processed
        try:
            os.makedirs(cache_dir, exist_ok=True)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(categorized_rules, f)
        except IOError as e:
            logging.warning(f"Could not write to cache file during update: {e}")

    if cache_updated:
        logging.info("Rule cache is now fully up to date.")
    else:
        logging.info("Rule cache was already up to date.")

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
