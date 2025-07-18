# -*- coding: utf-8 -*-
import click

from .utils.builders.amd64 import create_debian_installer_amd64
from .utils.builders.rpi64 import create_debian_installer_rpi64
from .utils.common import create_debian_package
from .utils.kubernetes_tools import deploy, destroy, get_kubectl_command
from .utils.plugin_manager import PluginManager


@click.group()
def cli():
    """
    Defines a CLI group for managing commands.

    This function serves as the entry point for grouping a set of related CLI
    commands using Click, a Python package for creating command-line interfaces.

    The `cli` group allows commands to be registered under it via the
    Click library, thus enabling command-line functionality for a Python
    application.

    """
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
    """
    Deploys Docker images to the specified environment.

    This function serves as a CLI entry point named "deploy" for initiating
    the deployment process of Docker images. The command allows customization
    via various options such as specifying the environment, explicitly targeting
    production, overwriting existing Docker images, and deploying specific
    images.

    Parameters:
        env (str): The environment to target.
        images (tuple[str, ...]): A space-delimited list of images to deploy.
        overwrite (bool): Whether to force overwrite of existing Docker images.
        production (bool): Indicates whether to target the production environment.
    """
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
    """
    Defines a CLI command for destroying resources and images in a specified environment.

    This command facilitates the destruction of specified images in a given environment
    by leveraging a plugin manager and kubectl command. The targeted environment and
    images are configurable through options.

    Parameters:
        env: str
            The target environment for the destroy operation. Defaults to "local".
        images: list of str
            A space-delimited list of images to be destroyed.

    Raises:
        ClickException: If an issue occurs with the command execution.
    """
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
    """
    Builds a Debian package using the specified creation method.

    This function is used to automate the process of building a Debian package,
    which may involve compiling software, packaging files, and preparing
    metadata for distribution.

    Raises
    ------
    Any exceptions raised by create_debian_package are propagated without
    modification.
    """
    create_debian_package()


@cli.command()
def build_amd64():
    """
    Builds an AMD64 Debian installer.

    This command triggers the creation of a Debian installer package for the
    AMD64 architecture.

    Raises:
        Any error encountered during the execution of the installer creation
        process will be raised by the underlying implementation.
    """
    create_debian_installer_amd64()


@cli.command()
@click.option(
    "--rpi-model",
    default=4,
    help="The Raspberry Pi model to target (3 or 4).",
)
def build_rpi64(rpi_model):
    """
    Builds a 64-bit Debian installer for Raspberry Pi.

    This function uses the specified Raspberry Pi model to create a 64-bit
    Debian installer targeting the architecture and configurations specific
    to that model.

    Args:
        rpi_model (int, optional): The Raspberry Pi model to target.
                                   Defaults to 4.
    """
    create_debian_installer_rpi64(rpi_model)


if __name__ == "__main__":
    cli()
