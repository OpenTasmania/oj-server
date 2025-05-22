# setup/services/carto.py
"""
Handles the setup of CartoCSS compiler and OpenStreetMap-Carto stylesheet.
"""
import logging
import os
import getpass
import shutil  # For shutil.which
from typing import Optional

from .. import config
from ..command_utils import run_command, run_elevated_command, log_map_server, command_exists

# No specific helpers needed from helpers.py for this function directly, but systemd_reload might be used by an orchestrator after many services.

module_logger = logging.getLogger(__name__)


def carto_setup(current_logger: Optional[logging.Logger] = None) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Setting up CartoCSS compiler and OpenStreetMap-Carto stylesheet...",
                   "info", logger_to_use)

    if not command_exists("npm"):
        log_map_server(
            f"{config.SYMBOLS['error']} NPM (Node Package Manager) not found. Node.js needs to be installed first. Skipping carto setup.",
            "error", logger_to_use)
        # Not raising an error, as Carto might be optional or handled differently if Node isn't managed by this script.
        return

    log_map_server(f"{config.SYMBOLS['package']} Installing CartoCSS compiler (carto) globally via npm...", "info",
                   logger_to_use)
    try:
        # Global npm installs typically require sudo privileges.
        run_elevated_command(["npm", "install", "-g", "carto"], current_logger=logger_to_use)
        # Verify installation by checking version (run as user, should be in PATH if npm -g + sudo worked)
        carto_version_result = run_command(["carto", "-v"], capture_output=True, check=False,
                                           current_logger=logger_to_use)
        carto_version = carto_version_result.stdout.strip() if carto_version_result.returncode == 0 and carto_version_result.stdout else "Not found or error determining version"
        log_map_server(
            f"{config.SYMBOLS['success']} CartoCSS compiler 'carto' installed/updated. Version: {carto_version}",
            "success", logger_to_use)
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to install 'carto' via npm: {e}. Check npm and Node.js installation.",
            "error", logger_to_use)
        return  # Don't proceed if carto isn't installed

    log_map_server(f"{config.SYMBOLS['gear']} Setting up OpenStreetMap-Carto stylesheet...", "info", logger_to_use)
    osm_carto_base_dir = "/opt/openstreetmap-carto"

    dir_exists_check = run_elevated_command(["test", "-d", osm_carto_base_dir], check=False, capture_output=True,
                                            current_logger=logger_to_use)
    if dir_exists_check.returncode != 0:
        log_map_server(f"{config.SYMBOLS['info']} Cloning OpenStreetMap-Carto repository to {osm_carto_base_dir}...",
                       "info", logger_to_use)
        run_elevated_command(["git", "clone", "--depth", "1", "https://github.com/gravitystorm/openstreetmap-carto.git",
                              osm_carto_base_dir], current_logger=logger_to_use)
    else:
        log_map_server(
            f"{config.SYMBOLS['info']} Directory {osm_carto_base_dir} already exists. To update, please do it manually (e.g., cd {osm_carto_base_dir} && sudo git pull).",
            "info", logger_to_use)

    current_user = getpass.getuser()
    try:
        current_group = getpass.getgrgid(os.getgid()).gr_name
    except KeyError:
        current_group = str(os.getgid())  # Fallback to GID if name not found

    log_map_server(
        f"{config.SYMBOLS['info']} Temporarily changing ownership of {osm_carto_base_dir} to {current_user}:{current_group} for script execution.",
        "info", logger_to_use)
    run_elevated_command(["chown", "-R", f"{current_user}:{current_group}", osm_carto_base_dir],
                         current_logger=logger_to_use)

    original_cwd = os.getcwd()
    mapnik_xml_created_successfully = False
    try:
        os.chdir(osm_carto_base_dir)
        log_map_server(
            f"{config.SYMBOLS['gear']} Getting external data for OpenStreetMap-Carto style (running as {current_user})...",
            "info", logger_to_use)

        python_exe_path = shutil.which("python3") or shutil.which("python")
        if python_exe_path:
            run_command([python_exe_path, "scripts/get-external-data.py"], current_logger=logger_to_use)
        else:
            log_map_server(
                f"{config.SYMBOLS['warning']} Python executable not found. Cannot run get-external-data.py. Shapefiles might be missing.",
                "warning", logger_to_use)

        log_map_server(f"{config.SYMBOLS['gear']} Compiling project.mml to mapnik.xml (running as {current_user})...",
                       "info", logger_to_use)
        compile_log_filename = "carto_compile_log.txt"  # Log in the carto dir

        carto_cmd = ["carto", "project.mml"]  # Assumes 'carto' is in PATH for the user
        carto_result = run_command(carto_cmd, capture_output=True, check=False, current_logger=logger_to_use)

        # Always write log, regardless of success
        with open(compile_log_filename, "w") as log_f:  # Write as current user (due to chown)
            if carto_result.stdout: log_f.write(f"stdout from carto:\n{carto_result.stdout}\n")
            if carto_result.stderr: log_f.write(f"stderr from carto:\n{carto_result.stderr}\n")
            log_f.write(f"Return code: {carto_result.returncode}\n")

        if carto_result.returncode == 0 and carto_result.stdout:  # carto outputs XML to stdout on success
            with open("mapnik.xml", "w") as mapnik_f:  # Write as current user
                mapnik_f.write(carto_result.stdout)
            log_map_server(
                f"{config.SYMBOLS['success']} mapnik.xml compiled successfully. See '{compile_log_filename}'.",
                "success", logger_to_use)
            mapnik_xml_created_successfully = True
        else:
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to compile mapnik.xml. Return code: {carto_result.returncode}. Check '{compile_log_filename}' in {osm_carto_base_dir}.",
                "error", logger_to_use)
            # Continue to finally block to revert ownership

        if mapnik_xml_created_successfully and os.path.isfile("mapnik.xml") and os.path.getsize("mapnik.xml") > 0:
            mapnik_style_target_dir = "/usr/local/share/maps/style/openstreetmap-carto"
            run_elevated_command(["mkdir", "-p", mapnik_style_target_dir], current_logger=logger_to_use)
            run_elevated_command(["cp", "mapnik.xml", os.path.join(mapnik_style_target_dir, "mapnik.xml")],
                                 current_logger=logger_to_use)
            log_map_server(f"{config.SYMBOLS['success']} mapnik.xml copied to {mapnik_style_target_dir}/", "success",
                           logger_to_use)
        elif mapnik_xml_created_successfully:  # File exists but is empty
            log_map_server(
                f"{config.SYMBOLS['error']} mapnik.xml was created but is empty or invalid. Check '{compile_log_filename}'.",
                "error", logger_to_use)
            mapnik_xml_created_successfully = False  # Mark as failure

    except Exception as e_carto_processing:
        log_map_server(f"{config.SYMBOLS['error']} Error during OpenStreetMap-Carto processing: {e_carto_processing}",
                       "error", logger_to_use)
        mapnik_xml_created_successfully = False  # Ensure failure
    finally:
        os.chdir(original_cwd)
        log_map_server(f"{config.SYMBOLS['info']} Reverting ownership of {osm_carto_base_dir} to root:root.", "info",
                       logger_to_use)
        run_elevated_command(["chown", "-R", "root:root", osm_carto_base_dir], current_logger=logger_to_use)

    if not mapnik_xml_created_successfully:
        raise RuntimeError("Failed to create or install mapnik.xml for Carto style.")

    log_map_server(f"{config.SYMBOLS['gear']} Updating font cache...", "info", logger_to_use)
    run_elevated_command(["fc-cache", "-fv"], current_logger=logger_to_use)
    log_map_server(f"{config.SYMBOLS['success']} Carto and OSM stylesheet setup completed.", "success", logger_to_use)