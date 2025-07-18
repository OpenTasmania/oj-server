# Open Journey Server

<img src="assets/artwork/logos/oj-logo-full.png" alt="Open Journey Server Logo" width="40%"/>

[![Latest Release](https://gitlab.com/opentasmania/oj-server/-/badges/release.svg)](https://gitlab.com/opentasmania/oj-server/-/releases)

[![Latest Tag (SemVer)](https://img.shields.io/gitlab/v/tag/opentasmania/oj-server?sort=semver)](https://gitlab.com/opentasmania/oj-server/-/tags)

**Date:** 2025-07-10

**Primary Maintainer:** [Peter Lawler (relwalretep@gmail.com)](mailto:relwalretep@gmail.com)]

**Location Context:** Developed with a focus on Tasmania, Australia, but adaptable for other regions.

**Licence:** [LGPL3+](LICENCE.txt)

## 1. Overview

This project provides a complete, self-hosted OpenStreetMap and public transport system, designed for deployment on
Kubernetes. It ingests [OpenStreetMap](https://www.openstreetmap.org/) (OSM) data for base maps and routing networks,
and it can process public transport data in formats like [GTFS](https://gtfs.org/).

The system serves map tiles (vector and raster), provides turn-by-turn routing via [OSRM](https://project-osrm.org/),
and makes all data queryable through a [PostgreSQL](https://www.postgresql.org/)/[PostGIS](https://postgis.net/)
database.

The entire stack is designed to run within a [Kubernetes](https://kubernetes.io/) cluster,
with [Debian 13 "Trixie"](http://debian.org/) as the base for its container images.

## 2. System Architecture

The system is deployed as a collection of containerized services orchestrated by Kubernetes. Key components include:

* **Container Orchestration:** [Kubernetes](https://kubernetes.io/) manages the deployment, scaling, and networking of
  all application components. The system is optimized for [MicroK8s](https://microk8s.io/) for local development.
* **Database:** A [PostGIS](https://postgis.net/)-enabled PostgreSQL database stores all OSM and transport data. It is
  deployed as a stateful workload within the cluster.
* **Routing Engine:** [OSRM](http.project-osrm.org/) runs in a dedicated container, providing high-performance
  turn-by-turn routing services.
* **Map Tile Serving:**
    * **Vector Tiles:** [pg_tileserv](https://github.com/CrunchyData/pg_tileserv) serves vector tiles directly from the
      PostGIS database.
    * **Raster Tiles:** A classic OpenStreetMap stack (`renderd`, `mod_tile`, `mapnik`) provides raster imagery.
* **Web Access & SSL:** [Nginx](https://nginx.org/) acts as a reverse proxy for all services. In
  production, [Certbot](https://certbot.eff.org/) is used for automated SSL certificate management, while self-signed
  certificates are used for local development.
* **Data Processing:** A Python-based ETL pipeline handles the ingestion, validation, and processing of transit data
  feeds.

## 3. Setup Instructions

### Quick Start: Kubernetes Deployment

The primary installation method uses a Flask-based application that provides both a web interface and a command-line interface (CLI) to deploy the entire stack to a Kubernetes cluster.

1.  **Prerequisites:**
    *   Ensure you have a running Kubernetes cluster. For local development, we recommend [MicroK8s](httpss://microk8s.io/).
        *   **Install MicroK8s (for local development):**
            ```bash
            sudo snap install microk8s --classic
            sudo usermod -a -G microk8s $USER
            sudo chown -f -R $USER ~/.kube
            newgrp microk8s
            microk8s status --wait-ready
            microk8s enable dns storage ingress registry
            ```
    *   Install the required Python packages:
        ```bash
        pip install -r installer_app/requirements.txt
        ```

2.  **Deploy the Application:**

    You can deploy the application using either the web interface or the CLI.

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

## 4. History

This project started in late 2023 to optimize travel patterns. It initially relied on shell scripts and direct
installation on bare-metal servers.

In 2024, the project began migrating towards a container-based architecture to improve stability and simplify
dependencies.

In 2025, the architecture was fully redesigned to be Kubernetes-native. The legacy `install.py` script and bare-metal
installation process were deprecated and removed in favor of the `kubernetes_installer.py`, which provides a more
robust, scalable, and maintainable solution for deploying the entire Open Journey Server stack.

## 5. Future

Theres a [Todo list](docs/TODO.md), which is automatically generated from comments found in the code.
Planned [enhancements](https://gitlab.com/opentasmania/oj-server/-/issues/?label_name%5B%5D=Enhancement) can also be
found on the Gitlab site.

## 6. Support

There's an [issues](https://gitlab.com/opentasmania/oj-server/-/issues) board where you can submit bugs.
A [Revolt server])(https://revolt.chat) is being worked on, but not yet launched. An FAQ is planned, as well as a Wiki.

## 7. Contributions

Contributions welcome. Please see the [Contributions](docs/CONTRIBUTING.md) file for more details.

## 8. Developer Guidelines

For detailed development guidelines, including build/configuration instructions, testing information, and additional
development information, please see the [Developer Guidelines](.junie/guidelines.md) file.
