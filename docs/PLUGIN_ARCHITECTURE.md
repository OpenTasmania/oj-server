# OpenJourney Server Plugin Architecture

This document provides a comprehensive overview of the OpenJourney Server's plugin architecture, detailing how plugins are discovered, loaded, and integrated into the server's lifecycle. It also covers the architecture of the existing public plugins.

## Plugin System Architecture

The OpenJourney Server's plugin system is designed to be modular and extensible, allowing for the easy addition of new functionalities without modifying the core application. The system is built around a central plugin manager that discovers, loads, and manages plugins.

### Plugin Discovery

Plugins are discovered by searching for directories in the `plugins/Public` and `plugins/Private` directories. Each plugin is expected to be a self-contained module with a `plugin.py` file that acts as the entry point.

### Plugin Interface

All plugins must implement the `InstallerPlugin` interface, which defines a set of methods that the plugin manager calls at different stages of the server's lifecycle. The key methods are:

- `name()`: Returns the name of the plugin.
- `get_database_requirements()`: Returns a dictionary of the plugin's database requirements.
- `post_config_load(config)`: Called after the main configuration is loaded, allowing the plugin to add its own default configuration.
- `pre_apply_k8s(manifests)`: Called before Kubernetes manifests are applied, allowing the plugin to add its own manifests.
- `post_database_setup(db_connection)`: Called after the database is set up, allowing the plugin to perform its own database setup.
- `on_install_complete()`: Called when the installation is complete.
- `on_error(error)`: Called if an error occurs during installation.

### Plugin Loading

The plugin manager dynamically loads each plugin by importing its `plugin.py` file and calling the `get_plugin()` function to get an instance of the plugin class.

## Public Plugin Architectures

This section details the architecture of each of the public plugins.

### OpenJourneyServer_Apache

The Apache plugin provides an Apache HTTP server with `mod_tile` integration for serving map tiles and static web content.

- **Core Components**: Apache HTTP Server, `mod_tile` module.
- **Functionality**: Serves map tiles from the `/osm_tiles/{z}/{x}/{y}.png` endpoint, provides static web content hosting, and handles CORS headers.
- **Integration**: Integrates with `renderd` for on-demand tile generation.

### OpenJourneyServer_Dataprocessing

The Data Processing plugin orchestrates the extraction, transformation, and loading (ETL) of static transit data from various sources.

- **Core Components**: Static ETL Orchestrator (`run_static_etl.py`), Processor Registry, Configuration Manager, Plugin Loader.
- **Functionality**: Processes static transit feeds (GTFS, NeTEx, etc.) into a canonical database schema.
- **Integration**: Uses a processor interface to handle different data formats.

### OpenJourneyServer_GTFS

The GTFS plugin handles the processing of GTFS data. It provides two processing approaches: a legacy daemon and a modern processor.

- **Core Components**: GTFS Daemon, GTFS Processor, Database Schema.
- **Functionality**: Downloads and processes GTFS ZIP files, parses GTFS text files, and transforms data into both legacy and canonical database schemas.
- **Integration**: The modern processor integrates with the ETL orchestrator.

### OpenJourneyServer_OpenStreetMap

The OpenStreetMap plugin provides tile rendering capabilities through the `renderd` service.

- **Core Components**: `renderd` service, Mapnik, `mod_tile`.
- **Functionality**: Manages tile caching and integration with the mapping stack for serving raster tiles.
- **Integration**: Stores OSM data in a PostgreSQL database with the PostGIS extension.

### OpenJourneyServer_OSRM

The OSRM plugin provides routing services using the Open Source Routing Machine engine.

- **Core Components**: OSRM Backend, Routing Profiles, Database Integration.
- **Functionality**: Calculates optimal routes for different transportation modes, provides turn-by-turn navigation, and supports distance matrix calculations.
- **Integration**: Integrates with a PostgreSQL database for routing analytics and caching.

### OpenJourneyServer_pg_tileserv

The `pg_tileserv` plugin provides a lightweight vector tile server that serves tiles directly from PostGIS spatial tables.

- **Core Components**: Tile Server, PostGIS Integration, REST API.
- **Functionality**: Automatically discovers spatial tables and exposes them as vector tile endpoints.
- **Integration**: Connects directly to PostGIS spatial tables.

### OpenJourneyServer_pgAdmin

The pgAdmin plugin provides a web-based administration interface for PostgreSQL databases.

- **Core Components**: pgAdmin Web Server, Database Connections, Authentication System.
- **Functionality**: Allows for database management, query execution, and user administration.
- **Integration**: Connects to the PostgreSQL database.

### OpenJourneyServer_pgAgent

The pgAgent plugin provides a job scheduling system for PostgreSQL databases.

- **Core Components**: pgAgent Extension, Job Scheduler, Job Database.
- **Functionality**: Enables automated execution of database maintenance tasks, data processing jobs, and custom SQL operations.
- **Integration**: Connects to the PostgreSQL database and uses the `pgagent` extension.
