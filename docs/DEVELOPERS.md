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

The primary method for deploying the OJ Server for development or production is via Kubernetes, using the `kubernetes_installer.py` script.

*   **Local Development (MicroK8s):**
    ```bash
    ./kubernetes_installer.py deploy --env local
    ```
    This deploys the system to the `oj` namespace and configures Nginx with self-signed SSL certificates.

*   **Production Environment:**
    ```bash
    ./kubernetes_installer.py deploy --production
    ```
    This deploys the system and configures Certbot to manage Let's Encrypt SSL certificates.

For more details on the `kubernetes_installer.py` script, its options, and how to create custom node images, refer to the main `README.md` and the [Kubernetes Installer Guide](kubernetes.md).

## 3. Project Architecture

The project is organized into several key directories:

*   `kubernetes/`: Contains all Kubernetes manifests, organized by components and overlays (`local`, `production`) using `kustomize`.
*   `install_kubernetes/`: Contains the Python source code for the Kubernetes installer, including builders for custom Debian images.
*   `common/`: Shared Python utilities and helper functions used across the project.
*   `docs/`: Project documentation, including plans, strategies, and developer guides.
*   `processors/`: Contains the ETL logic for processing static and real-time transit data.

### Core Design Principle: Pluggable Processors

To handle a wide variety of transit data, the project uses a modular, pluggable architecture for both static and real-time data.

*   **Static Data Pipeline:** An ETL pipeline uses independent processor plugins for each data format (e.g., GTFS, NeTEx). All data is transformed into a single **Canonical Database Schema**, ensuring a consistent data structure in PostGIS.
*   **Real-time Data Service:** A continuously running service uses dedicated plugins for each real-time feed (e.g., GTFS-RT, SIRI). Each plugin transforms its data into a standard **Canonical Data Model** before it's cached and served via an API.

This architecture decouples the core application from the complexities of individual data formats. For more details, see the strategy documents in `docs/strategies/`.

## 4. Testing

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
