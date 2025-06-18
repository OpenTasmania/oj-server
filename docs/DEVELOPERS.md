# OSM-OSRM Server Development Guidelines

This document provides essential information for developers working on the OSM-OSRM Server project. It includes
build/configuration instructions, testing information, and additional development guidelines.

## Build/Configuration Instructions

### Environment Setup

1. **Python Requirements**:
    - Python 3.13 is required for this project
    - The project uses `uv` for package management and virtual environment

2. **Initial Setup**:
   ```bash
   # Clone the repository
   git clone https://gitlab.com/opentasmania/osm-osrm-server.git
   cd osm-osrm-server

   # Run the install script which will set up uv and create a virtual environment
   python3 install.py
   ```

3. **Configuration**:
    - The main configuration file is `config.yaml` in the project root
    - You can generate a preseed YAML configuration using:
      ```bash
      python3 install.py --generate-preseed-yaml
      ```

### Installation Process

The installation process is handled by the `install.py` script and the modules in the `installer` directory:

1. **Prerequisites Installation**:
   ```bash
   python3 install.py --prereqs
   ```

2. **Services Installation**:
   ```bash
   python3 install.py --services
   ```

3. **Data Preparation**:
   ```bash
   python3 install.py --data
   ```

4. **Full Installation**:
   ```bash
   python3 install.py --full -v your-domain.example.com
   ```

## Project Architecture

The project is organized into several key directories:

* `bootstrap/`: Contains the self-contained bootstrap process for the modular setup script.
* `installer/`: Contains components (individual services)
  * `components/`: Contains installer and configure code for a various component.
  * `processors/`: Where our core data processing logic lives.
* `common/`: Shared utilities and helper functions used across the project.
  * `common/debian/`: Contains Debian-specific utilities, including the AptManager.
* `docs/`: Project documentation, including the plans and strategies that guide our work.

### Package Management with AptManager

For Debian package management, we use the `AptManager` class located in `common/debian/apt_manager.py`. This provides a centralized, consistent interface for all apt operations.

**Important:** All apt package operations must be handled exclusively through the `AptManager` module. Direct calls to `apt-get` or similar commands should be avoided.

Example usage:

```python
from common.debian.apt_manager import AptManager

# Initialize with an optional logger
apt_manager = AptManager(logger=your_logger)

# Install packages
apt_manager.install(["package1", "package2"], update_first=True)

# Add a repository
apt_manager.add_repository("deb http://example.com/debian stable main")

# Add a GPG key
apt_manager.add_gpg_key_from_url("https://example.com/key.gpg", "/etc/apt/keyrings/example.gpg")
```

### Installer Commands

The `install.py` script provides several commands for managing the installation and configuration of components:

#### Setup Command

```bash
# Configure all components
./install.py setup

# Configure a specific component
./install.py setup postgres

# Check if components are already configured
./install.py setup --status

# Force reconfiguration even if already configured
./install.py setup --force

# Show what would be configured without actually doing it
./install.py setup --dry-run
```

#### Install and Setup Command

```bash
# Install and then configure a component
./install.py install setup postgres

# Install and then configure a group
./install.py install setup web_server
```

#### Status Command

```bash
# Check status of all components
./install.py status

# Check status of specific components
./install.py status postgres apache

# Display status as a dependency tree
./install.py status --tree

# Display status of specific components as a dependency tree
./install.py status postgres apache --tree
```

### Logging Guidelines

For consistent logging across the project, we use a centralized logging configuration approach.

**Important:** All logging must be configured exclusively through the `setup_logging` function in `/common/core_utils.py`. This function is called once at the application's entry point and sets up console and file logging for the entire application.

Key principles:
1. **Never** call `logging.basicConfig()` or other logging configuration functions in your modules.
2. **Always** acquire a logger using the standard Python mechanism: `import logging; logger = logging.getLogger(__name__)`.
3. For custom logging handlers, integrate them with the central logging system rather than creating separate configurations.

Example usage:

```python
import logging

# Get a logger for the current module
logger = logging.getLogger(__name__)

# Use the logger
logger.info("This is an informational message")
logger.warning("This is a warning message")
logger.error("This is an error message")

# For user-facing messages that require consistent formatting
from common.command_utils import log_map_server

log_map_server("Step completed successfully", "info", current_logger=logger, app_settings=app_settings)
```

### Core Design Principle: Pluggable Processors

To handle a wide variety of transit data, the project has adopted a modular, pluggable architecture:

* **Static Data Pipeline**: The ETL (Extract, Transform, Load) pipeline for static data like GTFS and NeTEx uses
  independent processor plugins for each format. All data is transformed into a single **Canonical Database Schema**,
  ensuring a consistent data structure in our PostgreSQL database.
* **Real-time Data Service**: Similarly, real-time feeds like GTFS-RT and SIRI are handled by dedicated plugins. Each
  plugin transforms its data into a standard **Canonical Data Model** before it's cached and served to the frontend.

For more details, see the strategy documents in the `docs/strategies/` directory.

## Testing Information

### Test Configuration

The project uses pytest for testing. Test configuration is defined in the `pyproject.toml` file:

```toml
[tool.pytest.ini_options]
addopts = """
        --cov-report html:cover/coverage_html
        --cov-report json:cover/coverage.json
        --cov-report xml:cover/coverage.xml
        """

[tool.coverage.report]
show_missing = true
omit = ["/etc/python3.13/sitecustomize.py", ]

[tool.coverage.xml]
output = "coverage.xml"
```

### Running Tests

To run all tests:

```bash
python -m pytest
```

To run specific tests:

```bash
python -m pytest tests/test_specific_file.py
```

To run tests with verbose output:

```bash
python -m pytest -v
```

To run tests with coverage:

```bash
python -m pytest --cov=.
```

### Adding New Tests

1. Create a new test file in the `tests` directory with a name starting with `test_`.
2. Import necessary modules and define test functions with names starting with `test_`.
3. Use assertions to verify expected behavior.

Example:

```python
# tests/test_example.py
import sys
from pathlib import Path

# Add the project root to the Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_example():
    """
    Example test function.
    """
    # Setup
    expected_result = True

    # Execute
    actual_result = True  # Replace with actual function call

    # Assert
    assert actual_result == expected_result, "Test failed"
```

## Additional Development Information

### Code Style

The project follows PEP 8 guidelines for Python code. Code formatting and linting are handled by ruff:

```toml
[tool.ruff]
line-length = 78
preview = true

[tool.ruff.lint]
select = [
    "E1", # Indentation
    "E2", # Whitespace
    "E3", # Blank lines
    "E4", # Import formatting
    "E5", # Line length
    "E7", # Statement, imports, expression formatting
    "E9", # Syntax errors
    "F", # PyFlakes
    "B", # Bugbear
    "I"  # isort rules
]

ignore = [
    "E501"  # Line length will be handled by ruff format
]
```

### Type Checking

The project uses mypy for type checking:

```toml
[tool.mypy]
python_version = "3.13"
warn_return_any = true
warn_unused_configs = true
exclude = ['\.git', '\.venv', 'build', 'dist']
```

### Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality. To install pre-commit hooks:

```bash
uv run pre-commit install
```

### Contribution Workflow

1. Fork the repository
2. Create a new branch for your feature or bug fix
3. Make your changes
4. Run tests to ensure your changes don't break existing functionality
5. Submit a merge request

For more detailed information, refer to the [CONTRIBUTING.md](CONTRIBUTING.md) file.
