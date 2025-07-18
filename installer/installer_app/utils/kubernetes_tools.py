# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import sys
from typing import Dict, List, Optional

import yaml

from .common import run_command

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

ALL_IMAGES: Dict[str, str] = {
    "nodejs": "node:latest",
    "postgres": "postgis/postgis:16-3.4",
    "carto": "kubernetes/components/carto/Dockerfile",
    "apache": "kubernetes/components/apache/Dockerfile",
    "renderd": "kubernetes/components/renderd/Dockerfile",
    "pg_tileserv": "kubernetes/components/pg_tileserv/Dockerfile",
    "osrm": "osrm/osrm-backend:latest",
    "nginx": "nginx:latest",
    "pgadmin": "dpage/pgadmin4:latest",
    "pgagent": "kubernetes/components/pgagent/Dockerfile",
    "py3gtfskit": "kubernetes/components/py3gtfskit/Dockerfile",
}

# Scan plugins directory for additional tools to install
PLUGINS_DIR = os.path.join(PROJECT_ROOT, "plugins")
if os.path.exists(PLUGINS_DIR) and os.path.isdir(PLUGINS_DIR):
    for plugin_name in os.listdir(PLUGINS_DIR):
        plugin_path = os.path.join(PLUGINS_DIR, plugin_name)
        if os.path.isdir(plugin_path):
            dockerfile_path = os.path.join(plugin_path, "Dockerfile")
            if os.path.exists(dockerfile_path):
                ALL_IMAGES[plugin_name] = f"plugins/{plugin_name}/Dockerfile"
                print(f"Found plugin: {plugin_name}")


def _purge_images_from_local_registry(
    images: Optional[List[str]] = None,
) -> None:
    """
    Purges the specified Docker images from the local registry or all managed images
    if no specific images are provided. This function first checks if the images
    exist in the local registry and removes them if found.

    Args:
        images (Optional[List[str]]): A list of image names to purge. If not
            provided, all managed images are purged.

    Raises:
        SubprocessError: Raised if there are issues executing the Docker
            commands for inspecting or removing images.
    """
    print("\n--- Purging images from local registry ---")

    images_to_purge = get_managed_images() if images is None else images

    for image_name in images_to_purge:
        local_image_tag = f"localhost:32000/{image_name}"
        check_command = ["docker", "image", "inspect", local_image_tag]
        result = run_command(check_command, check=False, capture_output=True)
        if result.returncode == 0:
            print(f"Removing image '{local_image_tag}'...")
            run_command(["docker", "rmi", local_image_tag], check=True)
        else:
            print(f"Image '{local_image_tag}' not found. Skipping removal.")


