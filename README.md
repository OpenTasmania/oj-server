# Comprehensive Local Open Street Map routing system

**Version:** 0.0.1 (Project Inception)

**Date:** May 22, 2025

**Primary Maintainer:** [Peter Lawler (relwalretep@gmail.com)](mailto:relwalretep@gmail.com)]

**Location Context:** Developed with a focus on Tasmania, Australia, but adaptable for other regions.

**Licence:** [LGPL3+](LICENCE.txt)

## 1. Overview

This project provides a complete, self-hosted OpenStreetMap system. It ingests OpenStreetMap (OSM) data for base maps
and routing networks. The system serves map tiles (both vector and raster), provides turn-by-turn routing (including for
routes via OSRM). It adds GTFS data as an example of additional data that can be ingested and makes this data queryable
through a PostgreSQL/PostGIS database.

The entire stack is designed to run on a dedicated Debian 12 "Bookworm" system.

**Core Features:**

* **Map Tile Serving:**
    * Vector Tiles via `pg_tileserv` (dynamic, from PostGIS).
    * Raster Tiles via a classic OpenStreetMap stack (Mapnik, `renderd`, `mod_tile` with Apache2, OpenStreetMap-Carto
      style sheet).
* **Routing Engine:**
    * OSRM (Open Source Routing Machine) running in a Docker container for general point-to-point routing (car profile
      by default, adaptable).
* **GTFS Data Management:**
    * Automated download and import of GTFS static feeds into PostGIS.
    * Python-based ETL pipeline for processing, validating, cleaning GTFS data, and handling problematic records via
      Dead-Letter Queues (DLQ).
    * (Future) GTFS-Realtime processing.
* **Database:** PostgreSQL with PostGIS extension for storing OSM and GTFS data.
* **Web Access:** Nginx as a reverse proxy for all services.
* **Development Environment:** Python package (`gtfs_processor`) managed with `uv` and defined by `pyproject.toml`,
  suitable for development in IDEs like PyCharm.

## 2. System Architecture

The system is deployed on a single Debian 12 VM with the following key components:

1. **Debian 12 "Bookworm":** The primary server environment.
2. **PostgreSQL Server (v15):** With PostGIS and HStore extensions. Stores processed OSM data and GTFS feeds.
3. **`pg_tileserv`:** Serves vector tiles directly from PostGIS. Runs as a `systemd` service.
4. **Raster Tile Stack:**
    * **Mapnik:** Rendering library.
    * **OpenStreetMap-Carto:** Stylesheet for rendering.
    * **`renderd`:** Tile rendering daemon. Runs as a `systemd` service.
    * **Apache2 with `mod_tile`:** Serves raster tiles and manages the cache. Runs as a `systemd` service (typically
      on port 8080 if Nginx is primary).
5. **OSRM Server (Docker):**
    * The `osrm/osrm-backend` Docker image is used.
    * OSM PBF data is preprocessed using tools within the Docker image.
    * `osrm-routed` runs inside a Docker container managed by a `systemd` service, exposing port 5000 locally.
6. **GTFS Processor (Python Package):**
    * A custom Python package (`gtfs_processor`) handles GTFS download, validation, cleaning, transformation, and
      loading into PostgreSQL.
    * Includes DLQ mechanisms for bad data.
    * Managed by `uv` within a virtual environment.
    * A cron job triggers updates.
7. **Nginx:** Acts as the main reverse proxy (typically on ports 80/443), routing requests to the appropriate backend
   services (`pg_tileserv`, Apache/`mod_tile`, OSRM). Handles SSL termination.
8. **UFW (Uncomplicated Firewall):** Configured for basic security.

## 3. Setup Instructions

### Quick Start

To set up the system, use the provided installation script:

```bash
sudo apt --yes update
sudo apt --yes upgrade
if ! dpkg -s python3 > /dev/null 2>&1 || ! dpkg -s python3-dev > /dev/null 2>&1; then 
  echo "python3 and/or python3-dev not found. Proceeding with installation..."
  sudo apt update && sudo apt --yes install python3 python3-dev
else
   echo "python3 and python3-dev are already installed."
fi
```

This command:

1. Updates the system package lists.
2. Upgrades the system if required to ensure the latest packages are installed.
3. Tests to see if basic python3 capability is available, and if not install it.

```
python3 install.py
```

This command:

1. Checks for required Python packages
2. Prompts to install any missing packages using sudo apt install
3. Runs the main installation script (install_map_server.py)

### Detailed Setup

The detailed setup process is designed to be followed sequentially.

* **System Foundation - Debian 12**
    * Initial OS configuration, updates, and essential package installations (including all anticipated dependencies for
      subsequent services via a single `apt` command).
    * Firewall (`ufw`) setup.

* **Service Installation & Configuration]**
    * PostgreSQL and PostGIS.
    * OSRM (Docker setup to be detailed here).
    * `pg_tileserv` (Vector Tiles).
    * Raster Tile Stack (Apache2, `mod_tile`, `renderd`, Mapnik, OpenStreetMap-Carto stylesheet).
    * Nginx (Reverse Proxy).
    * `systemd` service definitions.

* **Initial Data Import, Processing & GTFS Automation**
    * Downloading and importing OpenStreetMap (OSM) PBF data into PostGIS using `osm2pgsql`.
    * Preprocessing the OSM PBF data for OSRM using the OSRM Docker image tools (`osrm-extract`, `osrm-partition`,
      `osrm-customize`).
    * Performing the initial GTFS data import using the Python package.
    * Configuring the cron job for automated GTFS updates.
    * (Optional) Pre-rendering raster tiles.

## 4. Project Structure (Python GTFS Processor)

1. [Installer](install.py)
    * Ensure prequisites are available.
2. [Map server installer](install_map_server.py)
    * Install the map server.
    * Import data from processors.
3. Submodules
    * [GTFS processor](gtfs_processor) Python package to import GTFS data into the postgis database on which
      the mapping data exists.

## 5. History

This project started out in late 2023 as a tool to help optimise travel patterns to purchase household goods,
while comparing its results to commercial tools. While the publicly available OSM/OSRM could be usable, there was a
though about how it could be useful in [Home Assistant](https://home-assistant.io) and thinking. As such, it became
increasingly clear a lot of data verification should be handled by python libraries. In 2024, reliance on microk8s
was removed, and the code base cleaned and documentation for such was removed - although some may linger in the
dark recesses somewhere.

While it's intended at some stage to bring back microk8s, due to the thoughts of having this run on Home Assistant, for
now the project examine the possibility of dockerizing everything.

In 2025, the reliance on shell scripting was reduced to the point where it was removed in early May. Initial release is
barely tested as a working project, it's conceptual as a Python project. In fact, it would be surprising if it
works at all at initial release, but that's why it is not marked beyond Alpha quality at that time.

## 6. Contributions

Contributions welcome. This project is hosted on [Gitlab](https://gitlab.com/opentasmania/osm-osrm-server), so there's
all the good stuff there like an [Issues board](https://gitlab.com/opentasmania/osm-osrm-server/issues).
