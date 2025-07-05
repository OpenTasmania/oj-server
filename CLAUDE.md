# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Testing
- `python -m pytest` - Run all tests
- `python -m pytest -v` - Run tests with verbose output  
- `python -m pytest --cov=.` - Run tests with coverage
- `python -m pytest tests/test_specific_file.py` - Run specific test file

### Code Quality
- `ruff check` - Run linting
- `ruff format` - Format code
- `mypy .` - Type checking
- `vulture .` - Find unused code
- `uv run pre-commit run --all-files` - Run all pre-commit hooks

### Installation and Setup
- `python3 install.py --help` - Show installer help
- `python3 install.py list` - List available components
- `python3 install.py install <component>` - Install specific component
- `python3 install.py status` - Check component installation status
- `python3 install.py setup <component>` - Configure component after installation

### Coverage Reports
Coverage reports are generated in multiple formats:
- HTML: `cover/coverage_html/index.html`
- JSON: `cover/coverage.json`
- XML: `cover/coverage.xml`

## Architecture Overview

This is an **OpenStreetMap (OSM) and Open Source Routing Machine (OSRM) server** that provides:
- Map tile serving (vector and raster)
- Turn-by-turn routing via OSRM
- GTFS transit data integration
- Self-hosted stack on Debian systems

### Key Components

**Core Architecture:**
- **Modular installer framework** (`installer/`) with pluggable components
- **Bootstrap system** (`bootstrap/`) for environment setup
- **Component registry** for dynamic discovery and loading
- **Common utilities** (`common/`) shared across components

**Service Stack:**
- **Database**: PostgreSQL with PostGIS extensions
- **Routing**: OSRM in Docker containers managed by systemd
- **Tile Serving**: pg_tileserv (vector) + Apache/mod_tile/renderd (raster)
- **Web Access**: nginx reverse proxy with SSL via Certbot
- **Data Processing**: Python ETL pipeline for GTFS data

**Component Structure:**
Each component in `installer/components/` has:
- `*_installer.py` - Installation logic
- `*_configurator.py` - Configuration logic
- Both inherit from `BaseComponent` (`installer/base_component.py`)

### Data Processing Pipeline

**GTFS Processing** (`installer/processors/plugins/importers/transit/gtfs/`):
- Modular ETL pipeline with pluggable processors
- Dead Letter Queue (DLQ) for problematic records
- Canonical database schema for consistent data structure
- Automated download and import via cron jobs

**Key Pipeline Files:**
- `main_pipeline.py` - Main ETL orchestration
- `download.py` - Data fetching
- `transform.py` - Data transformation
- `load.py` - Database loading
- `automation.py` - Scheduling and automation

## Important Development Guidelines

### Package Management
- **All apt operations** must use `AptManager` class (`common/debian/apt_manager.py`)
- Never call `apt-get` directly - always use the centralized interface

### Logging
- **All logging** must be configured through `setup_logging()` in `common/core_utils.py`
- Never call `logging.basicConfig()` in modules
- Get loggers with: `logger = logging.getLogger(__name__)`
- Use `log_map_server()` from `common/command_utils.py` for user-facing messages

### Code Organization
- Python 3.13 required
- Uses `uv` for package management (defined in `pyproject.toml`)
- Code style enforced by ruff (line length: 78 characters)
- Type checking with mypy
- Pre-commit hooks for code quality

### Testing Structure
- Tests in `tests/` directory
- Use pytest with coverage reporting
- Test files must start with `test_`
- Add project root to Python path in test files

## Entry Points and Key Files

- `install.py` - Main installer entry point
- `config.yaml` - Main configuration file
- `pyproject.toml` - Python project configuration and dependencies
- `cliff.toml` - Changelog generation configuration
- `installer/orchestrator.py` - Component orchestration logic
- `installer/registry.py` - Dynamic component registration
- `common/core_utils.py` - Core utilities and logging setup

## Component Dependencies

Components have dependencies managed through the registry system. Use `python3 install.py status --tree` to view dependency relationships.

Common installation order:
1. Prerequisites (`prerequisites`)
2. Database (`postgres`)
3. Web services (`nginx`, `apache`)
4. Routing (`osrm`)
5. Tile services (`pg_tileserv`, `renderd`)
6. Security (`ufw`, `certbot`)