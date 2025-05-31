#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Handles the setup of the CartoCSS compiler and OpenStreetMap-Carto stylesheet.

This module installs the 'carto' npm package, clones or updates the
OpenStreetMap-Carto repository, processes its external data using a
potentially custom script, compiles the Mapnik XML stylesheet, and
copies it to the appropriate system location. It also updates the font cache.
"""

import getpass
import grp
import logging
import os
import sys
from typing import Optional

from setup import config
from common.command_utils import (
    command_exists,
    log_map_server,
    run_command,
    run_elevated_command,
)

module_logger = logging.getLogger(__name__)


def carto_setup(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Set up CartoCSS compiler and OpenStreetMap-Carto stylesheet.

    - Installs 'carto' globally via npm if npm is available.
    - Clones the OpenStreetMap-Carto git repository to /opt if not present.
    - Runs 'get-external-data.py' (potentially a custom version) to fetch shapefiles.
    - Compiles 'project.mml' to 'mapnik.xml' using the 'carto' compiler.
    - Copies the generated 'mapnik.xml' to a system style directory.
    - Updates the system font cache.

    Args:
        current_logger: Optional logger instance to use. If None,
                        the module's default logger is used.

    Raises:
        RuntimeError: If the CartoCSS compilation to mapnik.xml fails.
        Exception: For other critical failures during setup.
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
        return

    log_map_server(
        f"{config.SYMBOLS['package']} Installing CartoCSS compiler (carto) "
        "globally via npm...",
        "info",
        logger_to_use,
    )
    try:
        run_elevated_command(
            ["npm", "install", "-g", "carto"], current_logger=logger_to_use
        )
        carto_version_result = run_command(
            ["carto", "-v"],
            capture_output=True,
            check=False,
            current_logger=logger_to_use,
        )
        carto_version = (
            carto_version_result.stdout.strip()
            if carto_version_result.returncode == 0
               and carto_version_result.stdout
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
        return

    log_map_server(
        f"{config.SYMBOLS['gear']} Setting up OpenStreetMap-Carto stylesheet...",
        "info",
        logger_to_use,
    )
    osm_carto_base_dir = "/opt/openstreetmap-carto"

    dir_exists_check = run_elevated_command(
        ["test", "-d", osm_carto_base_dir],
        check=False,
        capture_output=True,
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
                "git",
                "clone",
                "--depth",
                "1",
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
        current_group_name = str(os.getgid())

    log_map_server(
        f"{config.SYMBOLS['info']} Temporarily changing ownership of "
        f"{osm_carto_base_dir} to {current_user}:{current_group_name} for "
        "script execution.",
        "info",
        logger_to_use,
    )
    run_elevated_command(
        [
            "chown",
            "-R",
            f"{current_user}:{current_group_name}",
            osm_carto_base_dir,
        ],
        current_logger=logger_to_use,
    )

    original_cwd = os.getcwd()
    mapnik_xml_created_successfully = False
    try:
        # Determine the path to the custom get-external-data.py script
        # config.OSM_PROJECT_ROOT should point to the 'osm/' directory
        custom_get_external_data_script_path = (
                config.OSM_PROJECT_ROOT / "setup/external/openstreetmap-carto/scripts/get-external-data.py"
        )

        os.chdir(osm_carto_base_dir)  # Change CWD for carto scripts
        log_map_server(
            f"{config.SYMBOLS['gear']} Getting external data for "
            f"OpenStreetMap-Carto style (running as {current_user})...",
            "info",
            logger_to_use,
        )

        python_exe_path = sys.executable
        if python_exe_path:
            # Code change: Use the custom script if it exists, otherwise log a warning.
            # The original script call is commented out.
            if custom_get_external_data_script_path.is_file():
                log_map_server(
                    f"{config.SYMBOLS['info']} Using custom get-external-data.py script: {custom_get_external_data_script_path}",
                    "info",
                    logger_to_use,
                )
                run_command(
                    [python_exe_path, str(custom_get_external_data_script_path)],  # Use absolute path to custom script
                    current_logger=logger_to_use,
                    # Note: The custom script is run with CWD=/opt/openstreetmap-carto
                )
            else:
                log_map_server(
                    f"{config.SYMBOLS['warning']} Custom get-external-data.py not found at "
                    f"{custom_get_external_data_script_path}. Shapefiles might be missing or "
                    "you might need to run the original script manually if intended.",
                    "warning",
                    logger_to_use,
                )

            # Original script call:
            # run_command(
            #     [python_exe_path, "scripts/get-external-data.py"],
            #     current_logger=logger_to_use,
            # )
        else:
            log_map_server(
                f"{config.SYMBOLS['warning']} Python executable (sys.executable) "
                "was unexpectedly not found. Cannot run get-external-data.py. "
                "Shapefiles might be missing.",
                "warning",
                logger_to_use,
            )

        log_map_server(
            f"{config.SYMBOLS['gear']} Compiling project.mml to mapnik.xml "
            f"(running as {current_user})...",
            "info",
            logger_to_use,
        )
        compile_log_filename = "carto_compile_log.txt"

        carto_cmd = ["carto", "project.mml"]
        carto_result = run_command(
            carto_cmd,
            capture_output=True,
            check=False,
            current_logger=logger_to_use,
        )

        with open(compile_log_filename, "w", encoding="utf-8") as log_f:
            if carto_result.stdout:
                log_f.write(f"stdout from carto:\n{carto_result.stdout}\n")
            if carto_result.stderr:
                log_f.write(f"stderr from carto:\n{carto_result.stderr}\n")
            log_f.write(f"Return code: {carto_result.returncode}\n")

        if carto_result.returncode == 0 and carto_result.stdout:
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

        if mapnik_xml_created_successfully:
            mapnik_xml_path = os.path.join(os.getcwd(), "mapnik.xml")
            if (
                    os.path.isfile(mapnik_xml_path)
                    and os.path.getsize(mapnik_xml_path) > 0
            ):
                mapnik_style_target_dir = (
                    "/usr/local/share/maps/style/openstreetmap-carto"
                )
                run_elevated_command(
                    ["mkdir", "-p", mapnik_style_target_dir],
                    current_logger=logger_to_use,
                )
                run_elevated_command(
                    [
                        "cp",
                        "mapnik.xml",
                        os.path.join(mapnik_style_target_dir, "mapnik.xml"),
                    ],
                    current_logger=logger_to_use,
                )
                log_map_server(
                    f"{config.SYMBOLS['success']} mapnik.xml copied to "
                    f"{mapnik_style_target_dir}/",
                    "success",
                    logger_to_use,
                )
            else:
                log_map_server(
                    f"{config.SYMBOLS['error']} mapnik.xml was created but "
                    "is empty or invalid. Check "
                    f"'{compile_log_filename}'.",
                    "error",
                    logger_to_use,
                )
                mapnik_xml_created_successfully = False
    except Exception as e_carto_processing:
        log_map_server(
            f"{config.SYMBOLS['error']} Error during OpenStreetMap-Carto "
            f"processing: {e_carto_processing}",
            "error",
            logger_to_use,
        )
        mapnik_xml_created_successfully = False
    finally:
        os.chdir(original_cwd)
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