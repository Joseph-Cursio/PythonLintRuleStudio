"""
Manages caching for data that is expensive to compute, like rule discovery.
"""
import json
from pathlib import Path

# Define a user-specific cache directory to avoid cluttering the project
CACHE_DIR = Path.home() / ".ruff_studio" / "cache"
CACHE_FILE = CACHE_DIR / "rule_cache.json"

def _ensure_cache_dir_exists():
    """Creates the cache directory if it doesn't exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _read_cache_file():
    """Reads the entire cache file into a dictionary."""
    _ensure_cache_dir_exists()
    if not CACHE_FILE.is_file():
        return {}
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def _write_cache_file(data):
    """Writes a dictionary to the cache file."""
    _ensure_cache_dir_exists()
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except IOError:
        # If writing fails, we don't want to crash the app
        pass

def get_cache(key):
    """
    Retrieves a value from the cache by its key.

    Args:
        key (str): The key for the cached item (e.g., 'ruff_rules').

    Returns:
        The cached data, or None if not found.
    """
    cache_data = _read_cache_file()
    return cache_data.get(key)

def set_cache(key, value):
    """
    Sets a value in the cache for a given key.

    Args:
        key (str): The key for the cached item.
        value: The data to cache.
    """
    cache_data = _read_cache_file()
    cache_data[key] = value
    _write_cache_file(cache_data)
