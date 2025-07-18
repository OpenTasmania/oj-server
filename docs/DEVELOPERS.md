# Open Journey Server Development Guidelines

This document provides essential information for developers working on the Open Journey Server project. It covers the development environment, deployment process, and project architecture.

## 1. Development Environment Setup

1.  **Clone the Repository:**
    ```bash
    git clone https://gitlab.com/opentasmania/oj-server.git
    cd oj-server
    ```

2.  **Python Environment:** The project uses `uv` for managing Python dependencies.
    ```bash
    # Activate the virtual environment (if you have one)
    # or set up a new one with uv
    uv venv
    source .venv/bin/activate
    uv pip install -r requirements.txt
    ```

3.  **Pre-commit Hooks:** Install the pre-commit hooks to ensure code quality and style consistency.
    ```bash
    uv run pre-commit install
    ```

## 2. Kubernetes-Based Deployment

The primary method for deploying the OJ Server is via a Flask-based application that provides both a web interface and a command-line interface (CLI).

*   **Web Interface:**
    1.  Start the Flask development server:
        ```bash
        FLASK_APP=installer_app/app.py flask run
        ```
    2.  Open your web browser and navigate to `http://127.0.0.1:5000`.
    3.  Use the web interface to deploy, destroy, or build the application components.

*   **Command-Line Interface (CLI):**
    The CLI provides the same functionality as the web interface.
    ```bash
    python3 -m installer_app.cli --help
    ```
    This will display a list of available commands and options.

    **Example: Deploy to a local environment**
    ```bash
    python3 -m installer_app.cli deploy --env local
    ```

For more details, refer to the main `README.md`.

## 3. Project Architecture

The project is organized into several key directories:

*   `kubernetes/`: Contains all Kubernetes manifests, organized by components and overlays (`local`, `production`) using `kustomize`.
*   `installer/`: Contains the Python source code for the Flask-based installer application.
*   `common/`: Shared Python utilities and helper functions used across the project.
*   `docs/`: Project documentation, including plans, strategies, and developer guides.
*   `processors/`: Contains the ETL logic for processing static and real-time transit data.

### Core Design Principle: Pluggable Processors

To handle a wide variety of transit data, the project uses a modular, pluggable architecture for both static and real-time data.

*   **Static Data Pipeline:** An ETL pipeline uses independent processor plugins for each data format (e.g., GTFS, NeTEx). All data is transformed into a single **Canonical Database Schema**, ensuring a consistent data structure in PostGIS.
*   **Real-time Data Service:** A continuously running service uses dedicated plugins for each real-time feed (e.g., GTFS-RT, SIRI). Each plugin transforms its data into a standard **Canonical Data Model** before it's cached and served via an API.

This architecture decouples the core application from the complexities of individual data formats. For more details, see the strategy documents in `docs/strategies/`.

## 4. Creating a Data Processor

The Open Journey Server uses a pluggable processor architecture to handle different static data formats (like GTFS, NeTEx, etc.). This is managed by the `ProcessorInterface` abstract base class, which ensures all data processors follow a consistent Extract, Transform, and Load (ETL) pattern.

To add support for a new data format, you need to create a new processor class that inherits from `common.processor_interface.ProcessorInterface` and implement its abstract methods.

### The `ProcessorInterface` Contract

Any new processor must implement the following properties and methods:

*   **`processor_name` (property)**: A unique string name for your processor (e.g., `"GTFS"`).
*   **`supported_formats` (property)**: A list of file extensions your processor can handle (e.g., `['.zip', '.xml']`).
*   **`validate_source(self, source_path)`**: A method that returns `True` if the given `source_path` is a valid file for this processor.
*   **`extract(self, source_path, **kwargs)`**: Reads the data from the `source_path` and returns it in a raw format (e.g., a dictionary of dataframes).
*   **`transform(self, raw_data, source_info)`**: Takes the raw data from `extract` and transforms it into the project's canonical data model.
*   **`load(self, transformed_data)`**: Loads the transformed, canonical data into the PostgreSQL database.

### The `ProcessorRegistry`

Once your processor is created, it must be registered with the global `processor_registry` instance from `common.processor_interface`. This allows the system to automatically discover and use your processor for the correct file types.

### Example: A Simple CSV Processor

Here is a minimal example of what a processor looks like.

```python
# plugins/Public/MyCSVProcessor/processor.py

from pathlib import Path
from typing import Dict, List, Any
from common.processor_interface import ProcessorInterface, processor_registry, ProcessorError

class MyCSVProcessor(ProcessorInterface):
    """A simple processor for CSV files."""

    def __init__(self, db_config: Dict[str, Any]):
        super().__init__(db_config)

    @property
    def processor_name(self) -> str:
        return "MyCSV"

    @property
    def supported_formats(self) -> List[str]:
        return [".csv"]

    def validate_source(self, source_path: Path) -> bool:
        return source_path.suffix.lower() in self.supported_formats

    def extract(self, source_path: Path, **kwargs) -> Dict[str, Any]:
        self.logger.info(f"Extracting data from {source_path}")
        try:
            # In a real processor, you might use pandas here
            with source_path.open('r') as f:
                content = f.read()
            return {"csv_content": content}
        except Exception as e:
            raise ProcessorError(f"Failed to extract {source_path}", self.processor_name, e)

    def transform(self, raw_data: Dict[str, Any], source_info: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.info("Transforming raw CSV data")
        # This is where you would convert the CSV data to the canonical format
        transformed_data = {"data": raw_data["csv_content"].splitlines()}
        return transformed_data

    def load(self, transformed_data: Dict[str, Any]) -> bool:
        self.logger.info("Loading transformed data into the database")
        # This is where you would execute SQL queries to insert the data
        print("Loaded rows:", len(transformed_data["data"]))
        return True

# Register an instance of the processor with the registry
# This would typically be done in the plugin's __init__.py
# processor_registry.register(MyCSVProcessor(db_config={}))
```

This new processor could then be discovered and used by the main application to process `.csv` files.

## 5. Testing

The project uses `pytest` for testing.

*   **Running Tests:**
    ```bash
    # Run all tests
    pytest

    # Run tests with coverage report
    pytest --cov=.
    ```

*   **Adding New Tests:**
    1.  Create a new test file in the `tests/` directory, named `test_*.py`.
    2.  Define test functions with names starting with `test_`.
    3.  Use standard `assert` statements to verify behavior.

## 5. Code Style and Quality

*   **Linting & Formatting:** The project uses `ruff` for linting and code formatting, configured in `pyproject.toml`.
*   **Type Checking:** `mypy` is used for static type checking.
*   **Pre-commit:** Hooks automatically run `ruff` and `mypy` on every commit to maintain code quality.

## 6. Contribution Workflow

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Make your changes.
4.  Run tests to ensure your changes don't break existing functionality.
5.  Submit a merge request.

For more details, refer to the [CONTRIBUTING.md](CONTRIBUTING.md) file.
