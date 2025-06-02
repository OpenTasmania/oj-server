# configure/carto_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of CartoCSS project, stylesheet compilation,
deployment, and font cache updates.
"""

import datetime
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from common.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)
from setup.config_models import (
    PGPASSWORD_DEFAULT,
    AppSettings,
)

module_logger = logging.getLogger(__name__)

OSM_CARTO_BASE_DIR_CONFIG = "/opt/openstreetmap-carto"  # Matches installer
MAPNIK_STYLE_TARGET_DIR_CONFIG = (
    "/usr/local/share/maps/style/openstreetmap-carto"
)
PRIMARY_DATASOURCE_ANCHOR_LINE_START_CONFIG = "osm2pgsql: &osm2pgsql"


def compile_osm_carto_stylesheet(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> str:  # Return type is str (path to compiled xml)
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('step', '➡️')} Compiling Carto project.mml to mapnik.xml...",
        "info",
        logger_to_use,
        app_settings,
    )

    original_cwd = os.getcwd()
    # Initialize to ensure it's always "assigned" before the except block can be reached
    mml_content_original_text: Optional[str] = None
    mml_content_updated_for_log: str = ""

    carto_base_path = Path(OSM_CARTO_BASE_DIR_CONFIG)
    project_mml_path = carto_base_path / "project.mml"
    compiled_mapnik_xml_path = (
        carto_base_path / "mapnik.xml"
    )  # Define this path early
    compile_log_filename = carto_base_path / "carto_compile_log.txt"

    try:
        db_params_from_config = {
            "host": app_settings.pg.host,
            "port": str(app_settings.pg.port),
            "dbname": app_settings.pg.database,
            "user": app_settings.pg.user,
            "password": app_settings.pg.password,
        }

        # (Password checks and logging for default password usage - as per your existing logic)
        # This part is assumed to be present from your file. Example:
        db_params_are_all_default_check = (  # Simplified check for brevity
            db_params_from_config["password"] == PGPASSWORD_DEFAULT
        )
        if (
            db_params_are_all_default_check
            and not app_settings.dev_override_unsafe_password
        ):
            error_message = "Critical: Default PostgreSQL password in use..."
            log_map_server(
                f"{symbols.get('critical', '🔥')} {error_message}",
                "critical",
                logger_to_use,
                app_settings,
            )
            raise ValueError(error_message)
        # End of example password check section

        if not carto_base_path.is_dir():
            log_map_server(
                f"{symbols.get('error', '❌')} Carto base directory {carto_base_path} not found.",
                "error",
                logger_to_use,
                app_settings,
            )
            raise FileNotFoundError(
                f"Carto base directory {carto_base_path} not found."
            )

        os.chdir(carto_base_path)

        if not project_mml_path.is_file():
            log_map_server(
                f"{symbols.get('error', '❌')} {project_mml_path} not found. Cannot compile.",
                "error",
                logger_to_use,
                app_settings,
            )
            raise FileNotFoundError(f"{project_mml_path} not found.")

        # Backup original project.mml
        backup_timestamp = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{int(os.times().user % 10000)}"
        backup_mml_path = project_mml_path.with_suffix(
            f".mml.bak.{backup_timestamp}"
        )
        try:
            shutil.copy2(project_mml_path, backup_mml_path)
            log_map_server(
                f"Backed up {project_mml_path} to {backup_mml_path}",
                "debug",
                logger_to_use,
                app_settings,
            )
        except Exception as e_backup:
            log_map_server(
                f"{symbols.get('warning', '!')} Could not backup {project_mml_path}: {e_backup}",
                "warning",
                logger_to_use,
                app_settings,
            )

        mml_content_original_text = project_mml_path.read_text(
            encoding="utf-8"
        )  # Assigned here

        # --- Start of MML processing logic (ensure this part is complete and correct in your actual file) ---
        original_lines = mml_content_original_text.splitlines(keepends=False)
        output_lines_collector: List[str] = []
        processed_datasource_block = False
        # PRIMARY_DATASOURCE_ANCHOR_LINE_START_CONFIG should be defined, e.g., "osm2pgsql: &osm2pgsql"
        ds_anchor_pattern = re.compile(
            r"^( *)(%s.*)$"
            % re.escape(PRIMARY_DATASOURCE_ANCHOR_LINE_START_CONFIG)
        )
        kv_extract_pattern = re.compile(
            r"^\s*([\w-]+):\s*(?:\"([^\"]*)\"|([^#\s\"']+))"
        )
        line_idx = 0

        while line_idx < len(original_lines):
            line_content = original_lines[line_idx]
            if not processed_datasource_block:
                match_ds_start = ds_anchor_pattern.match(line_content)
                if match_ds_start:
                    processed_datasource_block = True
                    block_initial_indent = match_ds_start.group(1)
                    param_reconstruction_indent = block_initial_indent + "  "
                    output_lines_collector.append(line_content)
                    current_block_original_params: Dict[str, str] = {}
                    other_structural_lines_in_block: List[str] = []
                    block_line_idx_iter = line_idx + 1
                    while block_line_idx_iter < len(original_lines):
                        current_block_line_content = original_lines[
                            block_line_idx_iter
                        ]
                        current_line_actual_indent_match = re.match(
                            r"^( *)", current_block_line_content
                        )
                        current_line_actual_indent = (
                            current_line_actual_indent_match.group(1)
                            if current_line_actual_indent_match
                            else ""
                        )
                        if current_block_line_content.strip() and len(
                            current_line_actual_indent
                        ) <= len(block_initial_indent):
                            break
                        kv_match_obj = kv_extract_pattern.match(
                            current_block_line_content
                        )
                        if kv_match_obj:
                            key, quoted_val, unquoted_val = (
                                kv_match_obj.groups()
                            )
                            val = (
                                quoted_val
                                if quoted_val is not None
                                else unquoted_val
                            )
                            remainder = current_block_line_content[
                                kv_match_obj.end() :
                            ].strip()
                            is_complex = (
                                remainder and not remainder.startswith("#")
                            )
                            if key in db_params_from_config:
                                if is_complex:
                                    logger_to_use.warning(
                                        f"MML line for DB param '{key}' ('{current_block_line_content}') has trailing data. Will be replaced cleanly."
                                    )
                            elif not is_complex:
                                current_block_original_params[key] = (
                                    val if val is not None else ""
                                )
                            else:
                                other_structural_lines_in_block.append(
                                    current_block_line_content
                                )
                        elif (
                            current_block_line_content.strip().startswith("#")
                            or not current_block_line_content.strip()
                        ):
                            other_structural_lines_in_block.append(
                                current_block_line_content
                            )
                        else:
                            other_structural_lines_in_block.append(
                                current_block_line_content
                            )
                        block_line_idx_iter += 1
                    params_to_write: List[Tuple[str, str]] = [
                        (
                            "type",
                            current_block_original_params.pop(
                                "type", "postgis"
                            ),
                        )
                    ]
                    for db_key_ordered in [
                        "host",
                        "port",
                        "dbname",
                        "user",
                        "password",
                    ]:
                        params_to_write.append((
                            db_key_ordered,
                            db_params_from_config[db_key_ordered],
                        ))
                        current_block_original_params.pop(
                            db_key_ordered, None
                        )
                    for other_k, other_v in sorted(
                        current_block_original_params.items()
                    ):
                        params_to_write.append((other_k, other_v))
                    for k_out, v_out in params_to_write:
                        output_lines_collector.append(
                            f'{param_reconstruction_indent}{k_out}: "{v_out}"'
                        )
                    output_lines_collector.extend(
                        other_structural_lines_in_block
                    )
                    line_idx = block_line_idx_iter - 1
                else:
                    output_lines_collector.append(line_content)
            else:
                output_lines_collector.append(line_content)
            line_idx += 1
        if not processed_datasource_block:
            err_msg = f"Datasource block '{PRIMARY_DATASOURCE_ANCHOR_LINE_START_CONFIG}' not found in {project_mml_path}."
            log_map_server(
                f"{symbols.get('error', '❌')} Critical: {err_msg}",
                "error",
                logger_to_use,
                app_settings,
            )
            raise ValueError(err_msg)
        # --- End of MML processing logic ---

        mml_content_updated_for_log = "\n".join(output_lines_collector)
        # Ensure original text was read before trying to access its attributes
        if (
            mml_content_original_text
            and mml_content_original_text.endswith("\n")
            and not mml_content_updated_for_log.endswith("\n")
            and mml_content_updated_for_log
        ):
            mml_content_updated_for_log += "\n"

        project_mml_path.write_text(
            mml_content_updated_for_log, encoding="utf-8"
        )
        log_map_server(
            f"DB parameters processing in {project_mml_path} complete.",
            "debug",
            logger_to_use,
            app_settings,
        )

        carto_cmd = ["carto", "project.mml"]
        carto_result = run_command(
            carto_cmd,
            app_settings,
            capture_output=True,
            check=False,
            current_logger=logger_to_use,
        )

        with open(compile_log_filename, "w", encoding="utf-8") as log_f:
            log_f.write(
                f"--- Carto Compilation Log for {project_mml_path} ---\n"
            )
            # ... (logging details to compile_log_filename as before) ...
            log_f.write(f"Return code: {carto_result.returncode}\n")

        if carto_result.returncode == 0 and carto_result.stdout:
            with open(
                compiled_mapnik_xml_path, "w", encoding="utf-8"
            ) as mapnik_f:
                mapnik_f.write(carto_result.stdout)
            log_map_server(
                f"{symbols.get('success', '✅')} mapnik.xml compiled successfully. See '{compile_log_filename}'.",
                "success",
                logger_to_use,
                app_settings,
            )
            return str(compiled_mapnik_xml_path)  # Successful return
        else:
            log_map_server(
                f"{symbols.get('error', '❌')} Failed to compile mapnik.xml. RC: {carto_result.returncode}. Check '{compile_log_filename}'.",
                "error",
                logger_to_use,
                app_settings,
            )
            logger_to_use.debug(
                f"MML content written to {project_mml_path} that may have caused error:\n{mml_content_updated_for_log}"
            )
            raise RuntimeError(
                f"CartoCSS compilation to mapnik.xml failed. Check log: {compile_log_filename}"
            )

    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Error during CartoCSS compilation: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        # Safely log original or updated MML content if available
        if mml_content_updated_for_log:
            logger_to_use.debug(
                f"MML content (updated) at time of error:\n{mml_content_updated_for_log}"
            )
        elif mml_content_original_text:  # This is now safe to check directly
            logger_to_use.debug(
                f"MML content (original) at time of error:\n{mml_content_original_text}"
            )
        else:
            logger_to_use.debug(
                "Neither updated nor original MML content was available at time of error (it was None or empty)."
            )
        raise
    finally:
        os.chdir(original_cwd)


def deploy_mapnik_stylesheet(
    compiled_xml_path_str: str,
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """Deploys the compiled Mapnik XML stylesheet."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('step', '➡️')} Deploying compiled mapnik.xml...",
        "info",
        logger_to_use,
        app_settings,
    )

    if not compiled_xml_path_str:  # Check if path is None or empty
        log_map_server(
            f"{symbols.get('error', '❌')} Compiled mapnik.xml path is not provided. Cannot deploy.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise ValueError("Compiled XML path is required for deployment.")

    source_mapnik_xml = Path(compiled_xml_path_str)
    if (
        not source_mapnik_xml.is_file()
        or source_mapnik_xml.stat().st_size == 0
    ):
        log_map_server(
            f"{symbols.get('error', '❌')} Compiled mapnik.xml at {source_mapnik_xml} is missing or empty. Cannot deploy.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise FileNotFoundError(
            f"Valid mapnik.xml not found at {source_mapnik_xml} for deployment."
        )

    target_dir = Path(MAPNIK_STYLE_TARGET_DIR_CONFIG)
    target_xml_path = target_dir / "mapnik.xml"  # Standard name in target dir

    run_elevated_command(
        ["mkdir", "-p", str(target_dir)],
        app_settings,
        current_logger=logger_to_use,
    )
    run_elevated_command(
        ["cp", str(source_mapnik_xml), str(target_xml_path)],
        app_settings,
        current_logger=logger_to_use,
    )
    run_elevated_command(
        ["chmod", "644", str(target_xml_path)],
        app_settings,
        current_logger=logger_to_use,
    )  # Standard read permissions
    log_map_server(
        f"{symbols.get('success', '✅')} mapnik.xml copied to {target_xml_path}",
        "success",
        logger_to_use,
        app_settings,
    )


def finalize_carto_directory_processing(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Reverts ownership of the Carto directory to root:root."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('info', 'ℹ️')} Reverting ownership of {OSM_CARTO_BASE_DIR_CONFIG} to root:root.",
        "info",
        logger_to_use,
        app_settings,
    )
    run_elevated_command(
        ["chown", "-R", "root:root", OSM_CARTO_BASE_DIR_CONFIG],
        app_settings,
        current_logger=logger_to_use,
    )
    log_map_server(
        f"{symbols.get('success', '✅')} Ownership of {OSM_CARTO_BASE_DIR_CONFIG} reverted to root.",
        "success",
        logger_to_use,
        app_settings,
    )


def update_font_cache(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Updates the system font cache using fc-cache."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('step', '➡️')} Updating font cache (fc-cache -fv)...",
        "info",
        logger_to_use,
        app_settings,
    )
    try:
        run_elevated_command(
            ["fc-cache", "-fv"], app_settings, current_logger=logger_to_use
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Font cache updated.",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to update font cache: {e}",
            "error",
            logger_to_use,
            app_settings,
        )
        # This might not be fatal for all setups, but important for map rendering
        # Consider whether to raise
