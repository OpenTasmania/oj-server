import os
import shutil
import subprocess
import sys
from typing import Dict, List, Optional

_VERBOSE: bool = False
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def run_command(
    command: List[str],
    directory: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess:
    """
    Executes a command as a subprocess and handles its behavior based on the specified parameters.
    """
    if _VERBOSE:
        print(f"[VERBOSE] Executing: {' '.join(command)}")

    if _VERBOSE and command[0] in [
        "wget",
        "vmdb2",
        "dpkg",
        "apt",
        "apt-get",
        "python3",
        "docker",
        "kubectl",
        "microk8s.kubectl",
    ]:
        if "-v" not in command and "--verbose" not in command:
            insert_pos = 1
            if command[0] == "docker" and command[1] in ["build", "pull"]:
                insert_pos = 2
            command.insert(
                insert_pos, "--verbose" if command[0] == "docker" else "-v"
            )

    result = subprocess.run(
        command,
        cwd=directory,
        env=env,
        capture_output=capture_output,
        text=True,
    )
    if check and result.returncode != 0:
        print(
            f"Error: Command failed with exit code {result.returncode}",
            file=sys.stderr,
        )
        if capture_output:
            print(f"STDOUT: {result.stdout}", file=sys.stderr)
            print(f"STDERR: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result


def _build_and_register_images_for_local_env(kubectl: str) -> None:
    """
    Builds custom Docker images and pulls standard ones, then registers them
    with the local MicroK8s registry.
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

    images_to_process = {
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

    data_processor_dockerfile_path = os.path.join(
        PROJECT_ROOT, "..", "..", "data_processor", "Dockerfile"
    )
    os.makedirs(
        os.path.dirname(data_processor_dockerfile_path), exist_ok=True
    )
    if not os.path.exists(data_processor_dockerfile_path):
        print(
            f"Creating Dockerfile for data_processor at {data_processor_dockerfile_path}"
        )
        with open(data_processor_dockerfile_path, "w") as f:
            f.write("""# Use a slim Python base image
FROM python:3.9-slim

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

        if source.endswith("Dockerfile"):
            dockerfile_path = os.path.join(PROJECT_ROOT, "..", "..", source)
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
                os.path.join(PROJECT_ROOT, "..", ".."),
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


def deploy(env: str, kubectl: str, is_installed: bool = False) -> None:
    """
    Deploys the application using Kustomize.
    """
    print(f"Deploying '{env}' environment...")
    if env == "local":
        _build_and_register_images_for_local_env(kubectl)

    if is_installed:
        kustomize_path = f"/opt/ojp-server/kubernetes/overlays/{env}"
    else:
        kustomize_path = os.path.join(
            PROJECT_ROOT, "..", "..", "kubernetes", "overlays", env
        )

    if not os.path.isdir(kustomize_path):
        print(
            f"Error: Kustomize path not found at '{kustomize_path}'",
            file=sys.stderr,
        )
        sys.exit(1)

    command: List[str] = [kubectl, "apply", "-k", kustomize_path]
    run_command(command, check=True)


def destroy(env: str, kubectl: str, is_installed: bool = False) -> None:
    """
    Destroys the application deployment using Kustomize.
    """
    print(f"Destroying '{env}' environment...")
    if is_installed:
        kustomize_path = f"/opt/ojp-server/kubernetes/overlays/{env}"
    else:
        kustomize_path = os.path.join(
            PROJECT_ROOT, "..", "..", "kubernetes", "overlays", env
        )

    if not os.path.isdir(kustomize_path):
        print(
            f"Error: Kustomize path not found at '{kustomize_path}'",
            file=sys.stderr,
        )
        sys.exit(1)

    command: List[str] = [kubectl, "delete", "-k", kustomize_path]
    run_command(command, check=True)
