import os
import pytest
from ruff_studio import profile_manager

def test_get_built_in_profiles():
    """Tests that built-in profiles are correctly identified."""
    profiles = profile_manager.get_built_in_profiles()
    assert isinstance(profiles, list)
    assert "standard" in profiles
    assert "strict" in profiles

def test_load_profile():
    """Tests loading a profile by name."""
    profile = profile_manager.load_profile("standard")
    assert isinstance(profile, dict)
    assert "profile" in profile
    assert "rules" in profile["profile"]

def test_compare_profiles():
    """Tests comparing two profiles."""
    diff = profile_manager.compare_profiles("standard", "strict")
    assert isinstance(diff, dict)
    assert "select_only_in_1" in diff
    assert "select_only_in_2" in diff
    assert "common_select" in diff
    
    # Check for some expected differences based on common knowledge of standard/strict profiles
    # or just that the result is a dict with lists.
    assert isinstance(diff["select_only_in_2"], list)
