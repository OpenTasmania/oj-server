# Open Street Map and Routing Machine Server

<img src="assets/artwork/logos/osm-osrm-server-logo-full.png" alt="OSM ORSM Server Logo" width="40%"/>

[![Latest Release](https://gitlab.com/opentasmania/osm-osrm-server/-/badges/release.svg)](https://gitlab.com/opentasmania/osm-osrm-server/-/releases)

[![Latest Tag (SemVer)](https://img.shields.io/gitlab/v/tag/opentasmania/osm-osrm-server?sort=semver)](https://gitlab.com/opentasmania/osm-osrm-server/-/tags)
<!--
[![Pipeline Status](https://gitlab.com/opentasmania/osm-osrm-server/badges/main/pipeline.svg)](https://gitlab.com/opentasmania/osm-osrm-server/-/pipelines)

[![coverage report](https://gitlab.com/opentasmania/osm-osrm-server/badges/master/coverage.svg)](https://gitlab.com/opentasmania/osm-osrm-server/-/commits/master)
!-->

**Date:** 2025-06-26

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

The entire stack is designed to run on a dedicated [Debian 13 "Trixie"](http://debian.org/) system.

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
    * Runs the main mapping installer ([main_map_server_entry](installer/main_installer.py))

```bash
python3 install.py
```

### Installer help

To obtain install configuration options and associated help text, use this command (correct at 2025-05-28:

```bash
python3 install.py --continue-install --help

Usage: install.py <action_flag_or_help> [arguments_for_main_map_server_entry]

This script performs the following actions:
1. Ensures 'uv' (Python packager and virtual environment manager) is installed.
2. Ensures 'libpq-dev' (for 'pg_config' needed by psycopg) is installed.
3. Creates a virtual environment in '.venv' using 'uv venv'.
4. Installs project dependencies from 'pyproject.toml' into the venv.
5. Based on the <action_flag>, performs the specified action.

Action Flags and Help (one is required if not -h/--help):
  -h, --help                  Show this help message, it will also attempt to display
                                help from 'installer.main_installer'.

Arguments for installer.main_installer:
  (Displayed below if accessible when --help)


================================================================================
Help information for the main setup module (installer.main_installer):
================================================================================
usage: main_installer.py [-h] [--generate-preseed-yaml [TASK_OR_GROUP ...]] [--full] [--view-config] [--view-state] [--clear-state] [--config-file CONFIG_FILE] [-a ADMIN_GROUP_IP] [-f GTFS_FEED_URL] [-v VM_IP_OR_DOMAIN] [-b PG_TILESERV_BINARY_LOCATION] [-l LOG_PREFIX] [--container-runtime-command CONTAINER_RUNTIME_COMMAND] [--osrm-image-tag OSRM_IMAGE_TAG]
                         [--apache-listen-port APACHE_LISTEN_PORT] [-H PGHOST] [-P PGPORT] [-D PGDATABASE] [-U PGUSER] [-W PGPASSWORD] [--boot-verbosity] [--core-conflicts] [--docker-install] [--nodejs-install] [--ufw-pkg-check] [--ufw-rules] [--ufw-activate] [--ufw] [--postgres] [--carto] [--renderd] [--apache] [--nginx] [--certbot] [--pgtileserv] [--osrm] [--gtfs-prep]
                         [--raster-prep] [--website-setup] [--task-systemd-reload] [--prereqs] [--services] [--data] [--systemd-reload] [--dev-override-unsafe-password]

Map Server Installer Script

options:
  -h, --help            Show this help message and exit.
  --generate-preseed-yaml [TASK_OR_GROUP ...]
                        Generate package preseeding data as YAML and exit. Without arguments, shows all default preseed values. With specific task/group names (e.g., 'postgres', 'core_prereqs'), filters output to only show preseed data relevant to those tasks. Will include placeholder comments for packages without preseed data. (default: None)
  --full                Run full installation process. (default: False)
  --view-config         View current configuration settings and exit. (default: False)
  --view-state          View completed installation steps and exit. (default: False)
  --clear-state         Clear all progress state and exit. (default: False)
  --config-file CONFIG_FILE
                        Path to YAML configuration file (default: config.yaml). (default: config.yaml)

Configuration Overrides (CLI > YAML > ENV > Defaults):
  -a, --admin-group-ip ADMIN_GROUP_IP
                        Admin IP (CIDR). Default: 192.168.128.0/22 (default: None)
  -f, --gtfs-feed-url GTFS_FEED_URL
                        GTFS URL. Default: https://www.transport.act.gov.au/googletransit/google_transit.zip (default: None)
  -v, --vm-ip-or-domain VM_IP_OR_DOMAIN
                        Public IP/FQDN. Default: example.com (default: None)
  -b, --pg-tileserv-binary-location PG_TILESERV_BINARY_LOCATION
                        pg_tileserv URL. Default: https://postgisftw.s3.amazonaws.com/pg_tileserv_latest_linux.zip (default: None)
  -l, --log-prefix LOG_PREFIX
                        Log prefix. Default: [MAP-SETUP] (default: None)
  --container-runtime-command CONTAINER_RUNTIME_COMMAND
                        Container runtime. Default: docker (default: None)
  --osrm-image-tag OSRM_IMAGE_TAG
                        OSRM Docker image. Default: osrm/osrm-backend:latest (default: None)
  --apache-listen-port APACHE_LISTEN_PORT
                        Apache listen port. Default: 8080 (default: None)

PostgreSQL Overrides:
  -H, --pghost PGHOST   Host. Default: 127.0.0.1 (default: None)
  -P, --pgport PGPORT   Port. Default: 5432 (default: None)
  -D, --pgdatabase PGDATABASE
                        Database. Default: gis (default: None)
  -U, --pguser PGUSER   User. Default: osmuser (default: None)
  -W, --pgpassword PGPASSWORD
                        Password. (default: None)

Individual Task Flags:
  --boot-verbosity      Boot verbosity setup. (Specific task or component) (default: False)
  --core-conflicts      Core conflict removal. (Specific task or component) (default: False)
  --docker-install      Docker installation. (Specific task or component) (default: False)
  --nodejs-install      Node.js installation. (Specific task or component) (default: False)
  --ufw-pkg-check       UFW Package Check. (Part of Group: 'Firewall Service (UFW)', Sub-step: 1) (default: False)
  --ufw-rules           Configure UFW Rules. (Part of Group: 'Firewall Service (UFW)', Sub-step: 2) (default: False)
  --ufw-activate        Activate UFW Service. (Part of Group: 'Firewall Service (UFW)', Sub-step: 3) (default: False)
  --ufw                 UFW full setup. (Orchestrates Group: 'Firewall Service (UFW)') (default: False)
  --postgres            PostgreSQL full setup. (Orchestrates Group: 'Database Service (PostgreSQL)') (default: False)
  --carto               Carto full setup. (Orchestrates Group: 'Carto Service') (default: False)
  --renderd             Renderd full setup. (Orchestrates Group: 'Renderd Service') (default: False)
  --apache              Apache & mod_tile full setup. (Orchestrates Group: 'Apache Service') (default: False)
  --nginx               Nginx full setup. (Orchestrates Group: 'Nginx Service') (default: False)
  --certbot             Certbot full setup. (Orchestrates Group: 'Certbot Service') (default: False)
  --pgtileserv          pg_tileserv full setup. (Orchestrates Group: 'pg_tileserv Service') (default: False)
  --osrm                OSRM full setup & data processing. (Orchestrates Group: 'OSRM Service & Data Processing') (default: False)
  --gtfs-prep           Full GTFS Pipeline. (Part of Group: 'GTFS Data Pipeline', Sub-step: 1) (default: False)
  --raster-prep         Raster tile pre-rendering. (Part of Group: 'Raster Tile Pre-rendering', Sub-step: 1) (default: False)
  --website-setup       Deploy test website. (Part of Group: 'Application Content', Sub-step: 1) (default: False)
  --task-systemd-reload
                        Systemd reload task. (Part of Group: 'Systemd Reload', Sub-step: 1) (default: False)

Group Task Flags:
  --prereqs             Run 'Comprehensive Prerequisites' group. Includes: --boot-verbosity, --core-conflicts, --docker-install, --nodejs-install, and setup for essential utilities, Python, PostgreSQL, mapping & font packages, and unattended upgrades. (default: False)
  --services            Run setup for ALL services. Includes: --ufw, --postgres, --pgtileserv, --carto, --renderd, --osrm, --apache, --nginx, --certbot, --website-setup, and a final systemd reload. (default: False)
  --data                Run all data preparation tasks. Includes: --gtfs-prep (Full GTFS Pipeline) and --raster-prep (Raster tile pre-rendering). (default: False)
  --systemd-reload      Run systemd reload task (as a group action). Same as --task-systemd-reload. (default: False)

Developer Options:
  --dev-override-unsafe-password

Example: python3 ./installer/main_installer.py --full -v mymap.example.com
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
2. [Map server installer](installer/main_installer.py)
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

Theres a [Todo list](docs/TODO.md), which is automatically generated from comments found in the code.
Planned [enhancements](https://gitlab.com/opentasmania/osm-osrm-server/-/issues/?label_name%5B%5D=Enhancement)
can also be found on the Gitlab site.

## 7. Support

There's an [issues](https://gitlab.com/opentasmania/osm-osrm-server/-/issues) board where you can submit bugs.
A [Revolt server])(https://revolt.chat) is being worked on, but not yet launched. An FAQ is planned, as well
as a Wiki.

## 8. Contributions

Contributions welcome. Please see the [Contributions](docs/CONTRIBUTING.md) file for more details.
