# **Developer Guide**

Welcome to the development team! This guide provides everything you need to get the project running on your local
machine for development and testing purposes.

## **Getting Started**

Follow these steps to set up your development environment.

### **1. Prerequisites**

Before you begin, ensure you have the following tools installed on your system:

* **Git**: For version control.
* **Python 3.13**: The project's runtime.
* **python3-apt**: Required for the AptManager module.
* **uv**: An extremely fast Python package and project manager. We use it to manage our virtual environments and
  dependencies.

**NOTE:** This project is developed on
x86_64 [Debian](https://www.debian.org/) [Trixie](https://www.debian.org/releases/trixie/). For
now, YMMV on other systems.

### **2. Fork and Clone**

First, create a fork of the main repository on GitHub. Then, clone your fork to your local machine:

```bash
git clone https://github.com/opentasmania/osm-osrm-server.git
cd osm-osrm-server
```

### **3. Environment Setup**

We use [uv](https://docs.astral.sh/uv/) to ensure a consistent development environment.

1. **Create a virtual environment:**
   ```bash
   uv venv
   ```
2. **Activate the virtual environment:**
    * On macOS and Linux:
        ```bash
        source .venv/bin/activate
        ```
    * On Windows:
        ```bash
        .venv\Scripts\activate
        ```
3. **Install dependencies:**
   Sync the environment with our project's requirements.
   ```bash
   uv pip sync requirements.txt
   ```

### **4. Configuration**

The server is configured using a YAML file.

1. Copy the configuration template to a new local file. This file is ignored by Git, so your local settings won't be
   committed.
   ```bash
   cp config.yaml config.local.yaml
   ```
2. Open `config.local.yaml` and adjust the settings (like database credentials and file paths) as needed for your local
   environment.

## **Project Architecture**

The project is organized into several key directories:

* `installer/`: Contains scripts for installing individual services (e.g., PostgreSQL, Nginx).
* `configure/`: Holds the logic for configuring those services after installation.
* `processors/`: This is where our core data processing logic lives. It's built on a new, modern architecture.
* `common/`: Shared utilities and helper functions used across the project.
  * `common/debian/`: Contains Debian-specific utilities, including the AptManager.
* `docs/`: Project documentation, including the plans and strategies that guide our work.
* `modular_bootstrap/`: Contains the self-contained bootstrap process for the modular setup script. This ensures all prerequisites are met before the script is executed.

### **Package Management with AptManager**

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

### **Modular Bootstrap Process**

The modular setup script (`setup_modular.py`) uses a self-contained bootstrap process to ensure all prerequisites are met before execution. This process is implemented in the `/modular_bootstrap` directory.

**Key components:**
- `mb_utils.py`: Common utilities for the bootstrap process
- `mb_apt.py`: Ensures the presence of the `python3-apt` package
- `mb_pydantic.py`: Ensures the presence of the `pydantic` and `pydantic-settings` packages
- `mb_build_tools.py`: Ensures the presence of build tools like `build-essential` and `python3-dev`
- `mb_lsb.py`: Ensures the presence of the `lsb-release` package
- `mb_util_linux.py`: Ensures the presence of the `util-linux` package
- `orchestrator.py`: Manages the execution of the individual prerequisite checks

The bootstrap process is automatically executed when running the `setup_modular.py` script. It checks for and installs any missing prerequisites before proceeding with the main configuration tasks.

For more details, see the [README.md](/bootstrap/README.md) in the `/modular_bootstrap` directory.

### **Setup Command**

The `install.py` script provides a `setup` command that allows you to configure components of the system after they have been installed. This command uses the `SetupOrchestrator` class to manage the configuration process.

**Usage:**
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

### **Install and Setup Command**

The `install.py` script also provides an `install setup` command that allows you to install a component or group and then immediately run the setup process for it. This is a convenient way to perform both steps in a single command.

**Usage:**
```bash
# Install and then configure a component
./install.py install setup postgres

# Install and then configure a group
./install.py install setup web_server
```

This command will:
1. Install the specified component or group using the `InstallerOrchestrator`
2. If installation is successful, run the setup process for the component or group using the `SetupOrchestrator`

### **Status Command**

The `install.py` script provides a `status` command that allows you to check the installation and configuration status of components. The command can display the status as a flat list or as a dependency tree.

**Usage:**
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

The tree view shows the interdependencies between components and provides both installation and setup status for each component. Components are organized based on their dependencies, with root components (those that don't depend on any other components) at the top level.

Example output:
```
Component dependency tree:
└── postgres: installed, configured
    ├── postgis: installed, configured
    └── osm_db: installed, not configured
        └── osrm: not installed
```

This visualization makes it easy to understand the relationships between components and identify any issues in the installation or configuration process.

The `setup` command will:
1. Load the configuration from `config.yaml`
2. Import all configurator modules from the `modular_setup/configurators` directory
3. Resolve dependencies between configurators to determine the order of execution
4. Execute each configurator in the correct order

Each configurator is responsible for configuring a specific component of the system, such as PostgreSQL, Apache, or Docker. Configurators are registered with the `ConfiguratorRegistry` using a decorator, similar to how installers are registered with the `InstallerRegistry`.

**Example configurator registration:**

```python
from installer.registry import ComponentRegistry
from installer.base_configurator import BaseConfigurator


@ComponentRegistry.register(
    name="postgres",
    metadata={
        "dependencies": [],
        "description": "Configures PostgreSQL for the OSM-OSRM server.",
    },
)
class PostgresConfigurator(BaseConfigurator):
# Implementation details...
```

To add a new configurator, create a new Python module in the `modular_setup/configurators` directory and register it with the `ConfiguratorRegistry` using the `@ConfiguratorRegistry.register` decorator.

### **Logging Guidelines**

For consistent logging across the project, we use a centralized logging configuration approach.

**Important:** All logging must be configured exclusively through the `setup_logging` function in `/common/core_utils.py`. This function is called once at the application's entry point in `main_map_server_entry` and sets up console and file logging for the entire application.

Key principles:
1. **Never** call `logging.basicConfig()` or other logging configuration functions in your modules.
2. **Always** acquire a logger using the standard Python mechanism: `import logging; logger = logging.getLogger(__name__)`.
3. For custom logging handlers (like `TuiLogHandler`), integrate them with the central logging system rather than creating separate configurations.
4. **All logging automatically includes symbols** based on the log level (e.g., ℹ️ for info, ⚠️ for warning, ❌ for error). These symbols are defined in `SYMBOLS_DEFAULT` in `setup/config_models.py`.

Example usage:

```python
import logging

# Get a logger for the current module
logger = logging.getLogger(__name__)

# Use the logger - symbols are automatically added based on log level
logger.info("This is an informational message")  # Will include ℹ️ symbol
logger.warning("This is a warning message")  # Will include ⚠️ symbol
logger.error("This is an error message")  # Will include ❌ symbol

# For user-facing messages that require consistent formatting
from common.command_utils import log_map_server

log_map_server("Step completed successfully", "info", current_logger=logger, app_settings=app_settings)
```

Available symbols:
- `info`: ℹ️ - For informational messages
- `warning`: ⚠️ - For warning messages
- `error`: ❌ - For error messages
- `critical`: 🔥 - For critical error messages
- `debug`: 🐛 - For debug messages
- `success`: ✅ - For success messages
- `step`: ➡️ - For step indicators
- `gear`: ⚙️ - For configuration or processing operations
- `package`: 📦 - For package-related operations
- `rocket`: 🚀 - For deployment or startup operations
- `sparkles`: ✨ - For cleanup or completion operations

### **Core Design Principle: Pluggable Processors**

To handle a wide variety of transit data, we have adopted a modular, pluggable architecture.

* **Static Data Pipeline**: The ETL (Extract, Transform, Load) pipeline for static data like GTFS and NeTEx uses
  independent processor plugins for each format. All data is transformed into a single **Canonical Database Schema**,
  ensuring a consistent data structure in our PostgreSQL database.
* **Real-time Data Service**: Similarly, real-time feeds like GTFS-RT and SIRI are handled by dedicated plugins. Each
  plugin transforms its data into a standard **Canonical Data Model** before it's cached and served to the frontend.

Understanding this principle is key to working with the data processing parts of the application. For a deep dive,
please read the strategy documents:

* [Static Strategy](docs/strategies/StaticStrategy.md)
* [Realtime Strategy](docs/strategies/RealTimeStrategy.md)

## **Development Workflow**

### **Running Tests**

We use [pytest](https://pytest.org/) for testing. To run the full test suite, execute:

```bash
pytest
```

Please ensure all tests pass before submitting a pull request.

### **Code Style & Linting**

We use **[Ruff](https://docs.astral.sh/ruff/)** for lightning-fast code formatting and linting. Before committing your
code, please run:

```bash
# Format your code
ruff format .

# Check for linting errors
ruff check .
```

### **Running a Data Processor**

To run the static data ETL pipeline, you can execute the main orchestrator script:

```bash
python processors/run_static_etl.py
```

This script will read the `static_feeds` from your `config.local.yaml` and run the appropriate processor plugins.

## **Contributing**

We welcome contributions! Please follow these steps:

1. **Find an Issue**: Look for open tasks in
   the [issue tracker](https://gitlab.com/opentasmania/osm-osrm-server/-/issues), or in the [tasks](docs/tasks.md)
   documentation file. This file is prioritized based on our main improvement plan.
2. **Create a Branch**: Create a new feature branch for your work.
   ```bash
   git checkout -b your-feature-name
   ```
3. **Develop**: Make your changes, write tests, and ensure all checks pass.
4. **Submit a Pull Request**: Push your branch to your fork and open
   a [pull request](https://gitlab.com/opentasmania/osm-osrm-server/-/merge_requests)
   against the main repository. Provide a clear description of the changes you've made.

For more detailed policies on contributions, please review [Contributing](docs/CONTRIBUTING.md). To understand the
project's long-term vision, refer to [the plan](docs/plan.md)
