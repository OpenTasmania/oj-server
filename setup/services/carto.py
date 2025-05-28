# setup/services/carto.py
# -*- coding: utf-8 -*-
"""
Handles the setup of the CartoCSS compiler and OpenStreetMap-Carto stylesheet.

This module installs the 'carto' npm package, clones or updates the
OpenStreetMap-Carto repository, processes its external data, compiles
the Mapnik XML stylesheet, and copies it to the appropriate system location.
It also updates the font cache.
"""

import getpass
import grp
import logging
import os
import shutil  # For shutil.which to find executables
from typing import Optional

from setup import config
from setup.command_utils import (
    command_exists,
    log_map_server,
    run_command,
    run_elevated_command,
)

# No specific helpers needed from helpers.py for this function directly,
# but systemd_reload might be used by an orchestrator after many services.

module_logger = logging.getLogger(__name__)


def carto_setup(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Set up CartoCSS compiler and OpenStreetMap-Carto stylesheet.

    - Installs 'carto' globally via npm if npm is available.
    - Clones the OpenStreetMap-Carto git repository to /opt if not present.
    - Runs 'get-external-data.py' to fetch shapefiles.
    - Compiles 'project.mml' to 'mapnik.xml' using the 'carto' compiler.
    - Copies the generated 'mapnik.xml' to a system style directory.
    - Updates the system font cache.

    Args:
        current_logger: Optional logger instance to use. If None,
                        the module's default logger is used.

    Raises:
        RuntimeError: If the CartoCSS compilation to mapnik.xml fails.
        Exception: For other critical failures during setup, such as npm
                   or git command failures when `check=True` is used in
                   `run_command` or `run_elevated_command`.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up CartoCSS compiler and "
        "OpenStreetMap-Carto stylesheet...",
        "info",
        logger_to_use,
    )

    if not command_exists("npm"):
        log_map_server(
            f"{config.SYMBOLS['error']} NPM (Node Package Manager) not found. "
            "Node.js needs to be installed first. Skipping carto setup.",
            "error",
            logger_to_use,
        )
        # Not raising an error, as Carto might be optional or handled
        # differently if Node isn't managed by this script.
        return

    log_map_server(
        f"{config.SYMBOLS['package']} Installing CartoCSS compiler (carto) "
        "globally via npm...",
        "info",
        logger_to_use,
    )
    try:
        # Global npm installs typically require sudo privileges.
        run_elevated_command(
            ["npm", "install", "-g", "carto"], current_logger=logger_to_use
        )
        # Verify installation by checking version.
        # This should be run as the user, assuming 'carto' is now in PATH.
        carto_version_result = run_command(
            ["carto", "-v"],
            capture_output=True,
            check=False,  # Don't fail the script if version check has an issue
            current_logger=logger_to_use,
        )
        carto_version = (
            carto_version_result.stdout.strip()
            if carto_version_result.returncode == 0 and
               carto_version_result.stdout
            else "Not found or error determining version"
        )
        log_map_server(
            f"{config.SYMBOLS['success']} CartoCSS compiler 'carto' "
            f"installed/updated. Version: {carto_version}",
            "success",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to install 'carto' via npm: {e}. "
            "Check npm and Node.js installation.",
            "error",
            logger_to_use,
        )
        return  # Don't proceed if carto isn't installed.

    log_map_server(
        f"{config.SYMBOLS['gear']} Setting up OpenStreetMap-Carto stylesheet...",
        "info",
        logger_to_use,
    )
    osm_carto_base_dir = "/opt/openstreetmap-carto"

    # Check if the directory exists using an elevated command.
    dir_exists_check = run_elevated_command(
        ["test", "-d", osm_carto_base_dir],
        check=False,  # `test -d` returns 0 if exists, 1 if not.
        capture_output=True,  # Suppress output of 'test' command.
        current_logger=logger_to_use,
    )
    if dir_exists_check.returncode != 0:
        log_map_server(
            f"{config.SYMBOLS['info']} Cloning OpenStreetMap-Carto repository "
            f"to {osm_carto_base_dir}...",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            [
                "git", "clone", "--depth", "1",  # Shallow clone for speed
                "https://github.com/gravitystorm/openstreetmap-carto.git",
                osm_carto_base_dir,
            ],
            current_logger=logger_to_use,
        )
    else:
        log_map_server(
            f"{config.SYMBOLS['info']} Directory {osm_carto_base_dir} "
            "already exists. To update, please do it manually (e.g., "
            f"cd {osm_carto_base_dir} && sudo git pull).",
            "info",
            logger_to_use,
        )

    current_user = getpass.getuser()
    try:
        current_group_info = grp.getgrgid(os.getgid())
        current_group_name = current_group_info.gr_name
    except KeyError:
        # Fallback to GID if group name cannot be found.
        current_group_name = str(os.getgid())

    log_map_server(
        f"{config.SYMBOLS['info']} Temporarily changing ownership of "
        f"{osm_carto_base_dir} to {current_user}:{current_group_name} for "
        "script execution.",
        "info",
        logger_to_use,
    )
    run_elevated_command(
        ["chown", "-R", f"{current_user}:{current_group_name}",
         osm_carto_base_dir],
        current_logger=logger_to_use,
    )

    original_cwd = os.getcwd()
    mapnik_xml_created_successfully = False
    try:
        os.chdir(osm_carto_base_dir)
        log_map_server(
            f"{config.SYMBOLS['gear']} Getting external data for "
            f"OpenStreetMap-Carto style (running as {current_user})...",
            "info",
            logger_to_use,
        )

        # Find python3 or python executable.
        python_exe_path = shutil.which("python3") or shutil.which("python")
        if python_exe_path:
            run_command(  # Run as current user due to chown.
                [python_exe_path, "scripts/get-external-data.py"],
                current_logger=logger_to_use,
            )
        else:
            log_map_server(
                f"{config.SYMBOLS['warning']} Python executable not found. "
                "Cannot run get-external-data.py. Shapefiles might be missing.",
                "warning",
                logger_to_use,
            )

        log_map_server(
            f"{config.SYMBOLS['gear']} Compiling project.mml to mapnik.xml "
            f"(running as {current_user})...",
            "info",
            logger_to_use,
        )
        # Log compilation output to a file in the carto directory.
        compile_log_filename = "carto_compile_log.txt"

        # Assumes 'carto' is in PATH for the current user.
        carto_cmd = ["carto", "project.mml"]
        carto_result = run_command(  # Run as current user.
            carto_cmd,
            capture_output=True,
            check=False,  # Check return code manually.
            current_logger=logger_to_use,
        )

        # Always write log, regardless of success.
        # Written as current user due to chown.
        with open(compile_log_filename, "w", encoding="utf-8") as log_f:
            if carto_result.stdout:
                log_f.write(f"stdout from carto:\n{carto_result.stdout}\n")
            if carto_result.stderr:
                log_f.write(f"stderr from carto:\n{carto_result.stderr}\n")
            log_f.write(f"Return code: {carto_result.returncode}\n")

        # 'carto' outputs XML to stdout on success.
        if carto_result.returncode == 0 and carto_result.stdout:
            # Write as current user.
            with open("mapnik.xml", "w", encoding="utf-8") as mapnik_f:
                mapnik_f.write(carto_result.stdout)
            log_map_server(
                f"{config.SYMBOLS['success']} mapnik.xml compiled "
                f"successfully. See '{compile_log_filename}'.",
                "success",
                logger_to_use,
            )
            mapnik_xml_created_successfully = True
        else:
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to compile mapnik.xml. "
                f"Return code: {carto_result.returncode}. Check "
                f"'{compile_log_filename}' in {osm_carto_base_dir}.",
                "error",
                logger_to_use,
            )
            # Continue to finally block to revert ownership.

        if mapnik_xml_created_successfully:
            mapnik_xml_path = os.path.join(os.getcwd(), "mapnik.xml")
            if os.path.isfile(mapnik_xml_path) and \
               os.path.getsize(mapnik_xml_path) > 0:
                mapnik_style_target_dir = (
                    "/usr/local/share/maps/style/openstreetmap-carto"
                )
                run_elevated_command(
                    ["mkdir", "-p", mapnik_style_target_dir],
                    current_logger=logger_to_use,
                )
                run_elevated_command(
                    ["cp", "mapnik.xml",
                     os.path.join(mapnik_style_target_dir, "mapnik.xml")],
                    current_logger=logger_to_use,
                )
                log_map_server(
                    f"{config.SYMBOLS['success']} mapnik.xml copied to "
                    f"{mapnik_style_target_dir}/",
                    "success",
                    logger_to_use,
                )
            else:  # File exists but is empty or other issue.
                log_map_server(
                    f"{config.SYMBOLS['error']} mapnik.xml was created but "
                    "is empty or invalid. Check "
                    f"'{compile_log_filename}'.",
                    "error",
                    logger_to_use,
                )
                mapnik_xml_created_successfully = False  # Mark as failure.
    except Exception as e_carto_processing:
        log_map_server(
            f"{config.SYMBOLS['error']} Error during OpenStreetMap-Carto "
            f"processing: {e_carto_processing}",
            "error",
            logger_to_use,
        )
        mapnik_xml_created_successfully = False  # Ensure failure status.
    finally:
        os.chdir(original_cwd)  # Always change back to original directory.
        log_map_server(
            f"{config.SYMBOLS['info']} Reverting ownership of "
            f"{osm_carto_base_dir} to root:root.",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            ["chown", "-R", "root:root", osm_carto_base_dir],
            current_logger=logger_to_use,
        )

    if not mapnik_xml_created_successfully:
        raise RuntimeError(
            "Failed to create or install mapnik.xml for Carto style."
        )

    log_map_server(
        f"{config.SYMBOLS['gear']} Updating font cache...",
        "info",
        logger_to_use,
    )
    run_elevated_command(["fc-cache", "-fv"], current_logger=logger_to_use)
    log_map_server(
        f"{config.SYMBOLS['success']} Carto and OSM stylesheet setup completed.",
        "success",
        logger_to_use,
    )