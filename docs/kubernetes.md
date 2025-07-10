# Open Journey Server - Kubernetes Installer Guide

This document provides comprehensive instructions for using the `kubernetes_installer.py` script to deploy and manage
the Open Journey Server using Kubernetes. The script offers a streamlined approach for both local development
and production deployments.

## Table of Contents

1. [Introduction](#introduction)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Basic Usage](#basic-usage)
5. [Deployment Management](#deployment-management)
6. [Creating Installer Images](#creating-installer-images)
7. [Advanced Options](#advanced-options)
8. [Troubleshooting](#troubleshooting)
9. [Project Structure]

## Introduction

The `kubernetes_installer.py` script provides a comprehensive solution for deploying and managing the Open Journey
Server using Kubernetes. It supports both local development environments using MicroK8s and production deployments on
full Kubernetes clusters.

Key benefits of using the Kubernetes-based approach include:

- **Containerization**: Each component runs in its own container, providing isolation and portability
- **Declarative Configuration**: All settings are defined in YAML files, making changes trackable and reproducible
- **Scalability**: Easy horizontal scaling for handling increased load
- **Flexibility**: Support for multiple container runtimes (Docker, CRI-O, containerd)
- **Simplified Management**: Unified tooling for deployment, updates, and monitoring

## Prerequisites

Before using the `kubernetes_installer.py` script, ensure you have the following prerequisites installed:

### For All Environments

- Python 3.13 or higher
- Basic understanding of Kubernetes concepts
- Git (for cloning the repository)

### For Local Development (MicroK8s)

1. Install MicroK8s:
   ```bash
   sudo snap install microk8s --classic
   sudo usermod -a -G microk8s $USER
   sudo chown -f -R $USER ~/.kube
   newgrp microk8s
   ```

2. Verify MicroK8s is running:
   ```bash
   microk8s status --wait-ready
   ```

3. Enable required add-ons:
   ```bash
   microk8s enable dns storage ingress registry
   ```

### For Production Environments

- Access to a Kubernetes cluster (self-hosted or cloud provider)
- `kubectl` configured to access your cluster
- Sufficient permissions to create namespaces and deploy resources
- Cert-Manager installed and configured in your cluster (if using `--production` for SSL).

## Installation

1. Clone the repository:
   ```bash
   git clone https://gitlab.com/opentasmania/oj-server.git
   cd oj-server
   ```

2. Ensure the script is executable:
   ```bash
   chmod +x install_kubernetes.py
   ```

## Basic Usage

The `kubernetes_installer.py` script can be used in two ways:

### Interactive Menu

For a guided experience, run the script without arguments:

```bash
./kubernetes_installer.py
```

This will display the main menu with options for deployment, destruction, and creating installer images.

### Command-Line Arguments

For scripted or automated use, you can provide command-line arguments:

```bash
./kubernetes_installer.py [action] [options]
```

To see all available options:

```bash
./kubernetes_installer.py --help
```

This will display help for the Kubernetes installer, showing available commands and options:

```
usage: kubernetes_installer.py [-h] [--env ENV] [--images [IMAGES ...]] [-v] [-d] [--overwrite] [--production]
                             {deploy,destroy,build-amd64,build-rpi64,build-deb,menu} ...

Kubernetes deployment script for OJM.

positional arguments:
  {deploy,destroy,build-amd64,build-rpi64,build-deb,menu}
                        The action to perform.

options:
  -h, --help            show this help message and exit
  --env ENV             The environment to target (e.g., 'local', 'staging'). Cannot be used with --production.
  --images [IMAGES ...] A space-delimited list of images to deploy or destroy. If not provided, all images will be processed.
  -v, --verbose         Enable verbose output.
  -d, --debug           Enable debug mode (implies --verbose and pauses before each step).
  --overwrite           Force overwrite of existing Docker images in the local registry. Only valid with 'deploy' action.
  --production          Target the production environment. Cannot be used with --env.
```

## Deployment Management

### Deploying to a Local Environment (Self-Signed Certificates)

To deploy to a local MicroK8s environment with self-signed certificates for Nginx:

```bash
./kubernetes_installer.py deploy --env local
```

The script will automatically detect if you're using MicroK8s and use the appropriate kubectl command. Nginx will be
configured to use automatically generated self-signed certificates for HTTPS.

### Deploying to a Production Environment (Certbot SSL)

To deploy to a production Kubernetes cluster with Certbot for SSL certificate management:

```bash
./kubernetes_installer.py deploy --production
```

Ensure your kubectl is configured to point to your production cluster before running this command. This will deploy
Certbot and configure Nginx to use certificates issued by Certbot.

### Destroying a Deployment

To remove a deployment and all its resources (deployments, jobs, statefulsets, daemonsets, and services):

```bash
./kubernetes_installer.py destroy --env local
```

or

```bash
./kubernetes_installer.py destroy --production
```

### Checking Deployment Status

After deployment, you can check the status of your pods:

```bash
# For MicroK8s
microk8s.kubectl get pods -n oj

# For standard Kubernetes
kubectl get pods -n oj
```

To view logs for a specific pod:

```bash
# For MicroK8s
microk8s.kubectl logs -f <pod-name >-n oj

# For standard Kubernetes
kubectl logs -f <pod-name >-n oj
```

## Creating Installer Images

The script can create custom Debian installer images that include the Kubernetes configurations:

### Creating an AMD64 Installer Image

To create a custom Debian installer image for AMD64 architecture:

```bash
./install_kubernetes.py build-amd64
```

This will:

1. Download the latest Debian testing netinst ISO
2. Verify its checksum
3. Extract and modify the ISO to include the OJ Server Kubernetes configurations
4. Create a new ISO that will automatically install OJ Server when used

The resulting image will be saved in the `images/` directory as `debian-trixie-amd64-microk8s-unattended.iso`.

### Creating a Raspberry Pi Installer Image

To create a custom Debian installer image for Raspberry Pi 3 or 4 (64-bit) with MicroK8s and OJ Server pre-installed.

```bash
./install_kubernetes.py build-rpi64
```

By default, this creates an image for Raspberry Pi 4. To specify a different model:

```bash
# When using the interactive menu, you'll be prompted for the model
# When using command line, you can specify the model in the interactive prompt
./install_kubernetes.py build-rpi64
```

The resulting image will be saved in the `images/` directory as `debian-trixie-rpi64-microk8s-unattended.img`.

### Creating a Debian Package

To create a standalone Debian package containing the Kubernetes configurations:

```bash
./install_kubernetes.py build-deb
```

This creates a `.deb` package that can be installed on any Debian-based system. The package will be saved in the
`images/` directory.

## Advanced Options

### Verbose Mode

For more detailed output during script execution:

```bash
./install_kubernetes.py deploy --env local -v
```

### Debug Mode

For step-by-step execution with pauses between each step (useful for troubleshooting):

```bash
./install_kubernetes.py deploy --env local -d
```

Debug mode automatically enables verbose mode and adds pauses before critical operations.

### Custom Environment Configurations

The script supports different environment configurations through Kustomize overlays:

1. **Local**: Optimized for local development with MicroK8s
    - Uses NodePort for service exposure
    - Configures minimal resource requirements
    - Points to the local MicroK8s registry

2. **Production**: Optimized for production deployments
    - Uses LoadBalancer for service exposure
    - Configures appropriate resource requests and limits
    - Points to a production container registry

To create a custom environment, you can:

1. Create a new directory under `kubernetes/overlays/`
2. Add your custom Kustomize patches
3. Use your custom environment with the `--env` flag:
   ```bash
   ./install_kubernetes.py deploy --env my-custom-env
   ```

## Troubleshooting

### Common Issues

#### MicroK8s Not Detected

**Symptom**: The script doesn't automatically detect MicroK8s.

**Solution**: Ensure MicroK8s is installed and in your PATH:

```bash
which microk8s
microk8s status
```

#### Permission Denied

**Symptom**: You receive "Permission denied" errors when running the script.

**Solution**: Make the script executable:

```bash
chmod +x install_kubernetes.py
```

#### Missing Dependencies

**Symptom**: The script reports missing tools or dependencies.

**Solution**: The script will attempt to install missing dependencies automatically. If this fails, you can install them
manually:

```bash
sudo apt update
sudo apt install python3 python3-pip wget xorriso isolinux grub-efi-amd64-bin dpkg-dev
```

#### Deployment Fails

**Symptom**: The deployment fails with Kubernetes errors.

**Solution**:

1. Check if your Kubernetes cluster is running:
   ```bash
   kubectl cluster-info
   # or for MicroK8s
   microk8s.kubectl cluster-info
   ```

2. Check for detailed error messages in the pod logs:
   ```bash
   kubectl get pods -n oj
   kubectl logs -f <pod-name> -n oj
   ```

3. Try destroying and redeploying:
   ```bash
   ./install_kubernetes.py destroy --env local
   ./install_kubernetes.py deploy --env local
   ```

### Getting Help

If you encounter issues not covered here:

1. Run the script in debug mode to get more information:
   ```bash
   ./install_kubernetes.py deploy --env local -d
   ```

2. Check the [GitLab issues page](https://gitlab.com/opentasmania/oj-server/-/issues) for known issues or to report a
   new one.

## Project Structure

The Kubernetes deployment uses the following directory structure:

```
oj-server/
├── install_kubernetes.py       # Main installer script
├── kubernetes/                 # Kubernetes configuration files
│   ├── base/                   # Base configurations (environment-agnostic)
│   │   ├── deployments/        # Deployment definitions
│   │   ├── services/           # Service definitions
│   │   ├── configmaps/         # ConfigMap definitions
│   │   └── kustomization.yaml  # Base Kustomize configuration
│   ├── components/             # Component-specific configurations
│   │   ├── postgres/           # PostgreSQL component
│   │   ├── osrm/               # OSRM component
│   │   └── ...                 # Other components
│   └── overlays/               # Environment-specific overlays
│       ├── local/              # Local development overlay
│       │   └── kustomization.yaml
│       └── production/         # Production overlay
│           └── kustomization.yaml
└── images/                     # Output directory for installer images
```

This structure follows the Kustomize best practices for managing Kubernetes configurations across different
environments.

---

By following this guide, you should be able to effectively use the `install_kubernetes.py` script to deploy and manage
the Open Journey Server using Kubernetes. The script provides a flexible and powerful way to handle both local
development and production deployments.
