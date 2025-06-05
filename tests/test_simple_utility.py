import sys
from pathlib import Path

# Add the project root to the Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_path_exists():
    """
    A simple test to verify that the project root path exists.
    This demonstrates how to create and run a basic test.
    """
    assert PROJECT_ROOT.exists(), (
        f"Project root path {PROJECT_ROOT} does not exist"
    )


def test_simple_addition():
    """
    A trivial test to demonstrate test assertions.
    """
    assert 1 + 1 == 2, "Basic arithmetic failed"
