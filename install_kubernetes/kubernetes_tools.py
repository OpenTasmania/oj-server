# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import sys
from typing import Dict, List, Optional

import yaml

from install_kubernetes.common import run_command

# PROJECT_ROOT is correctly defined as the root of the project source
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

ALL_IMAGES: Dict[str, str] = {
    "postgres": "postgres:latest",
    "osrm": "osrm/osrm-backend:latest",
    "nginx": "nginx:latest",
    "nodejs": "node:latest",
    "certbot": "certbot/certbot:latest",
    "pgadmin": "dpage/pgadmin4:latest",
    "data_processing": "data_processor/Dockerfile",
    "apache": "kubernetes/components/apache/Dockerfile",
    "carto": "kubernetes/components/carto/Dockerfile",
    "pgagent": "kubernetes/components/pgagent/Dockerfile",
    "pg_tileserv": "kubernetes/components/pg_tileserv/Dockerfile",
    "py3gtfskit": "kubernetes/components/py3gtfskit/Dockerfile",
    "renderd": "kubernetes/components/renderd/Dockerfile",
}


def get_managed_images() -> List[str]:
    """Returns a list of all manageable image names."""
    return list(ALL_IMAGES.keys())


def _build_and_register_images_for_local_env(
    kubectl: str, images: Optional[List[str]] = None, overwrite: bool = False
) -> None:
    """
    Builds custom Docker images and pulls standard ones, then registers them
    with the local MicroK8s registry.
    If a list of images is provided, only those images are processed.
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
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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
            # --- FIX ---
            # The build context has been changed from os.path.join(PROJECT_ROOT, "..", "..")
            # to just PROJECT_ROOT. This ensures Docker looks for files in the correct directory.
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
    Determines the appropriate 'kubectl' command based on system availability.
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


def deploy(
    env: str,
    kubectl: str,
    is_installed: bool = False,
    images: Optional[List[str]] = None,
    overwrite: bool = False,
) -> None:
    """
    Deploys the application using Kustomize.
    If a list of images is provided, only the corresponding components are deployed.
    """
    print(f"Deploying '{env}' environment...")
    if env == "local":
        _build_and_register_images_for_local_env(kubectl, images, overwrite)

    if is_installed:
        kustomize_path = f"/opt/ojp-server/kubernetes/overlays/{env}"
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
    is_installed: bool = False,
    images: Optional[List[str]] = None,
) -> None:
    """
    Destroys the application deployment by deleting deployments and jobs,
    and purges the associated images from the local registry.
    If a list of images is provided, only the corresponding components are destroyed.
    """
    print(f"Destroying '{env}' environment...")

    resource_mapping = {
        "postgres": "postgres-deployment",
        "osrm": "osrm-deployment",
        "nginx": "nginx-deployment",
        "nodejs": "nodejs-deployment",
        "certbot": "certbot-job",
        "pgadmin": "pgadmin-deployment",
        "data_processing": "gtfs-processing-job",
        "apache": "apache-deployment",
        "carto": "carto-deployment",
        "pgagent": "pgagent-deployment",
        "pg_tileserv": "pg-tileserv-deployment",
        "py3gtfskit": "py3gtfskit-job",
        "renderd": "renderd-deployment",
    }

    images_to_destroy = get_managed_images() if images is None else images

    resources_to_delete = [
        f"{env}-{resource_mapping.get(image)}"
        for image in images_to_destroy
        if resource_mapping.get(image)
    ]

    if not resources_to_delete:
        print("No components specified to destroy.")
    else:
        print(f"Destroying resources: {', '.join(resources_to_delete)}")
        command = [
            kubectl,
            "delete",
            "deployments,jobs,statefulsets,daemonsets",
            *resources_to_delete,
            "--namespace",
            "ojp",
            "--ignore-not-found=true",
        ]
        run_command(command, check=True)

    _purge_images_from_local_registry(images)


def _purge_images_from_local_registry(
    images: Optional[List[str]] = None,
) -> None:
    """
    Removes specified Docker images from the local registry.
    """
    print("\n--- Purging images from local registry ---")

    images_to_purge = get_managed_images() if images is None else images

    for image_name in images_to_purge:
        local_image_tag = f"localhost:32000/{image_name}"
        print(f"Removing image '{local_image_tag}'...")
        run_command(["docker", "rmi", local_image_tag], check=False)


def _apply_or_delete_components(
    action: str, kubectl: str, kustomize_path: str, images: List[str]
) -> None:
    """
    Helper function to apply or delete a filtered set of Kustomize components.
    """
    # Generate the full kustomized YAML
    kustomize_command = [kubectl, "kustomize", kustomize_path]
    kustomized_yaml_str = run_command(
        kustomize_command, check=True, capture_output=True
    ).stdout

    # Parse the YAML into individual Kubernetes objects
    # yaml.safe_load_all returns a generator, so convert to list
    all_resources = list(yaml.safe_load_all(kustomized_yaml_str))

    filtered_resources = []
    for resource in all_resources:
        if resource is None:  # Skip empty documents
            continue

        # Check if the resource name or a part of its metadata matches any of the specified images
        # This logic might need refinement based on how resources are named in your Kustomize
        resource_name = resource.get("metadata", {}).get("name", "")

        # Simple check: if any image name is part of the resource name
        if any(image in resource_name for image in images):
            filtered_resources.append(resource)
        # More specific check: if the resource is a deployment/job/statefulset related to the image
        elif resource.get("kind") in [
            "Deployment",
            "Job",
            "StatefulSet",
            "DaemonSet",
        ]:
            # Check if the image name is in the containers' image names
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
        # Also include common resources like namespaces if they are not image-specific
        elif (
            resource.get("kind") == "Namespace" and resource_name == "ojp"
        ):  # Assuming 'ojp' is your main namespace
            filtered_resources.append(resource)

    if not filtered_resources:
        print(
            "No matching resources found for the specified images.",
            file=sys.stderr,
        )
        return

    # Dump the filtered resources back to YAML
    filtered_yaml_str = ""
    for resource in filtered_resources:
        filtered_yaml_str += (
            yaml.dump(resource, default_flow_style=False, sort_keys=False)
            + "---\n"
        )

    # Apply or delete the filtered YAML
    command = [kubectl, action, "-f", "-"]
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
