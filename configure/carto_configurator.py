# configure/carto_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of Carto: compiling stylesheets, deploying Mapnik XML,
and updating font cache.
"""
import logging
import os
from pathlib import Path  # For Path operations
from typing import Optional

from common.command_utils import log_map_server, run_command, run_elevated_command
from setup import config

module_logger = logging.getLogger(__name__)

OSM_CARTO_BASE_DIR = "/opt/openstreetmap-carto"  # Must match installer
MAPNIK_STYLE_TARGET_DIR = "/usr/local/share/maps/style/openstreetmap-carto"


def compile_osm_carto_stylesheet(current_logger: Optional[logging.Logger] = None) -> str:
    """Compiles project.mml to mapnik.xml using the carto compiler."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Compiling Carto project.mml to mapnik.xml...", "info", logger_to_use)

    original_cwd = os.getcwd()
    compiled_mapnik_xml_path = Path(OSM_CARTO_BASE_DIR) / "mapnik.xml"
    compile_log_filename = Path(OSM_CARTO_BASE_DIR) / "carto_compile_log.txt"

    try:
        os.chdir(OSM_CARTO_BASE_DIR)  # carto command typically run from project root

        carto_cmd = ["carto", "project.mml"]
        # Run as current user (who should own the directory from a previous setup step)
        carto_result = run_command(carto_cmd, capture_output=True, check=False, current_logger=logger_to_use)

        with open(compile_log_filename, "w", encoding="utf-8") as log_f:
            if carto_result.stdout:
                log_f.write(f"stdout from carto:\n{carto_result.stdout}\n")
            if carto_result.stderr:
                log_f.write(f"stderr from carto:\n{carto_result.stderr}\n")
            log_f.write(f"Return code: {carto_result.returncode}\n")

        if carto_result.returncode == 0 and carto_result.stdout:
            with open(compiled_mapnik_xml_path, "w", encoding="utf-8") as mapnik_f:
                mapnik_f.write(carto_result.stdout)
            log_map_server(
                f"{config.SYMBOLS['success']} mapnik.xml compiled successfully to {compiled_mapnik_xml_path}. "
                f"See '{compile_log_filename}'.", "success", logger_to_use
            )
            return str(compiled_mapnik_xml_path)
        else:
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to compile mapnik.xml. "
                f"Return code: {carto_result.returncode}. Check '{compile_log_filename}'.", "error", logger_to_use
            )
            raise RuntimeError("CartoCSS compilation to mapnik.xml failed.")

    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} Error during CartoCSS compilation: {e}", "error", logger_to_use)
        raise
    finally:
        os.chdir(original_cwd)


def deploy_mapnik_stylesheet(compiled_xml_path: str, current_logger: Optional[logging.Logger] = None) -> None:
    """Copies the compiled mapnik.xml to the system style directory."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Deploying compiled mapnik.xml...", "info", logger_to_use)

    source_mapnik_xml = Path(compiled_xml_path)
    if not source_mapnik_xml.is_file() or source_mapnik_xml.stat().st_size == 0:
        log_map_server(
            f"{config.SYMBOLS['error']} Compiled mapnik.xml at {source_mapnik_xml} is missing or empty. Cannot deploy.",
            "error", logger_to_use
        )
        raise FileNotFoundError(f"Valid mapnik.xml not found at {source_mapnik_xml} for deployment.")

    target_dir = Path(MAPNIK_STYLE_TARGET_DIR)
    target_xml_path = target_dir / "mapnik.xml"

    run_elevated_command(["mkdir", "-p", str(target_dir)], current_logger=logger_to_use)
    run_elevated_command(["cp", str(source_mapnik_xml), str(target_xml_path)], current_logger=logger_to_use)
    log_map_server(f"{config.SYMBOLS['success']} mapnik.xml copied to {target_xml_path}", "success", logger_to_use)


def finalize_carto_directory_processing(current_logger: Optional[logging.Logger] = None) -> None:
    """Reverts ownership of the Carto directory to root:root."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['info']} Reverting ownership of {OSM_CARTO_BASE_DIR} to root:root.",
        "info", logger_to_use
    )
    run_elevated_command(["chown", "-R", "root:root", OSM_CARTO_BASE_DIR], current_logger=logger_to_use)


def update_font_cache(current_logger: Optional[logging.Logger] = None) -> None:
    """Updates the system font cache."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Updating font cache (fc-cache -fv)...", "info", logger_to_use)
    try:
        run_elevated_command(["fc-cache", "-fv"], current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} Font cache updated.", "success", logger_to_use)
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} Failed to update font cache: {e}", "error", logger_to_use)
        # This might be non-critical depending on the setup