import click

from .utils.builders.amd64 import create_debian_installer_amd64
from .utils.builders.rpi64 import create_debian_installer_rpi64
from .utils.common import create_debian_package
from .utils.kubernetes_tools import deploy, destroy, get_kubectl_command
from .utils.plugin_manager import PluginManager


@click.group()
def cli():
    """A command-line interface for the OpenJourney installer."""
    pass


@cli.command(name="deploy")
@click.option("--env", default="local", help="The environment to target.")
@click.option(
    "--images",
    multiple=True,
    help="A space-delimited list of images to deploy.",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Force overwrite of existing Docker images.",
)
@click.option(
    "--production", is_flag=True, help="Target the production environment."
)
def deploy_command(env, images, overwrite, production):
    """Deploys the application."""
    plugin_manager = PluginManager()
    kubectl_cmd = get_kubectl_command()
    deploy(
        env,
        kubectl_cmd,
        plugin_manager,
        images=images,
        overwrite=overwrite,
        production=production,
    )


@cli.command(name="destroy")
@click.option("--env", default="local", help="The environment to target.")
@click.option(
    "--images",
    multiple=True,
    help="A space-delimited list of images to destroy.",
)
def destroy_command(env, images):
    """Destroys the application."""
    plugin_manager = PluginManager()
    kubectl_cmd = get_kubectl_command()
    destroy(
        env,
        kubectl_cmd,
        plugin_manager,
        images=images,
    )


@cli.command()
def build_deb():
    """Builds the debian package."""
    create_debian_package()


@cli.command()
def build_amd64():
    """Builds the amd64 debian installer."""
    create_debian_installer_amd64()


@cli.command()
@click.option(
    "--rpi-model",
    default=4,
    help="The Raspberry Pi model to target (3 or 4).",
)
def build_rpi64(rpi_model):
    """Builds the rpi64 debian installer."""
    create_debian_installer_rpi64(rpi_model)


if __name__ == "__main__":
    cli()
