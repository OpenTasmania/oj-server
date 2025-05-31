# -*- coding: utf-8 -*-
import datetime
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Optional, Dict, List, Tuple

from common.command_utils import log_map_server, run_command, run_elevated_command
from setup import config as app_config

module_logger = logging.getLogger(__name__)
OSM_CARTO_BASE_DIR = "/opt/openstreetmap-carto"
MAPNIK_STYLE_TARGET_DIR = "/usr/local/share/maps/style/openstreetmap-carto"
PRIMARY_DATASOURCE_ANCHOR_LINE_START = "osm2pgsql: &osm2pgsql"


def compile_osm_carto_stylesheet(current_logger: Optional[logging.Logger] = None) -> str:
    """
    Compiles the CartoCSS stylesheet `project.mml`, updates its database connection parameters using
    values from the application configuration, and produces the final Mapnik XML output `mapnik.xml`.
    This compilation process ensures that the database credentials are valid and updated in the
    CartoCSS configuration before rendering the mapping styles.

    Parameters:
        current_logger (Optional[logging.Logger]): An optional logger object to redirect logs to a
            specific logging instance. Defaults to the module-wide logger if not provided.

    Returns:
        str: The compiled Mapnik XML output file path.

    Raises:
        ValueError: If PostgreSQL connection parameters in the application configuration are still set
            to their defaults and the developer override flag is not activated.
        FileNotFoundError: If the required `project.mml` file is not found in the OSM Carto base directory.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{app_config.SYMBOLS['step']} Compiling Carto project.mml to mapnik.xml...", "info", logger_to_use)
    original_cwd = os.getcwd()
    project_mml_path = Path(OSM_CARTO_BASE_DIR) / "project.mml"
    compiled_mapnik_xml_path = Path(OSM_CARTO_BASE_DIR) / "mapnik.xml"
    compile_log_filename = Path(OSM_CARTO_BASE_DIR) / "carto_compile_log.txt"
    mml_content_updated_for_log = ""
    try:
        db_params_from_config = {
            "host": app_config.PGHOST,
            "port": str(app_config.PGPORT),
            "dbname": app_config.PGDATABASE,
            "user": app_config.PGUSER,
            "password": app_config.PGPASSWORD,
        }

        db_params_are_all_default = (
                db_params_from_config['host'] == app_config.PGHOST_DEFAULT and
                db_params_from_config['port'] == str(app_config.PGPORT_DEFAULT) and
                db_params_from_config['dbname'] == app_config.PGDATABASE_DEFAULT and
                db_params_from_config['user'] == app_config.PGUSER_DEFAULT and
                db_params_from_config['password'] == app_config.PGPASSWORD_DEFAULT
        )
        if db_params_are_all_default and not app_config.DEV_OVERRIDE_UNSAFE_PASSWORD:
            error_message = (
                "Critical: None of the PostgreSQL connection parameters have been changed from their defaults, "
                "and the developer override flag is not active. Mapnik.xml compilation requires valid or "
                "intentionally-defaulted database credentials. Please provide specific database connection "
                "parameters or enable the developer override flag if using defaults for development."
            )
            log_map_server(f"{app_config.SYMBOLS['critical']} {error_message}", "critical", logger_to_use)
            raise ValueError(error_message)
        os.chdir(OSM_CARTO_BASE_DIR)
        if not project_mml_path.is_file():
            log_map_server(f"{app_config.SYMBOLS['error']} {project_mml_path} not found. Cannot compile.", "error",
                           logger_to_use)
            raise FileNotFoundError(f"{project_mml_path} not found.")

        backup_timestamp = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{int(os.times().user % 10000)}"
        backup_mml_path = project_mml_path.with_suffix(f".mml.bak.{backup_timestamp}")
        try:
            shutil.copy2(project_mml_path, backup_mml_path)
            log_map_server(f"Backed up {project_mml_path} to {backup_mml_path}", "debug", logger_to_use)
        except Exception as e_backup:
            log_map_server(f"{app_config.SYMBOLS['warning']} Could not backup {project_mml_path}: {e_backup}",
                           "warning", logger_to_use)
        mml_content_original_text = project_mml_path.read_text(encoding="utf-8")

        log_map_server(
            f"Updating {project_mml_path} with DB params: Host={db_params_from_config['host']}, Port={db_params_from_config['port']}, "
            f"DB={db_params_from_config['dbname']}, User={db_params_from_config['user']}", "info", logger_to_use)
        if db_params_from_config[
            'password'] == app_config.PGPASSWORD_DEFAULT and not app_config.DEV_OVERRIDE_UNSAFE_PASSWORD and not db_params_are_all_default:
            log_map_server(
                f"{app_config.SYMBOLS['warning']} Using default DB password in project.mml. Consider setting a unique password.",
                "warning", logger_to_use)
        elif db_params_from_config[
            'password'] == app_config.PGPASSWORD_DEFAULT and app_config.DEV_OVERRIDE_UNSAFE_PASSWORD:
            log_map_server(
                f"{app_config.SYMBOLS['info']} Using default DB password in project.mml due to developer override.",
                "info", logger_to_use)

        original_lines = mml_content_original_text.splitlines(
            keepends=False)
        output_lines_collector: List[str] = []
        processed_datasource_block = False
        ds_anchor_pattern = re.compile(rf"^( *)(%s.*)$" % re.escape(PRIMARY_DATASOURCE_ANCHOR_LINE_START))

        kv_extract_pattern = re.compile(r"^\s*([\w-]+):\s*(?:\"([^\"]*)\"|([^#\s\"']+))")
        line_idx = 0
        # Regex to extract key-value pairs from a line, handling quoted and unquoted values.
        kv_extract_pattern = re.compile(r"^\s*([\w-]+):\s*(?:\"([^\"]*)\"|([^#\s\"']+))")
        line_idx = 0
        # Iterate through each line of the original file.
        while line_idx < len(original_lines):
            line_content = original_lines[line_idx]
            # Process the datasource block only if it hasn't been processed yet.
            if not processed_datasource_block:
                match_ds_start = ds_anchor_pattern.match(line_content)
                # Check if the current line marks the beginning of a datasource block.
                if match_ds_start:
                    processed_datasource_block = True
                    block_initial_indent = match_ds_start.group(1)
                    param_reconstruction_indent = block_initial_indent + "  "
                    output_lines_collector.append(line_content)

                    current_block_original_params: Dict[str, str] = {}
                    other_structural_lines_in_block: List[str] = []
                    block_line_idx_iter = line_idx + 1
                    # Iterate through lines within the current datasource block.
                    while block_line_idx_iter < len(original_lines):
                        current_block_line_content = original_lines[block_line_idx_iter]
                        # Determine the indentation of the current line.
                        current_line_actual_indent_match = re.match(r"^( *)", current_block_line_content)
                        current_line_actual_indent = current_line_actual_indent_match.group(
                            1) if current_line_actual_indent_match else ""
                        # If the line is not empty and its indent is less than or equal to the block's initial indent,
                        # it means the block has ended.
                        if current_block_line_content.strip() and len(current_line_actual_indent) <= len(
                                block_initial_indent):
                            break
                        kv_match_obj = kv_extract_pattern.match(current_block_line_content)
                        # If the line matches the key-value pattern.
                        if kv_match_obj:
                            key, quoted_val_content, unquoted_val_content = kv_match_obj.groups()
                            val_content = quoted_val_content if quoted_val_content is not None else unquoted_val_content
                            remainder_after_kv = current_block_line_content[kv_match_obj.end():].strip()
                            # Check if there's any data after the key-value pair on the same line (excluding comments).
                            is_complex_line_with_trailing_data = remainder_after_kv and not remainder_after_kv.startswith(
                                "#")
                            # If the key is a database parameter that needs to be configured.
                            if key in db_params_from_config:
                                if is_complex_line_with_trailing_data:
                                    logger_to_use.warning(
                                        f"Line for DB param '{key}' in MML ('{current_block_line_content}') has trailing data ('{remainder_after_kv}'). Line will be replaced by clean config value.")
                            # If it's not a complex line, store the original parameter.
                            elif not is_complex_line_with_trailing_data:
                                current_block_original_params[key] = val_content if val_content is not None else ""
                            # If it's a complex line that's not a DB param, preserve it as a structural line.
                            else:
                                logger_to_use.warning(
                                    f"Non-DB param line '{current_block_line_content}' is complex. Preserving as structural.")
                                other_structural_lines_in_block.append(current_block_line_content)
                            # If the line is a comment or an empty line, preserve it.
                        elif current_block_line_content.strip().startswith(
                                "#") or not current_block_line_content.strip():
                            other_structural_lines_in_block.append(current_block_line_content)
                        # Otherwise, preserve as a structural line.
                        else:
                            other_structural_lines_in_block.append(current_block_line_content)
                        block_line_idx_iter += 1
                
                    # Prepare the parameters to be written to the output.
                    params_to_write_ordered: List[Tuple[str, str]] = []
                    # Ensure 'type' parameter is first, defaulting to 'postgis'.
                    type_val = current_block_original_params.pop('type', "postgis")
                    params_to_write_ordered.append(('type', type_val))
                    # Add database parameters from the configuration.
                    for db_key in ['host', 'port', 'dbname', 'user', 'password']:
                        params_to_write_ordered.append((db_key, db_params_from_config[db_key]))
                        current_block_original_params.pop(db_key, None) # Remove them if they existed in original
                    # Add any other original parameters, sorted by key.
                    for other_key, other_val in sorted(current_block_original_params.items()):
                        params_to_write_ordered.append((other_key, other_val))
                    # Write the reconstructed parameters to the output.
                    for k_out, v_out in params_to_write_ordered:
                        output_lines_collector.append(f'{param_reconstruction_indent}{k_out}: "{v_out}"')
                        logger_to_use.info(f"Set for MML: {param_reconstruction_indent}{k_out}: \"{v_out}\"")
                    # Add any other structural lines from the block.
                    output_lines_collector.extend(other_structural_lines_in_block)
                    # Adjust the main line index to continue after the processed block.
                    line_idx = block_line_idx_iter - 1
                else:
                    # If not in a datasource block and the line doesn't start one, just append the line.
                    output_lines_collector.append(line_content)
            else:
                # If the datasource block has already been processed, just append the line.
                output_lines_collector.append(line_content)
            line_idx += 1
        # After processing all lines, if the datasource block was not found, log an error and raise an exception.
        if not processed_datasource_block:
            logger_to_use.error(f"Critical: Datasource block starting with '{PRIMARY_DATASOURCE_ANCHOR_LINE_START}' "
                                f"not found in {project_mml_path}. Cannot set DB parameters.")
            raise ValueError(f"Datasource block '{PRIMARY_DATASOURCE_ANCHOR_LINE_START}' not found in project.mml")
        mml_content_updated_for_log = "\n".join(output_lines_collector)
        if mml_content_original_text.endswith('\n') and not mml_content_updated_for_log.endswith(
                '\n') and mml_content_updated_for_log:
            mml_content_updated_for_log += '\n'
        project_mml_path.write_text(mml_content_updated_for_log, encoding="utf-8")
        log_map_server(f"DB parameters processing in {project_mml_path} complete.", "debug", logger_to_use)

        carto_cmd = ["carto", "project.mml"]
        carto_result = run_command(carto_cmd, capture_output=True, check=False, current_logger=logger_to_use)
        with open(compile_log_filename, "w", encoding="utf-8") as log_f:
            log_f.write(f"--- Carto Compilation Log for {project_mml_path} ---\n")
            log_f.write(f"Timestamp: {datetime.datetime.now().isoformat()}\n")
            log_f.write(f"Attempted DB Params: {db_params_from_config}\n\n")
            if carto_result.stdout: log_f.write(f"stdout from carto:\n{carto_result.stdout}\n")
            if carto_result.stderr: log_f.write(f"stderr from carto:\n{carto_result.stderr}\n")
            log_f.write(f"Return code: {carto_result.returncode}\n")
        if carto_result.returncode == 0 and carto_result.stdout:
            with open(compiled_mapnik_xml_path, "w", encoding="utf-8") as mapnik_f:
                mapnik_f.write(carto_result.stdout)
            log_map_server(
                f"{app_config.SYMBOLS['success']} mapnik.xml compiled successfully. See '{compile_log_filename}'.",
                "success", logger_to_use
            )
            return str(compiled_mapnik_xml_path)
        else:
            log_map_server(
                f"{app_config.SYMBOLS['error']} Failed to compile mapnik.xml. RC: {carto_result.returncode}. Check '{compile_log_filename}'.",
                "error", logger_to_use
            )
            logger_to_use.debug(f"MML content written to {project_mml_path}:\n{mml_content_updated_for_log}")
            raise RuntimeError("CartoCSS compilation to mapnik.xml failed.")
    except Exception as e:
        log_map_server(f"{app_config.SYMBOLS['error']} Error during CartoCSS compilation: {e}", "error", logger_to_use)
        if mml_content_updated_for_log:
            logger_to_use.debug(f"MML content that potentially caused error:\n{mml_content_updated_for_log}")
        elif 'mml_content_original_text' in locals():
            logger_to_use.debug(f"Initial MML content (pre-modification):\n{mml_content_original_text}")
        raise
    finally:
        os.chdir(original_cwd)


def deploy_mapnik_stylesheet(compiled_xml_path: str, current_logger: Optional[logging.Logger] = None) -> None:
    """
    Deploys a compiled Mapnik stylesheet XML file to the designated target directory
    for use by the map server. This operation includes validation of the source XML
    file, creation of required directories, copying the XML file, and setting
    appropriate file permissions.

    Parameters:
        compiled_xml_path: str
            The path to the compiled Mapnik XML file that will be deployed.
        current_logger: Optional[logging.Logger]
            An optional logger instance for logging deployment steps. If not
            provided, a module-level logger instance will be used.

    Raises:
        FileNotFoundError
            If the compiled XML file does not exist or is empty.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{app_config.SYMBOLS['step']} Deploying compiled mapnik.xml...", "info", logger_to_use)
    source_mapnik_xml = Path(compiled_xml_path)
    if not source_mapnik_xml.is_file() or source_mapnik_xml.stat().st_size == 0:
        log_map_server(
            f"{app_config.SYMBOLS['error']} Compiled mapnik.xml at {source_mapnik_xml} is missing or empty. Cannot deploy.",
            "error", logger_to_use
        )
        raise FileNotFoundError(f"Valid mapnik.xml not found at {source_mapnik_xml} for deployment.")
    target_dir = Path(MAPNIK_STYLE_TARGET_DIR)
    target_xml_path = target_dir / "mapnik.xml"
    run_elevated_command(["mkdir", "-p", str(target_dir)], current_logger=logger_to_use)
    run_elevated_command(["cp", str(source_mapnik_xml), str(target_xml_path)], current_logger=logger_to_use)
    run_elevated_command(["chmod", "644", str(target_xml_path)], current_logger=logger_to_use)
    log_map_server(f"{app_config.SYMBOLS['success']} mapnik.xml copied to {target_xml_path}", "success", logger_to_use)


