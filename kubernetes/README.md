# Kubernetes Core Infrastructure

This directory contains the core Kubernetes infrastructure for the Open Journey Server. These components are considered
essential for the system to run and are not part of the plugin architecture.

## Components

- **base**: Contains the base kustomization for the entire application, including the namespace definition.
- **components/certbot**: Manages SSL certificates using Certbot.
- **components/nginx**: The Nginx ingress controller, which routes traffic to the various services.
- **components/nodejs**: A base Node.js image used by other components.
- **components/osrm**: The OSRM routing engine.
- **components/postgres**: The PostgreSQL database, which stores all the application data.
- **components/self-signed-certs**: A job to generate self-signed certificates for local development.
- **overlays**: Contains kustomize overlays for different environments (e.g., `local`, `production`).
