# Open Street Map and Routing Machine Server

<img src="assets/artwork/logos/osm-osrm-server-logo-full.png" alt="OSM ORSM Server Logo" width="40%"/>

[![Latest Release](https://gitlab.com/opentasmania/osm-osrm-server/-/badges/release.svg)](https://gitlab.com/opentasmania/osm-osrm-server/-/releases)

[![Latest Tag (SemVer)](https://img.shields.io/gitlab/v/tag/opentasmania/osm-osrm-server?sort=semver)](https://gitlab.com/opentasmania/osm-osrm-server/-/tags)
<!--
[![Pipeline Status](https://gitlab.com/opentasmania/osm-osrm-server/badges/main/pipeline.svg)](https://gitlab.com/opentasmania/osm-osrm-server/-/pipelines)

[![coverage report](https://gitlab.com/opentasmania/osm-osrm-server/badges/master/coverage.svg)](https://gitlab.com/opentasmania/osm-osrm-server/-/commits/master)
!-->

**Date:** 2025-05-28

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

1. Check for essential preqrequisites:
    * Update the system package lists.
    * Upgrade the system if required to ensure the latest packages are installed.
    * Tests to see if basic python3 capability is available, and if not install it.

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

2. Run the installer
    * Checks for required Python packages
    * Prompts to install any missing packages using sudo apt install
    * Runs the main mapping installer ([main_map_server_entry](setup/main_installer.py))

```bash
python3 install.py
```

### Installer help

To obtain install configuration options and associated help text, use this command (correct at 2025-05-28:

```bash
python3 install.py --continue-install --help

Usage: install.py [--help] <action_flag> [arguments_for_main_map_server_entry]

Prerequisite installer for the Map Server Setup.
This script performs the following actions:
1. Ensures 'uv' (Python packager and virtual environment manager) is installed.
2. Creates a virtual environment in '.venv' using 'uv venv'.
3. Installs project dependencies from 'pyproject.toml' (expected in the same directory as this script)
   into the venv using 'uv pip install .'.
4. Based on the <action_flag> provided, it either continues to the main setup or exits.

Action Flags (mutually exclusive, one is required):
  --continue-install     After prerequisite and venv setup, proceed to run the
                         main map server setup ('setup.main_installer') using the
                         virtual environment's Python.
  --exit-on-complete     Exit successfully after prerequisite and venv setup is complete.
                         Does not run the main map server setup.

Options for this script (install.py):
  -h, --help             Show this combined help message (including help for the main setup script if --continue-install is used)
                         and exit.

Arguments for setup.main_installer (passed if --continue-install is used):
  (These are arguments for 'setup.main_installer' and will be dynamically fetched and listed below if possible)


================================================================================
Help information for the main setup module (setup.main_installer):
================================================================================
Could not import processors.gtfs module at load time: cannot import name 'model_validator' from 'pydantic' (/usr/lib/python3/dist-packages/pydantic/__init__.py). GTFS processing will likely fail.
usage: main_installer.py [-h] [-a ADMIN_GROUP_IP] [-f GTFS_FEED_URL] [-v VM_IP_OR_DOMAIN] [-b PG_TILESERV_BINARY_LOCATION] [-l LOG_PREFIX] [-H PGHOST] [-P PGPORT] [-D PGDATABASE]
                         [-U PGUSER] [-W PGPASSWORD] [--boot-verbosity] [--core-conflicts] [--core-install] [--docker-install] [--nodejs-install] [--ufw] [--postgres]
                         [--pgtileserv] [--carto] [--renderd] [--osrm] [--apache] [--nginx] [--certbot] [--gtfs-prep] [--raster-prep] [--website-prep] [--task-systemd-reload]
                         [--full] [--conflicts-removed] [--prereqs] [--services] [--data] [--systemd-reload] [--view-config] [--view-state] [--clear-state]
                         [--im-a-developer-get-me-out-of-here]

Map Server Installer Script. Automates installation and configuration.

options:
  -h, --help            show this help message and exit
  -a ADMIN_GROUP_IP, --admin-group-ip ADMIN_GROUP_IP
                        Admin group IP range (CIDR). (default: 192.168.128.0/22)
  -f GTFS_FEED_URL, --gtfs-feed-url GTFS_FEED_URL
                        GTFS feed URL. (default: https://www.transport.act.gov.au/googletransit/google_transit.zip)
  -v VM_IP_OR_DOMAIN, --vm-ip-or-domain VM_IP_OR_DOMAIN
                        VM IP or Domain Name. (default: example.com)
  -b PG_TILESERV_BINARY_LOCATION, --pg-tileserv-binary-location PG_TILESERV_BINARY_LOCATION
                        pg_tileserv binary URL. (default: https://postgisftw.s3.amazonaws.com/pg_tileserv_latest_linux.zip)
  -l LOG_PREFIX, --log-prefix LOG_PREFIX
                        Log message prefix. (default: [MAP-SETUP])
  -H PGHOST, --pghost PGHOST
                        PostgreSQL host. (default: 127.0.0.1)
  -P PGPORT, --pgport PGPORT
                        PostgreSQL port. (default: 5432)
  -D PGDATABASE, --pgdatabase PGDATABASE
                        PostgreSQL database name. (default: gis)
  -U PGUSER, --pguser PGUSER
                        PostgreSQL username. (default: osmuser)
  -W PGPASSWORD, --pgpassword PGPASSWORD
                        PostgreSQL password. IMPORTANT: Change this default! (default: yourStrongPasswordHere)
  --boot-verbosity      Run boot verbosity setup only. (Prerequisites, Step 1) (default: False)
  --core-conflicts      Run core conflict removal only. (Core Conflict Removal, Step 1) (default: False)
  --core-install        Run core package installation only. (Prerequisites, Step 2) (default: False)
  --docker-install      Run Docker installation only. (Prerequisites, Step 3) (default: False)
  --nodejs-install      Run Node.js installation only. (Prerequisites, Step 4) (default: False)
  --ufw                 Run UFW setup only. (Services, Step 1) (default: False)
  --postgres            Run PostgreSQL setup only. (Services, Step 2) (default: False)
  --pgtileserv          Run pg_tileserv setup only. (Services, Step 3) (default: False)
  --carto               Run CartoCSS & OSM Style setup only. (Services, Step 4) (default: False)
  --renderd             Run Renderd setup only. (Services, Step 5) (default: False)
  --osrm                Run OSM Data & OSRM setup only. (Services, Step 6) (default: False)
  --apache              Run Apache for mod_tile setup only. (Services, Step 7) (default: False)
  --nginx               Run Nginx reverse proxy setup only. (Services, Step 8) (default: False)
  --certbot             Run Certbot SSL setup only. (Services, Step 9) (default: False)
  --gtfs-prep           Run GTFS data preparation only. (Data Preparation, Step 1) (default: False)
  --raster-prep         Run raster tile pre-rendering only. (Data Preparation, Step 2) (default: False)
  --website-prep        Run test website preparation only. (Data Preparation, Step 3) (default: False)
  --task-systemd-reload 
                        Run systemd reload as a single task. (Systemd Reload, Step 1) (default: False)
  --full                Run full installation process (all groups in sequence). (default: False)
  --conflicts-removed   Run core conflict removal group only. (default: False)
  --prereqs             Run prerequisites installation group only. (default: False)
  --services            Run services setup group only. (default: False)
  --data                Run data preparation group only. (default: False)
  --systemd-reload      Run systemd reload (original group action). (default: False)
  --view-config         View current configuration settings and exit. (default: False)
  --view-state          View completed installation steps from state file and exit. (default: False)
  --clear-state         Clear all progress state from state file and exit. (default: False)
  --im-a-developer-get-me-out-of-here, --dev-override-unsafe-password
                        Developer flag: Allow using default PGPASSWORD for .pgpass and suppress related warnings. USE WITH CAUTION. (default: False)

Example: python3 ./setup/main_installer.py --full -v mymap.example.com

```

### Detailed Setup

The setup process is designed to be followed sequentially.

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
2. [Map server installer](setup/main_installer.py)
    * Install the map server.
    * Import data from processors.
3. Submodules
    * [GTFS processor](processors/gtfs) Python package to import GTFS data into the postgis database on which
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

## 6. Future

Theres a [Todo list](TODO.md), which is automatically generated from comments found in the code.
Planned [enhancements](https://gitlab.com/opentasmania/osm-osrm-server/-/issues/?label_name%5B%5D=Enhancement)
can also be found on the Gitlab site.

## 7. Support

There's an [issues](https://gitlab.com/opentasmania/osm-osrm-server/-/issues) board where you can submit bugs.
A [Revolt server])(https://revolt.chat) is being worked on, but not yet launched. An FAQ is planned, as well
as a Wiki.

## 8. Contributions

Contributions welcome. Please see the [Contributions](CONTRIBUTING.md) file for more details.
