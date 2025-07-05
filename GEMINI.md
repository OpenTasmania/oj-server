# Gemini Project Guidelines

This document provides guidelines for using the Gemini CLI tool to contribute to the `osm-osrm-server` project.

## Project Overview

This project is a Python-based server for Open Street Map (OSM) and Open Source Routing Machine (OSRM). It uses
`setuptools` for packaging, `ruff` for linting and formatting, `mypy` for type checking, and `pytest` for testing.

## Development Workflow

### 1. Code Style and Formatting

All Python code should be formatted with `ruff format` and linted with `ruff`. This is enforced by a pre-commit hook.

- **Formatting:** `ruff format .`
- **Linting:** `ruff check .`

### 2. Type Checking

This project uses `mypy` for static type checking. All new code should include type hints.

- **Type Checking:** `mypy .`

### 3. Testing

Tests are written using `pytest`. All new features should be accompanied by tests.

- **Running Tests:** `pytest`

### 4. Dependencies

Dependencies are managed with `uv` and specified in `pyproject.toml`.

- To add a dependency, add it to `pyproject.toml` and then run `uv pip install -r requirements.txt`.

## Project Architecture

The application is a modular installer for a map server stack. The core logic is built around a component-based
architecture.

- **Entry Point**: The main entry point for the application is `install.py`. It handles command-line argument parsing
  and orchestrates the installation process.

- **Orchestrator**: The `installer.orchestrator.ComponentOrchestrator` class is the heart of the application. It manages
  the lifecycle of all components, including dependency resolution, installation, configuration, and status checking.

- **Component Registry**: The `installer.registry.ComponentRegistry` is used to discover and register all available
  components. Components are dynamically imported and registered when the application starts.

- **Base Component**: All components inherit from the `installer.base_component.BaseComponent` abstract base class. This
  class defines the interface that all components must implement, including methods like `install()`, `configure()`,
  `is_installed()`, and `is_configured()`.

- **Components**: Each component is a self-contained module located in a subdirectory of `installer/components/`. A
  component typically consists of an installer and/or a configurator class.
    - **Installer Classes**: Handle the installation of software packages (e.g., `apache_installer.py`).
    - **Configurator Classes**: Handle the configuration of the installed software (e.g., `gtfs_configurator.py`).

- **Configuration**: Application settings are loaded from `config.yaml` into Pydantic models defined in
  `installer.config_models.py`.

## Gemini Usage

When using Gemini to write or modify code, please adhere to the following:

- **Follow Existing Conventions:** Ensure that any generated code matches the style and structure of the existing
  codebase.
- **Run Verification:** After generating code, always run the linter, type checker, and tests to ensure the changes are
  valid.
- **Keep it Simple:** Prefer simple, clear code over complex solutions.
