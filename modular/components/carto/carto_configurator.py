"""
Carto configurator module.

This module provides a self-contained configurator for CartoCSS project,
stylesheet compilation, deployment, and font cache updates.
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
from modular.base_configurator import BaseConfigurator
from modular.registry2 import ConfiguratorRegistry
from setup.config_models import (
    PGPASSWORD_DEFAULT,
    AppSettings,
)


@ConfiguratorRegistry.register(
    name="carto",
    metadata={
        "dependencies": ["postgres"],  # Carto depends on PostgreSQL
        "description": "CartoCSS project configuration and stylesheet compilation",
    },
)
class CartoConfigurator(BaseConfigurator):
    """
    Configurator for CartoCSS project.

    This configurator ensures that the CartoCSS project is properly configured,
    stylesheets are compiled, deployed, and font cache is updated.
    """

    # Constants for Carto configuration
    OSM_CARTO_BASE_DIR_CONFIG = "/opt/openstreetmap-carto"
    MAPNIK_STYLE_TARGET_DIR_CONFIG = (
        "/usr/local/share/maps/style/openstreetmap-carto"
    )
    PRIMARY_DATASOURCE_ANCHOR_LINE_START_CONFIG = "osm2pgsql: &osm2pgsql"

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Carto configurator.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)

    def configure(self) -> bool:
        """
        Configure the CartoCSS project.

        This method performs the following configuration tasks:
        1. Compiles the OpenStreetMap CartoCSS stylesheet to a Mapnik XML file
        2. Deploys the compiled Mapnik XML stylesheet to the target directory
        3. Finalizes the Carto directory processing
        4. Updates the font cache

        Returns:
            True if the configuration was successful, False otherwise.
        """
        try:
            compiled_xml_path = self._compile_osm_carto_stylesheet()
            self._deploy_mapnik_stylesheet(compiled_xml_path)
            self._finalize_carto_directory_processing()
            self._update_font_cache()
            return True
        except Exception as e:
            self.logger.error(f"Error configuring Carto: {str(e)}")
            return False

    def unconfigure(self) -> bool:
        """
        Unconfigure the CartoCSS project.

        This method removes the deployed Mapnik XML stylesheet.

        Returns:
            True if the unconfiguration was successful, False otherwise.
        """
        try:
            symbols = self.app_settings.symbols
            target_dir = Path(self.MAPNIK_STYLE_TARGET_DIR_CONFIG)
            target_xml_path = target_dir / "mapnik.xml"

            if target_xml_path.exists():
                run_elevated_command(
                    ["rm", str(target_xml_path)],
                    self.app_settings,
                    current_logger=self.logger,
                )
                log_map_server(
                    f"{symbols.get('success', '')} Removed deployed mapnik.xml: {target_xml_path}",
                    "success",
                    self.logger,
                    self.app_settings,
                )

            return True
        except Exception as e:
            self.logger.error(f"Error unconfiguring Carto: {str(e)}")
            return False

    def is_configured(self) -> bool:
        """
        Check if the CartoCSS project is configured.

        This method checks if the deployed Mapnik XML stylesheet exists.

        Returns:
            True if the CartoCSS project is configured, False otherwise.
        """
        try:
            target_dir = Path(self.MAPNIK_STYLE_TARGET_DIR_CONFIG)
            target_xml_path = target_dir / "mapnik.xml"

            return (
                target_xml_path.exists()
                and target_xml_path.stat().st_size > 0
            )
        except Exception as e:
            self.logger.error(
                f"Error checking if Carto is configured: {str(e)}"
            )
            return False

    def _compile_osm_carto_stylesheet(self) -> str:
        """
        Compile the OpenStreetMap CartoCSS stylesheet to a Mapnik XML file.

        Returns:
            Path to the compiled Mapnik XML file.

        Raises:
            ValueError: If default PostgreSQL password is used without override.
            FileNotFoundError: If Carto base directory or project.mml file is not found.
            Exception: For any other errors encountered during compilation.
        """
        symbols = self.app_settings.symbols
        log_map_server(
            f"{symbols.get('step', '')} Compiling Carto project.mml to mapnik.xml...",
            "info",
            self.logger,
            self.app_settings,
        )

        original_cwd = os.getcwd()
        # Initialize to ensure it's always "assigned" before the except block can be reached
        mml_content_original_text: Optional[str] = None
        mml_content_updated_for_log: str = ""

        carto_base_path = Path(self.OSM_CARTO_BASE_DIR_CONFIG)
        project_mml_path = carto_base_path / "project.mml"
        compiled_mapnik_xml_path = carto_base_path / "mapnik.xml"
        compile_log_filename = carto_base_path / "carto_compile_log.txt"

        try:
            db_params_from_config = {
                "host": self.app_settings.pg.host,
                "port": str(self.app_settings.pg.port),
                "dbname": self.app_settings.pg.database,
                "user": self.app_settings.pg.user,
                "password": self.app_settings.pg.password,
            }

            db_params_are_all_default_check = (
                db_params_from_config["password"] == PGPASSWORD_DEFAULT
            )
            if (
                db_params_are_all_default_check
                and not self.app_settings.dev_override_unsafe_password
            ):
                error_message = (
                    "Critical: Default PostgreSQL password in use..."
                )
                log_map_server(
                    f"{symbols.get('critical', '')} {error_message}",
                    "critical",
                    self.logger,
                    self.app_settings,
                )
                raise ValueError(error_message)

            if not carto_base_path.is_dir():
                log_map_server(
                    f"{symbols.get('error', '')} Carto base directory {carto_base_path} not found.",
                    "error",
                    self.logger,
                    self.app_settings,
                )
                raise FileNotFoundError(
                    f"Carto base directory {carto_base_path} not found."
                )

            os.chdir(carto_base_path)

            if not project_mml_path.is_file():
                log_map_server(
                    f"{symbols.get('error', '')} {project_mml_path} not found. Cannot compile.",
                    "error",
                    self.logger,
                    self.app_settings,
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
                    self.logger,
                    self.app_settings,
                )
            except Exception as e_backup:
                log_map_server(
                    f"{symbols.get('warning', '')} Could not backup {project_mml_path}: {e_backup}",
                    "warning",
                    self.logger,
                    self.app_settings,
                )

            mml_content_original_text = project_mml_path.read_text(
                encoding="utf-8"
            )

            # --- Start of MML processing logic ---
            original_lines = mml_content_original_text.splitlines(
                keepends=False
            )
            output_lines_collector: List[str] = []
            processed_datasource_block = False
            ds_anchor_pattern = re.compile(
                r"^( *)(%s.*)$"
                % re.escape(self.PRIMARY_DATASOURCE_ANCHOR_LINE_START_CONFIG)
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
                        param_reconstruction_indent = (
                            block_initial_indent + "  "
                        )
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
                                    remainder
                                    and not remainder.startswith("#")
                                )
                                if key in db_params_from_config:
                                    if is_complex:
                                        self.logger.warning(
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
                                current_block_line_content.strip().startswith(
                                    "#"
                                )
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
                err_msg = f"Datasource block '{self.PRIMARY_DATASOURCE_ANCHOR_LINE_START_CONFIG}' not found in {project_mml_path}."
                log_map_server(
                    f"{symbols.get('error', '')} Critical: {err_msg}",
                    "error",
                    self.logger,
                    self.app_settings,
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
                self.logger,
                self.app_settings,
            )

            carto_cmd = ["carto", "project.mml"]
            carto_result = run_command(
                carto_cmd,
                self.app_settings,
                capture_output=True,
                check=False,
                current_logger=self.logger,
            )

            with open(compile_log_filename, "w", encoding="utf-8") as log_f:
                log_f.write(
                    f"--- Carto Compilation Log for {project_mml_path} ---\n"
                )
                log_f.write(f"Return code: {carto_result.returncode}\n")

            if carto_result.returncode == 0 and carto_result.stdout:
                with open(
                    compiled_mapnik_xml_path, "w", encoding="utf-8"
                ) as mapnik_f:
                    mapnik_f.write(carto_result.stdout)
                log_map_server(
                    f"{symbols.get('success', '')} mapnik.xml compiled successfully. See '{compile_log_filename}'.",
                    "success",
                    self.logger,
                    self.app_settings,
                )
                return str(compiled_mapnik_xml_path)  # Successful return
            else:
                log_map_server(
                    f"{symbols.get('error', '')} Failed to compile mapnik.xml. RC: {carto_result.returncode}. Check '{compile_log_filename}'.",
                    "error",
                    self.logger,
                    self.app_settings,
                )
                self.logger.debug(
                    f"MML content written to {project_mml_path} that may have caused error:\n{mml_content_updated_for_log}"
                )
                raise RuntimeError(
                    f"CartoCSS compilation to mapnik.xml failed. Check log: {compile_log_filename}"
                )

        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '')} Error during CartoCSS compilation: {e}",
                "error",
                self.logger,
                self.app_settings,
                exc_info=True,
            )
            # Safely log original or updated MML content if available
            if mml_content_updated_for_log:
                self.logger.debug(
                    f"MML content (updated) at time of error:\n{mml_content_updated_for_log}"
                )
            elif mml_content_original_text:
                self.logger.debug(
                    f"MML content (original) at time of error:\n{mml_content_original_text}"
                )
            else:
                self.logger.debug(
                    "Neither updated nor original MML content was available at time of error (it was None or empty)."
                )
            raise
        finally:
            os.chdir(original_cwd)

    def _deploy_mapnik_stylesheet(self, compiled_xml_path_str: str) -> None:
        """
        Deploy the compiled Mapnik XML stylesheet to the target directory.

        Args:
            compiled_xml_path_str: Path to the compiled Mapnik XML file to deploy.

        Raises:
            ValueError: If the compiled XML path is not provided.
            FileNotFoundError: If the compiled XML file is missing or empty.
        """
        symbols = self.app_settings.symbols
        log_map_server(
            f"{symbols.get('step', '')} Deploying compiled mapnik.xml...",
            "info",
            self.logger,
            self.app_settings,
        )

        if not compiled_xml_path_str:  # Check if path is None or empty
            log_map_server(
                f"{symbols.get('error', '')} Compiled mapnik.xml path is not provided. Cannot deploy.",
                "error",
                self.logger,
                self.app_settings,
            )
            raise ValueError("Compiled XML path is required for deployment.")

        source_mapnik_xml = Path(compiled_xml_path_str)
        if (
            not source_mapnik_xml.is_file()
            or source_mapnik_xml.stat().st_size == 0
        ):
            log_map_server(
                f"{symbols.get('error', '')} Compiled mapnik.xml at {source_mapnik_xml} is missing or empty. Cannot deploy.",
                "error",
                self.logger,
                self.app_settings,
            )
            raise FileNotFoundError(
                f"Valid mapnik.xml not found at {source_mapnik_xml} for deployment."
            )

        target_dir = Path(self.MAPNIK_STYLE_TARGET_DIR_CONFIG)
        target_xml_path = (
            target_dir / "mapnik.xml"
        )  # Standard name in target dir

        run_elevated_command(
            ["mkdir", "-p", str(target_dir)],
            self.app_settings,
            current_logger=self.logger,
        )
        run_elevated_command(
            ["cp", str(source_mapnik_xml), str(target_xml_path)],
            self.app_settings,
            current_logger=self.logger,
        )
        run_elevated_command(
            ["chmod", "644", str(target_xml_path)],
            self.app_settings,
            current_logger=self.logger,
        )  # Standard read permissions
        log_map_server(
            f"{symbols.get('success', '')} mapnik.xml copied to {target_xml_path}",
            "success",
            self.logger,
            self.app_settings,
        )

    def _finalize_carto_directory_processing(self) -> None:
        """
        Revert ownership of the Carto directory to root:root after processing.
        """
        symbols = self.app_settings.symbols
        log_map_server(
            f"{symbols.get('info', '')} Reverting ownership of {self.OSM_CARTO_BASE_DIR_CONFIG} to root:root.",
            "info",
            self.logger,
            self.app_settings,
        )
        run_elevated_command(
            ["chown", "-R", "root:root", self.OSM_CARTO_BASE_DIR_CONFIG],
            self.app_settings,
            current_logger=self.logger,
        )
        log_map_server(
            f"{symbols.get('success', '')} Ownership of {self.OSM_CARTO_BASE_DIR_CONFIG} reverted to root.",
            "success",
            self.logger,
            self.app_settings,
        )

    def _update_font_cache(self) -> None:
        """
        Update the system font cache using the fc-cache command.
        """
        symbols = self.app_settings.symbols
        log_map_server(
            f"{symbols.get('step', '')} Updating font cache (fc-cache -fv)...",
            "info",
            self.logger,
            self.app_settings,
        )
        try:
            run_elevated_command(
                ["fc-cache", "-fv"],
                self.app_settings,
                current_logger=self.logger,
            )
            log_map_server(
                f"{symbols.get('success', '')} Font cache updated.",
                "success",
                self.logger,
                self.app_settings,
            )
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '')} Failed to update font cache: {e}",
                "error",
                self.logger,
                self.app_settings,
            )
            # This might not be fatal for all setups, but important for map rendering