def _apply_or_delete_components(
    action: str,
    kubectl: str,
    kustomize_path: str,
    images: List[str],
    plugin_manager,
) -> None:
    """
    Applies or deletes Kubernetes components filtered by specific criteria based on the
    resources' metadata or their association with specified images. Resources are processed
    through kustomization and then the subset of matching resources is either applied to or
    deleted from the Kubernetes cluster.

    Args:
        action (str): The action to perform, either 'apply' or 'delete', to manage the
            resources in the cluster.
        kubectl (str): Path to the `kubectl` command-line tool used for Kubernetes operations.
        kustomize_path (str): Path to the Kustomize configuration directory containing the
            Kubernetes manifests.
        images (List[str]): List of image names used to filter resources based on whether
            they are associated with these images.

    Raises:
        SystemExit: If the process to apply or delete resources fails.

    """
    kustomize_command = [kubectl, "kustomize", kustomize_path]
    kustomized_yaml_str = run_command(
        kustomize_command, check=True, capture_output=True
    ).stdout

    kustomized_yaml_str = plugin_manager.run_hook(
        "pre_apply_k8s", kustomized_yaml_str
    )

    all_resources = list(yaml.safe_load_all(kustomized_yaml_str))

    filtered_resources = []
    for resource in all_resources:
        if resource is None:
            continue

        resource_name = resource.get("metadata", {}).get("name", "")

        if any(image in resource_name for image in images):
            filtered_resources.append(resource)
        elif resource.get("kind") in [
            "Deployment",
            "Job",
            "StatefulSet",
            "DaemonSet",
        ]:
            containers = (
                resource.get("spec", {})
                .get("template", {})
                .get("spec", {})
                .get("containers", [])
            )
            if any(
                any(image in container.get("image", "") for image in images)
                for container in containers
            ):
                filtered_resources.append(resource)
        elif resource.get("kind") == "Namespace":
            filtered_resources.append(resource)

    if not filtered_resources:
        print(
            "No matching resources found for the specified images.",
            file=sys.stderr,
        )
        return

    filtered_yaml_str = ""
    for resource in filtered_resources:
        filtered_yaml_str += (
            yaml.dump(resource, default_flow_style=False, sort_keys=False)
            + "---\n"
        )

    command = [kubectl, action, "-f", "-"]
    print(f"Command: {command}")
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = process.communicate(
        input=filtered_yaml_str.encode("utf-8")
    )

    if process.returncode != 0:
        print(
            f"Error applying/deleting components: {stderr.decode('utf-8')}",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        print(stdout.decode("utf-8"))


def _setup_dashboard(kubectl: str):
    """
    Enables the MicroK8s dashboard, generates a token, saves it, and sets up port forwarding.
    """
    print("\n--- Setting up Kubernetes Dashboard ---")

    # 1. Enable Dashboard Addon
    print("--- Enabling dashboard addon... ---")
    run_command([kubectl.split(".")[0], "enable", "dashboard"], check=True)

    print(
        "--- Waiting for Kubernetes Dashboard deployment to be ready... ---"
    )
    run_command(
        [
            kubectl,
            "wait",
            "--for=condition=available",
            "deployment/dashboard-metrics-scraper",
            "-n",
            "kube-system",
            "--timeout=300s",
        ],
        check=True,
    )
    run_command(
        [
            kubectl,
            "wait",
            "--for=condition=available",
            "deployment/kubernetes-dashboard",
            "-n",
            "kube-system",
            "--timeout=300s",
        ],
        check=True,
    )

    print("--- Generating dashboard access token... ---")
    try:
        dashboard_token = run_command(
            [kubectl, "create", "token", "default", "-n", "kube-system"],
            check=True,
            capture_output=True,
        ).stdout.strip()

        token_file_path = os.path.join(PROJECT_ROOT, "kubernetes-token.txt")
        with open(file=token_file_path, mode="w", buffering=1) as f:
            f.write(dashboard_token + "\n")
        print(f"Dashboard token saved to {token_file_path}")

    except Exception as e:
        print(
            f"Error generating or saving dashboard token: {e}",
            file=sys.stderr,
        )
        sys.exit(1)

    _manage_dashboard_port_forward_service(kubectl)
    print("Dashboard setup complete. Use the token above to log in.")


def _manage_dashboard_port_forward_service(kubectl: str):
    """
    Manages the systemd service for Kubernetes Dashboard port forwarding.
    Checks if the service exists, is enabled, and is active. If not, it creates,
    enables, and starts the service.
    """
    print("\n--- Managing Kubernetes Dashboard Port Forward Service ---")

    service_name = "microk8s-dashboard-port-forward.service"
    service_file_path = f"/etc/systemd/system/{service_name}"
    current_user = os.environ.get("USER", "root")

    service_content = f"""[Unit]
Description=MicroK8s Kubernetes Dashboard Port Forward
After=network.target

[Service]
Type=simple
ExecStart=/snap/bin/microk8s.kubectl port-forward -n kube-system service/kubernetes-dashboard 10443:443
Restart=on-failure
User={current_user}
Group={current_user}
WorkingDirectory={PROJECT_ROOT}

[Install]
WantedBy=multi-user.target
"""
    service_exists = os.path.exists(service_file_path)
    is_enabled = False
    is_active = False

    if service_exists:
        print(
            f"Service file {service_file_path} already exists. Checking status..."
        )
        # Check if enabled
        enabled_result = run_command(
            ["systemctl", "is-enabled", service_name],
            check=False,
            capture_output=True,
        )
        if enabled_result.returncode == 0:
            is_enabled = True
            print(f"Service {service_name} is enabled.")
        else:
            print(f"Service {service_name} is not enabled.")

        # Check if active
        active_result = run_command(
            ["systemctl", "is-active", service_name],
            check=False,
            capture_output=True,
        )
        if active_result.returncode == 0:
            is_active = True
            print(f"Service {service_name} is active.")
        else:
            print(f"Service {service_name} is not active.")

    if not service_exists or not is_enabled or not is_active:
        print(f"Creating/Updating and starting {service_name}...")
        try:
            # Write the service file
            run_command(
                [
                    "sudo",
                    "bash",
                    "-c",
                    f"echo '{service_content}' > {service_file_path}",
                ],
                check=True,
            )
            print(f"Service file written to {service_file_path}.")

            # Reload systemd daemon
            run_command(["sudo", "systemctl", "daemon-reload"], check=True)
            print("Systemd daemon reloaded.")

            # Enable the service
            run_command(
                ["sudo", "systemctl", "enable", service_name], check=True
            )
            print(f"Service {service_name} enabled.")

            # Start the service
            run_command(
                ["sudo", "systemctl", "start", service_name], check=True
            )
            print(f"Service {service_name} started.")
            print("Dashboard port-forwarding is managed by systemd.")
        except Exception as e:
            print(
                f"Error managing systemd service for dashboard port-forward: {e}",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        print(
            f"Dashboard port-forward service {service_name} is already enabled and active."
        )
        print("Access at https://localhost:10443")


def _check_microk8s_addons():
    """
    Checks if the required MicroK8s addons are enabled and exits if they are not.
    """
    print("\n--- Checking MicroK8s addon status ---")
    try:
        status_output = run_command(
            ["microk8s", "status", "--format=yaml"],
            check=True,
            capture_output=True,
        )
        status_data = yaml.safe_load(status_output.stdout)
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        yaml.YAMLError,
    ) as e:
        print(f"Error getting MicroK8s status: {e}", file=sys.stderr)
        print(
            "Could not verify addon status. Please ensure MicroK8s is running correctly.",
            file=sys.stderr,
        )
        sys.exit(1)

    required_addons = {
        "dns",
        "storage",
        "registry",
        "ingress",
        "hostpath-storage",
    }
    enabled_addons = set()

    for addon in status_data.get("addons", []):
        if (
            addon.get("name") in required_addons
            and addon.get("status") == "enabled"
        ):
            enabled_addons.add(addon["name"])

    missing_addons = required_addons - enabled_addons
    if missing_addons:
        print(
            "The following required MicroK8s addons are not enabled. Attempting to enable them:",
            file=sys.stderr,
        )
        for addon in sorted(missing_addons):
            print(f"  - {addon}", file=sys.stderr)
            try:
                run_command(["microk8s", "enable", addon], check=True)
                print(f"Successfully enabled {addon}.")
            except subprocess.CalledProcessError as e:
                print(
                    f"Error: Failed to enable MicroK8s addon '{addon}'. It might be missing or there's a system issue.",
                    file=sys.stderr,
                )
                print(f"Details: {e}", file=sys.stderr)
                sys.exit(1)
        print("All previously missing MicroK8s addons are now enabled.")

    print("All required MicroK8s addons are enabled.")


def _build_and_register_images_for_local_env(
    kubectl: str, images: Optional[List[str]] = None, overwrite: bool = False
) -> None:
    """
    Builds and registers Docker images for use in a local MicroK8s Kubernetes environment.

    This function facilitates the building and importing of Docker images into the
    local MicroK8s registry. It uses predefined or provided image configurations and
    supports both custom Dockerfile-based images and standard images pulled from external
    repositories. Additionally, the function validates requirements, manages overwrites,
    and processes images efficiently.

    If not already present, this function can create a data processor Dockerfile specifically
    for the `data_processing` image, enhancing its utility in certain use cases.

    Args:
        kubectl (str): The kubectl command to interact with Kubernetes. Expected to be
            compatible with 'microk8s.kubectl'.
        images (Optional[List[str]]): A list of image names to process. If None, all
            available images will be processed.
        overwrite (bool): Flag to determine whether to overwrite existing images in the
            local MicroK8s registry. Defaults to False.
    """
    print(
        "\n--- Building and registering images for local MicroK8s environment ---"
    )

    if not shutil.which("docker"):
        print(
            "Error: 'docker' command not found. Please install Docker.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not kubectl.startswith("microk8s"):
        print(
            "Warning: Not using 'microk8s.kubectl'. This function is designed for MicroK8s."
        )
        print(
            "It will attempt to push to 'localhost:32000', which might require 'docker login'."
        )

    images_to_process = ALL_IMAGES
    if images is not None:
        images_to_process = {
            name: source
            for name, source in ALL_IMAGES.items()
            if name in images
        }
        missing_images = set(images) - set(images_to_process.keys())
        if missing_images:
            print(
                f"Warning: The following specified images are not defined and will be skipped: {', '.join(missing_images)}",
                file=sys.stderr,
            )

    if not images_to_process:
        print("No images selected to process.")
        return

    for name, source in images_to_process.items():
        print(f"\nProcessing image: {name}")
        local_image_tag = f"localhost:32000/{name}"

        if not overwrite:
            check_command = ["docker", "image", "inspect", local_image_tag]
            result = run_command(
                check_command, check=False, capture_output=True
            )
            if result.returncode == 0:
                print(f"Image '{local_image_tag}' already exists. Skipping.")
                continue

        if source.endswith("Dockerfile"):
            dockerfile_path = os.path.join(PROJECT_ROOT, source)
            if not os.path.exists(dockerfile_path):
                print(
                    f"Warning: Dockerfile not found at '{dockerfile_path}' for '{name}'. Skipping."
                )
                continue

            print(
                f"Building custom image '{local_image_tag}' from '{dockerfile_path}'..."
            )
            build_command = [
                "docker",
                "build",
                "-t",
                local_image_tag,
                "-f",
                dockerfile_path,
                PROJECT_ROOT,
            ]
            run_command(build_command, check=True)

        else:
            print(f"Pulling standard image '{source}'...")
            run_command(["docker", "pull", source], check=True)
            print(f"Retagging '{source}' to '{local_image_tag}'...")
            run_command(
                ["docker", "tag", source, local_image_tag], check=True
            )

        print(f"Importing '{local_image_tag}' into MicroK8s registry...")

        save_process = subprocess.Popen(
            ["docker", "save", local_image_tag], stdout=subprocess.PIPE
        )
        import_command = [
            kubectl.split(".")[0],
            "ctr",
            "image",
            "import",
            "-",
        ]
        import_process = subprocess.run(
            import_command,
            stdin=save_process.stdout,
            capture_output=True,
            text=True,
        )

        if save_process.stdout:
            save_process.stdout.close()

        save_process.wait()

        if import_process.returncode != 0:
            print(
                f"Error importing image '{local_image_tag}' into MicroK8s.",
                file=sys.stderr,
            )
            print(f"STDERR: {import_process.stderr}", file=sys.stderr)
            sys.exit(1)

        print(f"Successfully processed image: {name}")

    print("\n--- Image building and registration complete ---")


def get_kubectl_command() -> str:
    """
    Determines the appropriate kubectl command for MicroK8s usage.

    If MicroK8s is not found on the system, attempts to detect the operating system and install MicroK8s
    via Snap if applicable. The function ensures MicroK8s is properly initialized and attempts to
    configure the current user for interaction with MicroK8s, including adding the user to the
    appropriate user group if necessary. Users may need to log out and back in after the script makes
    certain changes.

    Returns:
        str: The command to use for kubectl within MicroK8s.

    Raises:
        SystemExit: If MicroK8s is not found and cannot be installed, or if it fails to properly initialize.
    """
    if not shutil.which("microk8s"):
        if sys.platform == "linux" and shutil.which("snap"):
            print(
                "MicroK8s not found, but Snap is installed. Attempting to install MicroK8s...",
                file=sys.stderr,
            )
            try:
                print("Attempting to install MicroK8s...")
                run_command(
                    ["sudo", "snap", "install", "microk8s", "--classic"],
                    check=True,
                )

                print("Waiting for MicroK8s to settle...")
                max_attempts = 30
                for i in range(max_attempts):
                    command_to_run = [
                        "sudo",
                        "/snap/bin/microk8s",
                        "status",
                        "--wait-ready",
                    ]
                    status_result = run_command(
                        command_to_run, check=False, capture_output=True
                    )
                    if "microk8s is running" in status_result.stdout.lower():
                        print("MicroK8s is running and settled.")
                        break
                    print(
                        f"MicroK8s not yet ready (attempt {i + 1}/{max_attempts})... Waiting 10 seconds."
                    )
                    import time

                    time.sleep(10)
                else:
                    print(
                        "Error: MicroK8s did not become ready within the expected time.",
                        file=sys.stderr,
                    )
                    sys.exit(1)

                current_user = os.environ.get("USER", "")
                if current_user:
                    groups_output = run_command(
                        ["id", "-Gn", current_user],
                        check=True,
                        capture_output=True,
                    ).stdout.strip()
                    if "microk8s" not in groups_output.split():
                        print(
                            f"Adding user '{current_user}' to 'microk8s' group..."
                        )
                        run_command(
                            [
                                "sudo",
                                "usermod",
                                "-a",
                                "-G",
                                "microk8s",
                                current_user,
                            ],
                            check=True,
                        )
                        print("User added to microk8s group.")
                        print(
                            "MicroK8s installed. Please log out and log back in for group changes to take effect, then re-run this script.",
                            file=sys.stderr,
                        )
                        sys.exit(1)
                    else:
                        print(
                            f"User '{current_user}' is already in 'microk8s' group."
                        )
                else:
                    print(
                        "Warning: Could not determine current user to add to microk8s group.",
                        file=sys.stderr,
                    )

                run_command(
                    [
                        "sudo",
                        "chown",
                        "-f",
                        "-R",
                        os.environ.get("USER", ""),
                        os.path.expanduser("~/.kube"),
                    ],
                    check=True,
                )
            except Exception as e:
                print(f"Error installing MicroK8s: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print(
                "Error: 'microk8s' command not found.",
                file=sys.stderr,
            )
            print(
                "This script is designed for a MicroK8s environment. Please install MicroK8s.",
                file=sys.stderr,
            )
            print(
                "Installation instructions: https://microk8s.io/docs/getting-started",
                file=sys.stderr,
            )
            sys.exit(1)
    return "microk8s.kubectl"


def get_managed_images() -> List[str]:
    """Returns a list of all manageable image names."""
    return list(ALL_IMAGES.keys())


def deploy(
    env: str,
    kubectl: str,
    plugin_manager,
    is_installed: bool = False,
    images: Optional[List[str]] = None,
    overwrite: bool = False,
    production: bool = False,
) -> None:
    """
    Deploys the specified environment using kustomize and kubectl.

    This function handles the deployment process, allowing for optional
    installation of specific images or entire components for a given
    environment. It also processes local environment customizations
    separately.

    Args:
        env (str): The environment to deploy (e.g., "local", "dev", "prod").
        kubectl (str): The path to the `kubectl` command-line tool.
        is_installed (bool, optional): Indicates whether the environment is
            already installed. Defaults to False.
        images (Optional[List[str]], optional): A list of images or components
            to deploy. If None, all components are deployed. Defaults to None.
        overwrite (bool, optional): Whether to overwrite existing image
            registrations in a local environment. Defaults to False.

    Raises:
        SystemExit: If the specified kustomize path does not exist.

    """
    try:
        print(f"Deploying '{env}' environment...")

        _check_microk8s_addons()
        _setup_dashboard(kubectl)

        if production:
            env = "production"
        else:
            env = "local"
        if env == "local":
            _build_and_register_images_for_local_env(
                kubectl, images, overwrite
            )

        if is_installed:
            kustomize_path = f"/opt/oj-server/kubernetes/overlays/{env}"
        else:
            kustomize_path = os.path.join(
                PROJECT_ROOT, "kubernetes", "overlays", env
            )

        if not os.path.isdir(kustomize_path):
            print(
                f"Error: Kustomize path not found at '{kustomize_path}'",
                file=sys.stderr,
            )
            sys.exit(1)

        if images is not None:
            print(f"Deploying specified components: {', '.join(images)}")
            _apply_or_delete_components(
                "apply", kubectl, kustomize_path, images, plugin_manager
            )
        else:
            print("Deploying all components...")
            command: List[str] = [kubectl, "apply", "-k", kustomize_path]
            run_command(command, check=True)
        plugin_manager.run_hook("on_install_complete")
    except Exception as e:
        plugin_manager.run_hook("on_error", e)
        print(f"An error occurred during deployment: {e}", file=sys.stderr)
        sys.exit(1)


def destroy(
    env: str,
    kubectl: str,
    plugin_manager,
    images: Optional[List[str]] = None,
) -> None:
    """
    Destroys specified resources in the given environment.

    This function deletes specific Kubernetes resources managed in the provided
    environment by determining their mapping from predefined resource names.
    If no images are provided, it retrieves all managed images and deletes their
    associated deployments, jobs, or other Kubernetes resources. Finally, it purges
    the relevant images from the local registry.

    Args:
        env (str): The environment in which the resources are deployed.
        kubectl (str): The command-line tool used to execute Kubernetes commands.
        images (Optional[List[str]]): A list of images whose associated resources
            need to be destroyed. If None, all managed images will be considered.

    """
    try:
        print(f"Destroying '{env}' environment...")

        resource_mapping = {
            "postgres": ["postgres-deployment", "postgres-service"],
            "osrm": ["osrm-deployment", "osrm-service"],
            "nginx": ["nginx-deployment", "nginx-service"],
            "nodejs": ["nodejs-deployment", "nodejs-service"],
            "pgadmin": ["pgadmin-deployment", "pgadmin-service"],
            "data_processing": ["gtfs-processing-job"],
            "apache": ["apache-deployment", "apache-service"],
            "carto": ["carto-deployment", "carto-service"],
            "pgagent": ["pgagent-deployment"],
            "pg_tileserv": ["pg-tileserv-deployment", "pg-tileserv-service"],
            "py3gtfskit": ["py3gtfskit-job"],
            "renderd": ["renderd-deployment", "renderd-service"],
        }

        # Add resource mappings for plugins
        PLUGINS_DIR = os.path.join(PROJECT_ROOT, "plugins")
        if os.path.exists(PLUGINS_DIR) and os.path.isdir(PLUGINS_DIR):
            for plugin_name in os.listdir(PLUGINS_DIR):
                plugin_path = os.path.join(PLUGINS_DIR, plugin_name)
                if os.path.isdir(plugin_path):
                    # Default resource mapping for plugins: deployment and service with the plugin name
                    resource_mapping[plugin_name] = [
                        f"{plugin_name}-deployment",
                        f"{plugin_name}-service",
                    ]

                    # Check if the plugin has a kustomization.yaml file
                    kustomization_file = os.path.join(
                        plugin_path, "kubernetes", "kustomization.yaml"
                    )

                    # For backward compatibility, also check for resource_mapping.py
                    mapping_file = os.path.join(
                        plugin_path, "kubernetes", "resource_mapping.py"
                    )

                    if os.path.exists(kustomization_file):
                        try:
                            # Parse the kustomization.yaml file to extract resources
                            with open(kustomization_file, "r") as f:
                                kustomization = yaml.safe_load(f)

                            # Extract resources from the kustomization file
                            resources = []

                            # Get resources from the 'resources' field
                            if "resources" in kustomization and isinstance(
                                kustomization["resources"], list
                            ):
                                for resource in kustomization["resources"]:
                                    # Extract the base name without extension and add appropriate suffixes
                                    base_name = os.path.splitext(resource)[0]
                                    if "deployment" in base_name.lower():
                                        resources.append(f"{base_name}")
                                    elif "service" in base_name.lower():
                                        resources.append(f"{base_name}")
                                    elif "job" in base_name.lower():
                                        resources.append(f"{base_name}")
                                    elif "statefulset" in base_name.lower():
                                        resources.append(f"{base_name}")
                                    elif "daemonset" in base_name.lower():
                                        resources.append(f"{base_name}")
                                    else:
                                        # For other resources, assume they follow the pattern: <name>-<kind>
                                        resources.append(f"{base_name}")

                            if resources:
                                resource_mapping[plugin_name] = resources
                        except Exception as e:
                            print(
                                f"Warning: Failed to load kustomization.yaml for plugin {plugin_name}: {e}"
                            )
                            # Keep the default mapping
                    elif os.path.exists(mapping_file):
                        try:
                            # Use a subprocess to safely extract the resource mapping from the plugin
                            import importlib.util

                            module = None
                            spec = importlib.util.spec_from_file_location(
                                "resource_mapping", mapping_file
                            )
                            if spec is not None:
                                module = importlib.util.module_from_spec(spec)
                                if spec.loader is not None:
                                    spec.loader.exec_module(module)

                            if (
                                module is not None
                                and hasattr(module, "RESOURCE_MAPPING")
                                and isinstance(module.RESOURCE_MAPPING, list)
                            ):
                                resource_mapping[plugin_name] = (
                                    module.RESOURCE_MAPPING
                                )
                        except Exception as e:
                            print(
                                f"Warning: Failed to load resource mapping for plugin {plugin_name}: {e}"
                            )
                            # Keep the default mapping

        images_to_destroy = get_managed_images() if images is None else images

        resources_to_delete = []
        for image in images_to_destroy:
            resources = resource_mapping.get(image, [])
            if resources:
                for resource in resources:
                    print(f"Checking for {resource}")
                    resources_to_delete.append(f"{env}-{resource}")

        if not resources_to_delete:
            print("No components specified to destroy.")
        else:
            print(f"Destroying resources: {', '.join(resources_to_delete)}")
            command = [
                kubectl,
                "delete",
                "deployments,jobs,statefulsets,daemonsets,services",
                *resources_to_delete,
                "--ignore-not-found=true",
            ]
            run_command(command, check=True)

        _purge_images_from_local_registry(images)
    except Exception as e:
        plugin_manager.run_hook("on_error", e)
        print(f"An error occurred during destroy: {e}", file=sys.stderr)
        sys.exit(1)
