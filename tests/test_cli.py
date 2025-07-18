# -*- coding: utf-8 -*-
from click.testing import CliRunner

from installer.installer_app.cli import cli


def test_cli_no_args():
    """Test the CLI with no arguments."""
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert "Usage" in result.output
    assert (
        "A command-line interface for the OpenJourney installer."
        in result.output
    )


def test_build_amd64(mocker):
    """Test the build_amd64 subcommand in the CLI."""
    mock_create_debian_installer_amd64 = mocker.patch(
        "installer.installer_app.utils.builders.amd64.create_debian_installer_amd64"
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["build_amd64"])
    assert result.exit_code == 0
    assert "Build process for AMD64 succeeded" in result.output
    mock_create_debian_installer_amd64.assert_called_once()


def test_build_amd64_fails(mocker):
    """Test the build_amd64 subcommand for failure handling."""
    mock_create_debian_installer_amd64 = mocker.patch(
        "installer.installer_app.utils.builders.amd64.create_debian_installer_amd64",
        side_effect=Exception("Build error"),
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["build_amd64"])
    assert result.exit_code != 0
    assert "Build error" in result.output
    mock_create_debian_installer_amd64.assert_called_once()


def test_build_deb(mocker):
    """Test the build_deb subcommand in the CLI."""
    mock_create_debian_package = mocker.patch(
        "installer.installer_app.utils.common.create_debian_package"
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["build_deb"])
    assert result.exit_code == 0
    assert "Debian package built successfully" in result.output
    mock_create_debian_package.assert_called_once()


def test_build_deb_fails(mocker):
    """Test handling of errors during the build_deb subcommand."""
    mock_create_debian_package = mocker.patch(
        "installer.installer_app.utils.common.create_debian_package",
        side_effect=Exception("Build error"),
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["build_deb"])
    assert result.exit_code != 0
    assert "Build error" in result.output
    mock_create_debian_package.assert_called_once()
