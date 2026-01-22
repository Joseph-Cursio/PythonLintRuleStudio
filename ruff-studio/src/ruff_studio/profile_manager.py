"""
Manages loading, parsing, and applying configuration profiles.
"""
import yaml
import os

def get_built_in_profiles():
    """Returns a list of available built-in profile names."""
    profile_dir = os.path.join(os.path.dirname(__file__), "profiles")
    return [f.replace(".yaml", "") for f in os.listdir(profile_dir) if f.endswith(".yaml")]

def load_profile(profile_name):
    """Loads and parses a YAML profile file."""
    profile_path = os.path.join(os.path.dirname(__file__), "profiles", f"{profile_name}.yaml")
    with open(profile_path, 'r') as f:
        return yaml.safe_load(f)
