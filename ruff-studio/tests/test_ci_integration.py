import yaml
from ruff_studio import ci_integration


def test_generate_pre_commit_config():
    """Tests generating a pre-commit configuration."""
    ruff_version = "0.1.0"
    yaml_content = ci_integration.generate_pre_commit_config(ruff_version)

    # Parse back the YAML to verify structure
    config = yaml.safe_load(yaml_content)

    assert "repos" in config
    assert len(config["repos"]) == 1
    assert config["repos"][0]["repo"] == "https://github.com/astral-sh/ruff-pre-commit"
    assert config["repos"][0]["rev"] == f"v{ruff_version}"
    assert config["repos"][0]["hooks"][0]["id"] == "ruff"
