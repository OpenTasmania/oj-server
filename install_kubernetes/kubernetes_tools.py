# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import sys
from typing import Dict, List, Optional

import yaml

from install_kubernetes.common import run_command

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

ALL_IMAGES: Dict[str, str] = {
    "nodejs": "node:latest",
    "postgres": "postgis/postgis:16-3.4",
    "carto": "kubernetes/components/carto/Dockerfile",
    "apache": "kubernetes/components/apache/Dockerfile",
    "renderd": "kubernetes/components/renderd/Dockerfile",
    "pg_tileserv": "kubernetes/components/pg_tileserv/Dockerfile",
    "data_processing": "data_processor/Dockerfile",
    "osrm": "osrm/osrm-backend:latest",
    "nginx": "nginx:latest",
    "certbot": "certbot/certbot:latest",
    "pgadmin": "dpage/pgadmin4:latest",
    "pgagent": "kubernetes/components/pgagent/Dockerfile",
    "py3gtfskit": "kubernetes/components/py3gtfskit/Dockerfile",
}


def get_managed_images() -> List[str]:
    """Returns a list of all manageable image names."""
    return list(ALL_IMAGES.keys())


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

    data_processor_dockerfile_path = os.path.join(
        PROJECT_ROOT, "data_processor", "Dockerfile"
    )
    os.makedirs(
        os.path.dirname(data_processor_dockerfile_path), exist_ok=True
    )
    if (
        not os.path.exists(data_processor_dockerfile_path)
        and "data_processing" in images_to_process
    ):
        print(
            f"Creating Dockerfile for data_processor at {data_processor_dockerfile_path}"
        )
        with open(data_processor_dockerfile_path, "w") as f:
            f.write("""# Use a slim Python base image
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /app

# Copy and install Python dependencies
COPY uv.lock .
RUN pip install --no-cache-dir uv
RUN uv pip install --no-cache-dir .[dev]

# Copy the necessary application code
COPY common/ ./common/
COPY installer/processors/ ./installer/processors/
COPY data_processor/run.py .

CMD ["python", "run.py"]
""")

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
    Determines and returns the appropriate `kubectl` command to use based on the availability
    of `microk8s` and `kubectl` in the system. If neither is available, prompts the user to
    choose an option and provides instructions for installing the selected tool.

    Returns:
        str: The determined `kubectl` command to use.

    Raises:
        SystemExit: If neither `microk8s` nor `kubectl` is available and the user decides
        to exit after viewing installation instructions.
    """
    has_microk8s: Optional[str] = shutil.which("microk8s")
    has_kubectl: Optional[str] = shutil.which("kubectl")

    if has_microk8s and has_kubectl:
        while True:
            print(
                "Both 'microk8s' and 'kubectl' are available. Which one would you like to use?"
            )
            print("1. microk8s")
            print("2. kubectl")
            choice: str = input("Please enter your choice (1/2): ")
            if choice == "1":
                return "microk8s.kubectl"
            elif choice == "2":
                return "kubectl"
            print("Invalid choice. Please enter '1' or '2'.")
    elif has_microk8s:
        return "microk8s.kubectl"
    elif has_kubectl:
        return "kubectl"
    else:
        while True:
            print(
                "Neither 'microk8s' nor 'kubectl' were found. Which would you like to install?"
            )
            print("1. microk8s")
            print("2. kubectl")
            choice = input("Please enter your choice (1/2): ")
            if choice == "1":
                print(
                    "MicroK8s is a lightweight, single-node Kubernetes distribution."
                )
                print(
                    "Installation instructions: https://microk8s.io/docs/getting-started"
                )
                sys.exit(1)
            elif choice == "2":
                print(
                    "kubectl is the command-line tool for interacting with a Kubernetes cluster."
                )
                print(
                    "Installation instructions: https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/"
                )
                sys.exit(1)
            print("Invalid choice. Please enter '1' or '2'.")


# TODO: Use something like this when in Production mode
def install_cert_manager(self):
    """
    Installs cert-manager into the cluster.
    """
    self.log_message("Installing cert-manager...")
    cert_manager_url = "https://github.com/cert-manager/cert-manager/releases/download/v1.14.5/cert-manager.yaml"

    # Command to apply the cert-manager manifest
    install_command = ["kubectl", "apply", "-f", cert_manager_url]

    # Command to wait for the cert-manager deployment to be ready
    wait_command = [
        "kubectl",
        "wait",
        "--for=condition=Available",
        "deployment",
        "-n",
        "cert-manager",
        "--all",
        "--timeout=300s",
    ]

    try:
        # First, apply the manifest
        self.run_command(
            install_command, "Failed to apply cert-manager manifest"
        )
        self.log_message("cert-manager manifest applied successfully.")

        # Then, wait for the deployments to be available
        self.log_message("Waiting for cert-manager pods to be ready...")
        self.run_command(
            wait_command,
            "cert-manager deployment failed to become ready in time.",
        )
        self.log_message("cert-manager is installed and ready.")

    except Exception as e:
        self.log_message(
            f"An error occurred during cert-manager installation: {e}",
            "error",
        )
        raise


def deploy(
    env: str,
    kubectl: str,
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
    print(f"Deploying '{env}' environment...")

    if production:
        env = "production"
    else:
        env = "local"
    if env == "local":
        _build_and_register_images_for_local_env(kubectl, images, overwrite)

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
        _apply_or_delete_components("apply", kubectl, kustomize_path, images)
    else:
        print("Deploying all components...")
        command: List[str] = [kubectl, "apply", "-k", kustomize_path]
        run_command(command, check=True)


def destroy(
    env: str,
    kubectl: str,
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
    print(f"Destroying '{env}' environment...")

    resource_mapping = {
        "postgres": ["postgres-deployment", "postgres-service"],
        "osrm": ["osrm-deployment", "osrm-service"],
        "nginx": ["nginx-deployment", "nginx-service"],
        "nodejs": ["nodejs-deployment", "nodejs-service"],
        "certbot": ["certbot-job"],
        "pgadmin": ["pgadmin-deployment", "pgadmin-service"],
        "data_processing": ["gtfs-processing-job"],
        "apache": ["apache-deployment", "apache-service"],
        "carto": ["carto-deployment", "carto-service"],
        "pgagent": ["pgagent-deployment"],
        "pg_tileserv": ["pg-tileserv-deployment", "pg-tileserv-service"],
        "py3gtfskit": ["py3gtfskit-job"],
        "renderd": ["renderd-deployment", "renderd-service"],
    }

    images_to_destroy = get_managed_images() if images is None else images

    resources_to_delete = []
    for image in images_to_destroy:
        resources = resource_mapping.get(image)
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
            "--namespace",
            "oj",
            "--ignore-not-found=true",
            "-v",
            "3",
        ]
        run_command(command, check=True)

    _purge_images_from_local_registry(images)


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
    action: str, kubectl: str, kustomize_path: str, images: List[str]
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
        elif resource.get("kind") == "Namespace" and resource_name == "oj":
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
