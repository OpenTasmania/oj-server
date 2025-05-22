# Open Street Map and Routing Machine Server

<img src="assets/osm-osrm-server-logo-full.png" alt="OSM ORSM Server Logo" width="40%"/>

**Date:** 2025-05-22

**Primary Maintainer:** [Peter Lawler (relwalretep@gmail.com)](mailto:relwalretep@gmail.com)]

**Location Context:** Developed with a focus on Tasmania, Australia, but adaptable for other regions.

**Licence:** [LGPL3+](LICENCE.txt)

## 1. Overview

This project provides a complete self-hosted OpenStreetMap system. It
ingests [OpenStreetMap](https://www.openstreetmap.org/) (OSM) data for base maps and routing networks. The system serves
map tiles (both vector and raster), provides turn-by-turn routing (including for routes
via [OSRM](https://project-osrm.org/)). It adds [GTFS](https://gtfs.org/) data as an example of additional data that can
be ingested and makes this data queryable through
a [PostgreSQL](https://www.postgresql.org/)/[PostGIS](https://postgis.net/) database.

The entire stack is designed to run on a dedicated [Debian 12 "Bookworm"](http://debian.org/) system.

## 2. System Architecture

The system is deployed on a GNU/Linux system with the following key components:

* **Development Environment:** [Python](https://www.python.org/) package (`gtfs_processor`) managed with `uv` and
  defined by `pyproject.toml`, suitable for development in IDEs like [PyCharm](https://www.jetbrains.com/pycharm/).
* **Database:** PostgreSQL with ith PostGIS and HStore extensions for storing OSM and GTFS data.
* **Routing Engine:**
    * The `osrm/osrm-backend` [Docker](https://www.docker.com/) image is used, primarily due to dependency issues in
      development.
    * [OSM PBF](https://wiki.openstreetmap.org/wiki/PBF_Format) data is preprocessed using tools within the Docker
      image.
    * `osrm-routed` runs inside a Docker container managed by a `systemd` service, exposing port 5000 locally.
* **Map Tile Serving:**
    * Vector Tiles via [pg_tileserv](https://github.com/CrunchyData/pg_tileserv) serving vector tiles directly from
      PostGIS. Runs as a `systemd` service.
    * Raster Tiles via a classic OpenStreetMap stack ([Mapnik](https://mapnik.org/), `renderd` tile rendering daemon,
      `mod_tile` serving raster tiles with [Apache2](https://httpd.apache.org/), OpenStreetMap-Carto stylesheet for
      rendering. Runs as a `systemd` service (typically on port 8080 if Nginx is primary).
* **Web Access:** [nginx](https://nginx.org/) as a reverse proxy for all services.
* **SSL Certificate:** [Certbot](https://certbot.eff.org/) (typically on ports 80/443), routing requests to the
  appropriate backend services (`pg_tileserv`, Apache/`mod_tile`, OSRM). Handles SSL termination.
* **GTFS Data Management:**
    * Automated download and import of GTFS static feeds into PostGIS.
    * Python-based [ETL pipeline](https://en.wikipedia.org/wiki/Extract,_transform,_load) for processing, validating,
      cleaning GTFS data, and handling problematic records via
      [Dead-Letter Queues](https://en.wikipedia.org/wiki/Dead_letter_queue) (DLQ).
    * A cron job triggers updates.
    * (Future) GTFS-Realtime processing.
* **UFW (Uncomplicated Firewall):** Configured for basic security.
* **Other Data Sources**
    * Investigate using other file formats for known routing paths.

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
3. Runs the [main installation script](install_map_server.py)

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

## 4. Project Structure

1. [Installer](install.py)
    * Ensure prequisites are available.
2. [Map server installer](install_map_server.py)
    * Install the map server.
    * Import data from processors.
3. Submodules
    * [GTFS processor](gtfs_processor) Python package to import GTFS data into the postgis database on which
      the mapping data exists.

## 5. History

This project started out in late 2023 as a tool to help optimise travel patterns to purchase household goods
after becoming dissatisfied with commercial offerings. While the publicly available OSM/OSRM could be usable, there
was consideration given to how it might be useful in [Home Assistant](https://home-assistant.io). It became increasingly
clear a lot of data verification could be handled by python libraries and the system moved to docker.

In 2024, reliance on microk8s was removed, and the code base cleaned and documentation for such was removed -
although some may linger in the dark recesses somewhere. While it's intended at some stage to bring back microk8s, due
to the thoughts of having this run on Home Assistant for now the project intends to be dockerizing everything.

In 2025, the reliance on shell scripting was reduced to the point where it was removed in early May. Initial release is
intended to make use of Issues boards on a hosted git server, as well as continuous integration build testing.

## 6. Contributions

Contributions welcome. Please see the [Contributions](CONTRIBUTING.md) file for more details.
