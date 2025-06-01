# setup/cli_handler.py
# -*- coding: utf-8 -*-
"""
Handles Command Line Interface (CLI) interactions for the map server setup.
"""

import datetime
import logging
from typing import Optional
from common.system_utils import get_current_script_hash
from common.command_utils import log_map_server
# get_current_script_hash is now in common.system_utils, state_manager imports it
# Import static_config for OSM_PROJECT_ROOT, STATE_FILE_PATH, SCRIPT_VERSION
from setup import config as static_config
from setup.config_models import (  # For type hinting and default comparison
    PGPASSWORD_DEFAULT,
    AppSettings,
)

module_logger = logging.getLogger(__name__)


def cli_prompt_for_rerun(
        prompt_message: str,
        app_settings: AppSettings,
        current_logger_instance: Optional[logging.Logger] = None,
) -> bool:
    logger_to_use = (
        current_logger_instance if current_logger_instance else module_logger
    )
    symbols = app_settings.symbols
    try:
        user_input = (
            input(f"   {symbols.get('info', 'ℹ️')} {prompt_message} (y/N): ")
            .strip()
            .lower()
        )
        return user_input == "y"
    except EOFError:  # Handle non-interactive environments
        log_map_server(
            f"{symbols.get('warning', '!')} No user input (EOF), defaulting to 'N' for prompt: '{prompt_message}'",
            "warning",
            logger_to_use,
            app_settings,
        )
        return False


def view_configuration(
        app_config: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_config.symbols

    config_text = f"{symbols.get('info', 'ℹ️')} Current effective configuration values (CLI > YAML > ENV > Defaults):\n\n"
    config_text += (
        f"  Admin Group IP:                {app_config.admin_group_ip}\n"
    )
    config_text += (
        f"  GTFS Feed URL:                 {app_config.gtfs_feed_url}\n"
    )
    config_text += (
        f"  VM IP or Domain:               {app_config.vm_ip_or_domain}\n"
    )
    config_text += f"  pg_tileserv Binary Location:   {app_config.pg_tileserv_binary_location}\n"
    config_text += (
        f"  Log Prefix (installer):        {app_config.log_prefix}\n"
    )
    config_text += f"  Container Runtime Command:     {app_config.container_runtime_command}\n"
    config_text += (
        f"  OSRM Image Tag:                {app_config.osrm_image_tag}\n\n"
    )

    config_text += "  PostgreSQL Settings (pg.*):\n"
    config_text += f"    Host:                        {app_config.pg.host}\n"
    config_text += f"    Port:                        {app_config.pg.port}\n"
    config_text += (
        f"    Database:                    {app_config.pg.database}\n"
    )
    config_text += f"    User:                        {app_config.pg.user}\n"

    pg_password_display = "[FROM CONFIGURATION (ENV/YAML/CLI)]"
    if (
            app_config.pg.password == PGPASSWORD_DEFAULT
            and not app_config.dev_override_unsafe_password
    ):  # PGPASSWORD_DEFAULT from config_models
        pg_password_display = "[DEFAULT - Potentially Insecure! Override via ENV, YAML, or CLI -W]"
    elif (
            app_config.pg.password == PGPASSWORD_DEFAULT
            and app_config.dev_override_unsafe_password
    ):
        pg_password_display = "[DEFAULT - Dev override active]"
    elif not app_config.pg.password:  # Should be rare with Pydantic defaults
        pg_password_display = "[NOT SET or EMPTY - Check Configuration]"
    config_text += (
        f"    Password:                    {pg_password_display}\n\n"
    )

    config_text += f"  Developer Override Unsafe PW:  {app_config.dev_override_unsafe_password}\n\n"

    config_text += (
        f"  State File Path (static):      {static_config.STATE_FILE_PATH}\n"
    )
    current_hash = (
            get_current_script_hash(
                project_root_dir=static_config.OSM_PROJECT_ROOT,
                app_settings=app_config,
                logger_instance=logger_to_use,
            )
            or "N/A"
    )
    config_text += f"  Script Hash:                   {current_hash}\n"
    config_text += (
        f"  Script Version (static):       {static_config.SCRIPT_VERSION}\n"
    )
    config_text += f"  Timestamp (current view):      {datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S')}\n\n"
    config_text += "Configuration is loaded with precedence: CLI > YAML File > Environment Variables > Model Defaults."

    log_map_server(
        "Displaying current configuration:", "info", logger_to_use, app_config
    )
    print(f"\n{config_text}\n")

# manage_state_interactive and show_menu would also need app_settings
# if they use log_map_server or call functions that do.