def finalize_carto_directory_processing(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Finalize the post-processing of the Carto directory.

    This function ensures that the ownership of the Carto directory is reset to "root:root"
    after completing its processing. It logs the operation's progress and executes the
    command to change ownership with elevated privileges.

    Args:
        current_logger (Optional[logging.Logger]): Custom logger to log information.
            If not provided, the module-level logger will be used.

    Returns:
        None
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{app_config.SYMBOLS['info']} Reverting ownership of {OSM_CARTO_BASE_DIR} to root:root.",
        "info", logger_to_use
    )
    run_elevated_command(["chown", "-R", "root:root", OSM_CARTO_BASE_DIR], current_logger=logger_to_use)


def update_font_cache(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Updates the font cache using the `fc-cache` command. This process ensures that all
    fonts are properly indexed and available to the system. The update may require
    elevated privileges. A logger can be optionally provided to track the execution.

    Parameters:
        current_logger (Optional[logging.Logger]): An optional logger instance to log
            messages. If none is provided, the module's default logger will be used.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{app_config.SYMBOLS['step']} Updating font cache (fc-cache -fv)...", "info", logger_to_use)
    try:
        run_elevated_command(["fc-cache", "-fv"], current_logger=logger_to_use)
        log_map_server(f"{app_config.SYMBOLS['success']} Font cache updated.", "success", logger_to_use)
    except Exception as e:
        log_map_server(f"{app_config.SYMBOLS['error']} Failed to update font cache: {e}", "error", logger_to_use)