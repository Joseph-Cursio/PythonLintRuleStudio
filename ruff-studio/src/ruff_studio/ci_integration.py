"""
Handles the generation of CI/CD and pre-commit configurations.
"""

import yaml


def generate_pre_commit_config(ruff_version):
    """
    Generates the content for a .pre-commit-config.yaml file based on the
    current ruff version.
    """
    config = {
        "repos": [
            {
                "repo": "https://github.com/astral-sh/ruff-pre-commit",
                "rev": f"v{ruff_version}",
                "hooks": [{"id": "ruff", "args": ["--fix"]}, {"id": "ruff-format"}],
            }
        ]
    }

    # Use yaml.dump to convert the Python dict to a YAML string
    # default_flow_style=False ensures lists and dicts are block-style
    return yaml.dump(config, default_flow_style=False, sort_keys=False)
