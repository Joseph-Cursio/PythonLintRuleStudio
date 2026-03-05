"""
Manages loading, parsing, and applying configuration profiles.
"""

import yaml
import os


def get_built_in_profiles():
    """Returns a list of available built-in profile names."""
    profile_dir = os.path.join(os.path.dirname(__file__), "profiles")
    return [
        f.replace(".yaml", "") for f in os.listdir(profile_dir) if f.endswith(".yaml")
    ]


def load_profile(profile_name):
    """Loads and parses a YAML profile file."""
    profile_path = os.path.join(
        os.path.dirname(__file__), "profiles", f"{profile_name}.yaml"
    )
    with open(profile_path, "r") as f:
        return yaml.safe_load(f)


def compare_profiles(profile1_name, profile2_name):
    """
    Compares two profiles and returns a dictionary detailing the differences
    in their ruff rule configurations.
    """
    profile1_data = load_profile(profile1_name)
    profile2_data = load_profile(profile2_name)

    p1_rules = profile1_data.get("profile", {}).get("rules", {}).get("ruff", {})
    p2_rules = profile2_data.get("profile", {}).get("rules", {}).get("ruff", {})

    p1_select = set(p1_rules.get("select", []))
    p1_ignore = set(p1_rules.get("ignore", []))
    p2_select = set(p2_rules.get("select", []))
    p2_ignore = set(p2_rules.get("ignore", []))

    return {
        "select_only_in_1": sorted(list(p1_select - p2_select)),
        "select_only_in_2": sorted(list(p2_select - p1_select)),
        "ignore_only_in_1": sorted(list(p1_ignore - p2_ignore)),
        "ignore_only_in_2": sorted(list(p2_ignore - p1_ignore)),
        "common_select": sorted(list(p1_select & p2_select)),
        "common_ignore": sorted(list(p1_ignore & p2_ignore)),
    }
