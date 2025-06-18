# Modular Bootstrap

## Overview

The Modular Bootstrap system is a self-contained bootstrap process for the `setup_modular.py` script. It ensures that all prerequisites are met before the script is executed. This system mirrors the functionality of the existing `/bootstrap_installer` but is completely isolated within the `/modular_bootstrap` directory.

## Purpose

The primary purpose of the Modular Bootstrap system is to ensure that all necessary tools and libraries are installed and properly configured before the main application setup begins. This includes:

- Python modules like `python3-apt` and `pydantic`
- System utilities like `lsb-release` and `util-linux`
- Build tools like `build-essential` and `python3-dev`

## Components

The Modular Bootstrap system consists of the following components:

- `mb_utils.py`: Common utilities for the bootstrap process, including logging, command checking, and package management functions.
- `mb_apt.py`: Ensures the presence of the `python3-apt` package.
- `mb_pydantic.py`: Ensures the presence of the `pydantic` and `pydantic-settings` packages.
- `mb_build_tools.py`: Ensures the presence of build tools like `build-essential` and `python3-dev`.
- `mb_lsb.py`: Ensures the presence of the `lsb-release` package.
- `mb_util_linux.py`: Ensures the presence of the `util-linux` package.
- `orchestrator.py`: Manages the execution of the individual prerequisite checks.

## Integration

The Modular Bootstrap system is integrated into the `setup_modular.py` script. The script calls the `run_modular_bootstrap()` function immediately after setting up the logger and before the `SetupOrchestrator` is initialized. This ensures that all prerequisites are met before the script proceeds with its main configuration tasks.

## Usage

The Modular Bootstrap system is automatically used when running the `setup_modular.py` script. There is no need to manually invoke it.

```bash
python setup_modular.py [options]
```

## Development

When adding new prerequisites to the Modular Bootstrap system, follow these steps:

1. Create a new module in the `/modular_bootstrap` directory with the prefix `mb_`.
2. Implement a function that checks for the prerequisite and installs it if necessary.
3. Update the `orchestrator.py` file to include the new prerequisite check.
4. Update this README.md file to document the new prerequisite.