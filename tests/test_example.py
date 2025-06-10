import sys
from pathlib import Path

# Add the project root to the Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_project_structure():
    """
    Test that verifies the existence of key project directories.
    This demonstrates how to create a test that checks project structure.
    """
    # Check for essential directories
    assert (PROJECT_ROOT / "tests").exists(), "Tests directory should exist"
    assert (PROJECT_ROOT / "installer").exists(), (
        "Installer directory should exist"
    )
    assert (PROJECT_ROOT / "services").exists(), (
        "Services directory should exist"
    )

    # Check for essential files
    assert (PROJECT_ROOT / "install.py").exists(), "install.py should exist"
    assert (PROJECT_ROOT / "config.yaml").exists(), "config.yaml should exist"
    assert (PROJECT_ROOT / "pyproject.toml").exists(), (
        "pyproject.toml should exist"
    )


def test_config_yaml_structure():
    """
    Test that verifies the config.yaml file can be loaded and has expected structure.
    This demonstrates how to test configuration files.
    """
    import yaml

    config_path = PROJECT_ROOT / "config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Check that the config has the expected top-level keys
    assert isinstance(config, dict), "Config should be a dictionary"
    assert "admin_group_ip" in config, "Config should have admin_group_ip key"
