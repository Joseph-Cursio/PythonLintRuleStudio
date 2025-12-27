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
