# OpenJourney Server Plugins

This directory contains plugins for the OpenJourney Server. Plugins are standalone components that can be developed
independently and then integrated with the main OpenJourney Server project.

## Plugin Structure

Each plugin should have the following structure:

```
plugins/
└── plugin_name/
    ├── Dockerfile                  # Required: Used to build the plugin's Docker image
    ├── kubernetes/                 # Optional: Kubernetes-related files
    │   ├── deployment.yaml         # Optional: Kubernetes deployment manifest
    │   ├── service.yaml            # Optional: Kubernetes service manifest
    │   ├── configmap.yaml          # Optional: Kubernetes configmap manifest
    │   ├── kustomization.yaml      # Recommended: Kustomize configuration for this plugin
    │   └── resource_mapping.py     # Deprecated: Use kustomization.yaml instead
    └── ...                         # Other plugin files
```

## Adding a New Plugin

To add a new plugin:

1. Create a new directory under the `plugins` directory with your plugin name.
2. Add a `Dockerfile` to build your plugin's Docker image.
3. Optionally, add Kubernetes manifests in a `kubernetes` directory.
4. Add a `kubernetes/kustomization.yaml` file to define the Kubernetes resources for your plugin.
   - This file should list all the Kubernetes resource files (deployment.yaml, service.yaml, etc.) in the `resources` section.
   - Example:
     ```yaml
     apiVersion: kustomize.config.k8s.io/v1beta1
     kind: Kustomization
     resources:
       - deployment.yaml
       - service.yaml
     ```

## Plugin Detection

The OpenJourney Server automatically detects plugins in the `plugins` directory during deployment. It looks for:

1. A `Dockerfile` to build the plugin's Docker image.
2. A `kubernetes/kustomization.yaml` file to define the Kubernetes resources for the plugin.
   - For backward compatibility, it will also look for a `kubernetes/resource_mapping.py` file, but this is deprecated.

If a plugin doesn't have a `kustomization.yaml` or `resource_mapping.py` file, the server will use default resource names based on the plugin name (typically `<plugin_name>-deployment` and `<plugin_name>-service`).

## Example Plugin

The `openjourney_converter` plugin is an example of a plugin that can be used as a reference for creating new plugins.
