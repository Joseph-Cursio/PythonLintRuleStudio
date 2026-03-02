import tomlkit

def read_pyproject(path: str):
    """
    Reads a pyproject.toml file, preserving comments and formatting.
    """
    with open(path, "r") as f:
        return tomlkit.load(f)

def write_pyproject(path: str, data):
    """
    Writes to a pyproject.toml file, preserving comments and formatting.
    """
    with open(path, "w") as f:
        tomlkit.dump(data, f)

def read_pyproject_text(path: str):
    """Reads and returns the raw text of a pyproject.toml file."""
    with open(path, "r") as f:
        return f.read()

def get_pyproject_text(data):
    """Returns the pyproject data as a string."""
    return tomlkit.dumps(data)

def get_ruff_config(pyproject_data):
    """
    Extracts the ruff lint configuration from the pyproject data.
    Returns an empty dict if not found.
    """
    if pyproject_data is None:
        return {}
    return pyproject_data.get("tool", {}).get("ruff", {}).get("lint", {})

def update_ruff_config(pyproject_data, ruff_lint_config):
    """
    Updates the ruff lint configuration in the pyproject data.
    """
    tool_table = pyproject_data.setdefault("tool", tomlkit.table())
    ruff_table = tool_table.setdefault("ruff", tomlkit.table())
    ruff_table["lint"] = ruff_lint_config

def get_pylint_config(pyproject_data):
    """
    Extracts the pylint configuration from the pyproject data.
    Returns an empty dict if not found.
    """
    if pyproject_data is None:
        return {}
    # Pylint config can be under [tool.pylint] or [tool.pylint.messages_control]
    # For now, we'll assume a simple structure under [tool.pylint] for rule management
    return pyproject_data.get("tool", {}).get("pylint", {})

def update_pylint_config(pyproject_data, pylint_config):
    """
    Updates the pylint configuration in the pyproject data.
    """
    tool_table = pyproject_data.setdefault("tool", tomlkit.table())
    tool_table["pylint"] = pylint_config
