import os
import queue
import threading
import logging
from . import ruff_adapter, pylint_adapter, config_manager, workspace_analyzer


class StudioController:
    """
    Handles application state and coordination between the UI and backend logic.
    """

    def __init__(self, db_path="ruff_studio.db"):
        self.current_directory = None
        self.pyproject_path = None
        self.pyproject_data = None

        self.enabled_rules = set()
        self.all_rules = {}
        self.staged_changes = {}
        self.base_scan_results = []

        self.navigable_items = []
        self.navigable_index = 0
        self.selected_item = None

        self.analyzer = workspace_analyzer.WorkspaceAnalyzer(db_path)
        self.queue = queue.Queue()

        # Callbacks for UI updates
        self.on_state_changed = None  # Called when major state changes
        self.on_scan_finished = None  # Called when a scan result is ready

    def set_directory(self, directory):
        """Sets the active directory and initializes path data."""
        self.current_directory = directory
        self.pyproject_path = os.path.join(directory, "pyproject.toml")
        self.staged_changes = {}

        if os.path.exists(self.pyproject_path):
            try:
                self.pyproject_data = config_manager.read_pyproject(self.pyproject_path)
            except Exception as e:
                logging.error(f"Error reading pyproject.toml: {e}")
                self.pyproject_data = None
        else:
            self.pyproject_data = None

    def run_in_thread(self, func, command, *args):
        """Helper to run a function in a background thread."""
        thread = threading.Thread(target=func, args=(command, *args), daemon=True)
        thread.start()

    def discover_rules_worker(self, command):
        """Background worker for rule discovery."""
        try:
            ruff_rules = ruff_adapter.discover_rules()
            pylint_rules = pylint_adapter.discover_rules()

            # Combine them
            combined = ruff_rules.copy()
            for cat, data in pylint_rules.items():
                combined[f"Pylint: {cat}"] = data

            self.queue.put((command, combined))
        except Exception as e:
            logging.error(f"Error in rule discovery: {e}")
            self.queue.put(("error", str(e)))

    def run_full_scan_worker(self, command, directory):
        """Background worker for workspace scanning."""
        try:
            ruff_cfg, pylint_cfg = self.get_effective_configs()
            results = self.analyzer.run_full_scan(
                directory, config={"ruff": ruff_cfg, "pylint": pylint_cfg}
            )
            self.queue.put((command, results))
        except Exception as e:
            logging.error(f"Error in scan worker: {e}")
            self.queue.put(("error", str(e)))

    def get_scan_history(self):
        return self.analyzer.get_scan_history()

    def get_author_stats(self):
        return self.analyzer.get_author_stats()

    def get_rule_hotspots(self):
        return self.analyzer.get_rule_hotspots()

    def get_violation_trend(self):
        return self.analyzer.get_total_violations_trend()

    def get_effective_configs(self):
        """Calculates final ruff/pylint configs based on staged changes."""
        if self.pyproject_data is None:
            return {}, {}

        # --- Ruff ---
        ruff_config = config_manager.get_ruff_config(self.pyproject_data).copy()
        ruff_select = set(ruff_config.get("select", []))
        ruff_ignore = set(ruff_config.get("ignore", []))

        # --- Pylint ---
        pylint_config = config_manager.get_pylint_config(self.pyproject_data).copy()
        pylint_disable = set(pylint_config.get("disable", []))
        pylint_enable = set(pylint_config.get("enable", []))

        for code, state in self.staged_changes.items():
            if self.is_pylint_rule(code):
                if state == "select":
                    pylint_enable.add(code)
                    pylint_disable.discard(code)
                elif state == "ignore":
                    pylint_disable.add(code)
                    pylint_enable.discard(code)
                elif state == "default":
                    pylint_disable.discard(code)
                    pylint_enable.discard(code)
            else:  # Ruff
                if state == "select":
                    ruff_select.add(code)
                    ruff_ignore.discard(code)
                elif state == "ignore":
                    ruff_ignore.add(code)
                    ruff_select.discard(code)
                elif state == "default":
                    ruff_select.discard(code)
                    ruff_ignore.discard(code)

        ruff_config["select"] = sorted(list(ruff_select))
        ruff_config["ignore"] = sorted(list(ruff_ignore))

        if pylint_disable:
            pylint_config["disable"] = sorted(list(pylint_disable))
        elif "disable" in pylint_config:
            del pylint_config["disable"]

        if pylint_enable:
            pylint_config["enable"] = sorted(list(pylint_enable))
        elif "enable" in pylint_config:
            del pylint_config["enable"]

        return ruff_config, pylint_config

    def is_pylint_rule(self, code):
        """Helper to distinguish rule origins."""
        # Pylint rules in our model are either C, R, W, E, F (one char)
        # or the Pylint names. A simple check for the prefix:
        return any(code.startswith(p) for p in ["C", "R", "W", "I"]) or len(code) > 5

    def get_color_for_prefix(self, prefix):
        """Returns a color hex code based on rule severity/type."""
        prefix = prefix.upper()
        # Reddish for Errors/Pyflakes/Bugbear
        if any(prefix.startswith(p) for p in ["E", "F", "B", "ERR"]):
            return ("#f44336", "#ef5350")
        # Amber for Warnings/Annotations
        if any(prefix.startswith(p) for p in ["W", "ANN", "WARN"]):
            return ("#ff9800", "#ffb74d")
        # Blue for Conventions/Pylint Convention/Refactor
        if any(prefix.startswith(p) for p in ["C", "PL", "CONV", "R"]):
            return ("#2196f3", "#64b5f6")
        # Green for Style/Imports/Naming/Performance
        if any(prefix.startswith(p) for p in ["I", "D", "N", "PERF", "S"]):
            return ("#4caf50", "#81c784")
        return ("#9e9e9e", "#bdbdbd")  # Gray for others

    def get_explicit_rule_state(self, code, ruff_config, pylint_config=None):
        """Determines if a rule is explicitly select/ignore/default."""
        if self.is_pylint_rule(code):
            if pylint_config is not None:
                if code in pylint_config.get("disable", []):
                    return "ignore"
                if code in pylint_config.get("enable", []):
                    return "select"
            return "default"
        else:
            if code in ruff_config.get("select", []):
                return "select"
            if code in ruff_config.get("ignore", []):
                return "ignore"
            return "default"

    def get_effective_rule_state(self, rule_code, category_prefix):
        """Calculates the final boolean on/off state of a rule."""
        if rule_code in self.staged_changes:
            state = self.staged_changes[rule_code]
            if state == "select":
                return True
            if state == "ignore":
                return False

        if category_prefix in self.staged_changes:
            state = self.staged_changes[category_prefix]
            if state == "select":
                return True
            if state == "ignore":
                return False

        # Fallback to current saved config
        ruff_config = config_manager.get_ruff_config(self.pyproject_data)
        pylint_config = config_manager.get_pylint_config(self.pyproject_data)

        if self.is_pylint_rule(rule_code):
            # Pylint is default-on
            return rule_code not in pylint_config.get("disable", [])
        else:
            # Ruff requires explicit enablement
            enabled = self._get_ruff_rules_from_config(ruff_config)
            return rule_code in enabled

    def _get_ruff_rules_from_config(self, ruff_config):
        """Internal helper for ruff rule resolution."""
        select = ruff_config.get("select", [])
        ignore = ruff_config.get("ignore", [])
        enabled = set()

        # We need to iterate over all known rules to see which ones match
        for category_data in self.all_rules.values():
            if category_data.get("is_pylint"):
                continue
            for rule in category_data["rules"]:
                rc = rule["code"]
                # Rule is enabled if it matches a select prefix AND
                # doesn't match a more specific ignore prefix
                is_selected = any(rc.startswith(s) for i, s in enumerate(select))
                is_ignored = any(rc.startswith(ig) for i, ig in enumerate(ignore))

                if is_selected and not is_ignored:
                    enabled.add(rc)
        return enabled
