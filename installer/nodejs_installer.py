# installer/nodejs_installer.py
# -*- coding: utf-8 -*-
"""
Handles the installation of Node.js LTS (Long Term Support).
"""
import logging
from typing import Optional

from common.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)


def install_nodejs_lts(
        app_settings: AppSettings,
        current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(f"{symbols.get('step', '➡️')} Installing Node.js LTS using NodeSource...", "info", logger_to_use,
                   app_settings)
    try:
        # NodeSource setup URL - could be made configurable in AppSettings.nodejs if different versions needed
        nodesource_version_setup = getattr(app_settings, 'nodejs_version_setup_script', "setup_lts.x")
        nodesource_setup_url = f"https://deb.nodesource.com/{nodesource_version_setup}"

        log_map_server(f"{symbols.get('gear', '⚙️')} Downloading NodeSource script from {nodesource_setup_url}...",
                       "info", logger_to_use, app_settings)
        curl_res = run_command(["curl", "-fsSL", nodesource_setup_url], app_settings, capture_output=True, check=True,
                               current_logger=logger_to_use)

        log_map_server(f"{symbols.get('gear', '⚙️')} Executing NodeSource setup script...", "info", logger_to_use,
                       app_settings)
        run_elevated_command(["bash", "-"], app_settings, cmd_input=curl_res.stdout, current_logger=logger_to_use)

        run_elevated_command(["apt", "update"], app_settings, current_logger=logger_to_use)
        log_map_server(f"{symbols.get('package', '📦')} Installing Node.js...", "info", logger_to_use, app_settings)
        run_elevated_command(["apt", "--yes", "install", "nodejs"], app_settings, current_logger=logger_to_use)

        node_ver_res = run_command(["node", "--version"], app_settings, capture_output=True, check=False,
                                   current_logger=logger_to_use)
        npm_ver_res = run_command(["npm", "--version"], app_settings, capture_output=True, check=False,
                                  current_logger=logger_to_use)
        node_ver = node_ver_res.stdout.strip() if node_ver_res.returncode == 0 else "N/A"
        npm_ver = npm_ver_res.stdout.strip() if npm_ver_res.returncode == 0 else "N/A"

        log_map_server(f"{symbols.get('success', '✅')} Node.js installed. Version: {node_ver}, NPM Version: {npm_ver}",
                       "success", logger_to_use, app_settings)
    except Exception as e:
        log_map_server(f"{symbols.get('error', '❌')} Failed to install Node.js LTS: {e}", "error", logger_to_use,
                       app_settings, exc_info=True)
        raise