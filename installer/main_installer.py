# installer/main_installer.py
# -*- coding: utf-8 -*-
"""
Main entry point and orchestrator for the Map Server Setup script.
Handles argument parsing, logging setup, and calls a sequence of setup steps
from various modules.
"""

import argparse
import logging
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import yaml  # Added for YAML output

from common.command_utils import log_map_server
from common.core_utils import setup_logging as common_setup_logging
from common.pgpass_utils import setup_pgpass
from common.system_utils import (
    get_current_script_hash,
    get_primary_ip_address,
    systemd_reload,
)
from installer.apache_installer import ensure_apache_packages_installed
from installer.carto_installer import (
    fetch_carto_external_data,
    install_carto_cli,
    prepare_carto_directory_for_processing,
    setup_osm_carto_repository,
)
from installer.certbot_installer import install_certbot_packages
from installer.docker_installer import install_docker_engine
from installer.nginx_installer import ensure_nginx_package_installed
from installer.nodejs_installer import install_nodejs_lts
from installer.osrm_installer import (
    download_base_pbf,
    ensure_osrm_dependencies,
    prepare_region_boundaries,
    setup_osrm_data_directories,
)
from installer.pg_tileserv_installer import (
    create_pg_tileserv_system_user,
    download_and_install_pg_tileserv_binary,
    setup_pg_tileserv_binary_permissions,
)
from installer.postgres_installer import (
    ensure_postgres_packages_are_installed,
)
from installer.renderd_installer import (
    create_renderd_directories,
    create_renderd_systemd_service_file,
    ensure_renderd_packages_installed,
)
from installer.ufw_installer import ensure_ufw_package_installed
from processors.data_handling.data_processing import data_prep_group
from processors.data_handling.osrm_data_processor import (
    build_osrm_graphs_for_region,
    extract_regional_pbfs_with_osmium,
)
from processors.data_handling.raster_processor import raster_tile_prerender
from processors.plugins.importers.transit.gtfs.orchestrator import (
    process_and_setup_gtfs,
)
from setup import config as static_config

# Import all individual step functions
from setup.actions import deploy_test_website_content
from setup.cli_handler import cli_prompt_for_rerun, view_configuration
from setup.config_loader import load_app_settings
from setup.config_models import (
    ADMIN_GROUP_IP_DEFAULT,
    APACHE_LISTEN_PORT_DEFAULT,
    CONTAINER_RUNTIME_COMMAND_DEFAULT,
    GTFS_FEED_URL_DEFAULT,
    LOG_PREFIX_DEFAULT,
    OSRM_IMAGE_TAG_DEFAULT,
    PG_TILESERV_BINARY_LOCATION_DEFAULT,
    PGDATABASE_DEFAULT,
    PGHOST_DEFAULT,
    PGPASSWORD_DEFAULT,
    PGPORT_DEFAULT,
    PGUSER_DEFAULT,
    VM_IP_OR_DOMAIN_DEFAULT,
    AppSettings,
)
from setup.configure.apache_configurator import (
    activate_apache_service,
    configure_apache_ports,
    create_apache_tile_site_config,
    create_mod_tile_config,
    manage_apache_modules_and_sites,
)
from setup.configure.carto_configurator import (
    compile_osm_carto_stylesheet,
    deploy_mapnik_stylesheet,
    finalize_carto_directory_processing,
    update_font_cache,
)
from setup.configure.certbot_configurator import run_certbot_nginx
from setup.configure.nginx_configurator import (
    activate_nginx_service,
    create_nginx_proxy_site_config,
    manage_nginx_sites,
    test_nginx_configuration,
)
from setup.configure.osrm_configurator import (
    activate_osrm_routed_service,
    create_osrm_routed_service_file,
)
from setup.configure.pg_tileserv_configurator import (
    activate_pg_tileserv_service,
    create_pg_tileserv_config_file,
    create_pg_tileserv_systemd_service_file,
)
from setup.configure.postgres_configurator import (
    create_postgres_user_and_db,
    customize_pg_hba_conf,
    customize_postgresql_conf,
    enable_postgres_extensions,
    restart_and_enable_postgres_service,
    set_postgres_permissions,
)
from setup.configure.renderd_configurator import (
    activate_renderd_service,
    create_renderd_conf_file,
)
from setup.configure.ufw_configurator import (
    activate_ufw_service,
    apply_ufw_rules,
)
from setup.core_prerequisites import boot_verbosity as prereq_boot_verbosity
from setup.core_prerequisites import (
    core_conflict_removal,
    core_prerequisites_group,
)
from setup.state_manager import (
    clear_state_file,
    initialize_state_system,
    view_completed_steps,
)
from setup.step_executor import execute_step

logger = logging.getLogger(__name__)
APP_CONFIG: Optional[AppSettings] = None

StepExecutorFunc = Callable[[AppSettings, Optional[logging.Logger]], None]

PREREQ_BOOT_VERBOSITY_TAG = "PREREQ_BOOT_VERBOSITY_TAG"
PREREQ_CORE_CONFLICTS_TAG = "PREREQ_CORE_CONFLICTS_TAG"
PREREQ_DOCKER_ENGINE_TAG = "PREREQ_DOCKER_ENGINE_TAG"
PREREQ_NODEJS_LTS_TAG = "PREREQ_NODEJS_LTS_TAG"
ALL_CORE_PREREQUISITES_GROUP_TAG = "ALL_CORE_PREREQUISITES_GROUP"
UFW_PACKAGE_CHECK_TAG = "SETUP_UFW_PKG_CHECK"
CONFIG_UFW_RULES = "CONFIG_UFW_RULES"
UFW_ACTIVATE_SERVICE_TAG = "SERVICE_UFW_ACTIVATE"
UFW_FULL_SETUP = "UFW_FULL_SETUP"
SETUP_POSTGRES_PKG_CHECK = "SETUP_POSTGRES_PKG_CHECK"
CONFIG_POSTGRES_USER_DB = "CONFIG_POSTGRES_USER_DB"
CONFIG_POSTGRES_EXTENSIONS = "CONFIG_POSTGRES_EXTENSIONS"
CONFIG_POSTGRES_PERMISSIONS = "CONFIG_POSTGRES_PERMISSIONS"
CONFIG_POSTGRESQL_CONF = "CONFIG_POSTGRESQL_CONF"
CONFIG_PG_HBA_CONF = "CONFIG_PG_HBA_CONF"
SERVICE_POSTGRES_RESTART_ENABLE = "SERVICE_POSTGRES_RESTART_ENABLE"
POSTGRES_FULL_SETUP = "POSTGRES_FULL_SETUP"
SETUP_PGTILESERV_DOWNLOAD_BINARY = "SETUP_PGTILESERV_DOWNLOAD_BINARY"
SETUP_PGTILESERV_CREATE_USER = "SETUP_PGTILESERV_CREATE_USER"
SETUP_PGTILESERV_BINARY_PERMS = "SETUP_PGTILESERV_BINARY_PERMS"
SETUP_PGTILESERV_SYSTEMD_FILE = "SETUP_PGTILESERV_SYSTEMD_FILE"
CONFIG_PGTS_CONFIG_FILE = "CONFIG_PGTS_CONFIG_FILE"
SERVICE_PGTS_ACTIVATE = "SERVICE_PGTS_ACTIVATE"
PGTILESERV_FULL_SETUP = "PGTILESERV_FULL_SETUP"
SETUP_CARTO_CLI = "SETUP_CARTO_CLI"
SETUP_CARTO_REPO = "SETUP_CARTO_REPO"
SETUP_CARTO_PREPARE_DIR = "SETUP_CARTO_PREPARE_DIR"
SETUP_CARTO_FETCH_DATA = "SETUP_CARTO_FETCH_DATA"
CONFIG_CARTO_COMPILE = "CONFIG_CARTO_COMPILE"
CONFIG_CARTO_DEPLOY_XML = "CONFIG_CARTO_DEPLOY_XML"
CONFIG_CARTO_FINALIZE_DIR = "CONFIG_CARTO_FINALIZE_DIR"
CONFIG_SYSTEM_FONT_CACHE = "CONFIG_SYSTEM_FONT_CACHE"
CARTO_FULL_SETUP = "CARTO_FULL_SETUP"
SETUP_RENDERD_PKG_CHECK = "SETUP_RENDERD_PKG_CHECK"
SETUP_RENDERD_DIRS = "SETUP_RENDERD_DIRS"
SETUP_RENDERD_SYSTEMD_FILE = "SETUP_RENDERD_SYSTEMD_FILE"
CONFIG_RENDERD_CONF_FILE = "CONFIG_RENDERD_CONF_FILE"
SERVICE_RENDERD_ACTIVATE = "SERVICE_RENDERD_ACTIVATE"
RENDERD_FULL_SETUP = "RENDERD_FULL_SETUP"
SETUP_OSRM_DEPS = "SETUP_OSRM_DEPS"
SETUP_OSRM_DIRS = "SETUP_OSRM_DIRS"
SETUP_OSRM_DOWNLOAD_PBF = "SETUP_OSRM_DOWNLOAD_PBF"
SETUP_OSRM_REGION_BOUNDARIES = "SETUP_OSRM_REGION_BOUNDARIES"
DATAPROC_OSMIUM_EXTRACT_REGIONS = "DATAPROC_OSMIUM_EXTRACT_REGIONS"
DATAPROC_OSRM_BUILD_GRAPHS_ALL_REGIONS = (
    "DATAPROC_OSRM_BUILD_GRAPHS_ALL_REGIONS"
)
SETUP_OSRM_SYSTEMD_SERVICES_ALL_REGIONS = (
    "SETUP_OSRM_SYSTEMD_SERVICES_ALL_REGIONS"
)
CONFIG_OSRM_ACTIVATE_SERVICES_ALL_REGIONS = (
    "CONFIG_OSRM_ACTIVATE_SERVICES_ALL_REGIONS"
)
OSRM_FULL_SETUP = "OSRM_FULL_SETUP"
SETUP_APACHE_PKG_CHECK = "SETUP_APACHE_PKG_CHECK"
CONFIG_APACHE_PORTS = "CONFIG_APACHE_PORTS"
CONFIG_APACHE_MOD_TILE_CONF = "CONFIG_APACHE_MOD_TILE_CONF"
CONFIG_APACHE_TILE_SITE_CONF = "CONFIG_APACHE_TILE_SITE_CONF"
CONFIG_APACHE_MODULES_SITES = "CONFIG_APACHE_MODULES_SITES"
SERVICE_APACHE_ACTIVATE = "SERVICE_APACHE_ACTIVATE"
APACHE_FULL_SETUP = "APACHE_FULL_SETUP"
SETUP_NGINX_PKG_CHECK = "SETUP_NGINX_PKG_CHECK"
CONFIG_NGINX_PROXY_SITE = "CONFIG_NGINX_PROXY_SITE"
CONFIG_NGINX_MANAGE_SITES = "CONFIG_NGINX_MANAGE_SITES"
CONFIG_NGINX_TEST_CONFIG = "CONFIG_NGINX_TEST_CONFIG"
SERVICE_NGINX_ACTIVATE = "SERVICE_NGINX_ACTIVATE"
NGINX_FULL_SETUP = "NGINX_FULL_SETUP"
SETUP_CERTBOT_PACKAGES = "SETUP_CERTBOT_PACKAGES"
CONFIG_CERTBOT_RUN = "CONFIG_CERTBOT_RUN"
CERTBOT_FULL_SETUP = "CERTBOT_FULL_SETUP"
GTFS_PROCESS_AND_SETUP_TAG = "GTFS_PROCESS_AND_SETUP"
RASTER_PREP_TAG = "RASTER_PREP"
WEBSITE_CONTENT_DEPLOY_TAG = "WEBSITE_CONTENT_DEPLOY"
SYSTEMD_RELOAD_TASK_TAG = "SYSTEMD_RELOAD_TASK"

INSTALLATION_GROUPS_ORDER: List[Dict[str, Any]] = [
    {
        "name": "Comprehensive Prerequisites",
        "steps": [ALL_CORE_PREREQUISITES_GROUP_TAG],
    },
    {
        "name": "Firewall Service (UFW)",
        "steps": [
            UFW_PACKAGE_CHECK_TAG,
            CONFIG_UFW_RULES,
            UFW_ACTIVATE_SERVICE_TAG,
        ],
    },
    {
        "name": "Database Service (PostgreSQL)",
        "steps": [
            SETUP_POSTGRES_PKG_CHECK,
            CONFIG_POSTGRES_USER_DB,
            CONFIG_POSTGRES_EXTENSIONS,
            CONFIG_POSTGRES_PERMISSIONS,
            CONFIG_POSTGRESQL_CONF,
            CONFIG_PG_HBA_CONF,
            SERVICE_POSTGRES_RESTART_ENABLE,
        ],
    },
    {
        "name": "pg_tileserv Service",
        "steps": [
            SETUP_PGTILESERV_DOWNLOAD_BINARY,
            SETUP_PGTILESERV_CREATE_USER,
            SETUP_PGTILESERV_BINARY_PERMS,
            SETUP_PGTILESERV_SYSTEMD_FILE,
            CONFIG_PGTS_CONFIG_FILE,
            SERVICE_PGTS_ACTIVATE,
        ],
    },
    {
        "name": "Carto Service",
        "steps": [
            SETUP_CARTO_CLI,
            SETUP_CARTO_REPO,
            SETUP_CARTO_PREPARE_DIR,
            SETUP_CARTO_FETCH_DATA,
            CONFIG_CARTO_COMPILE,
            CONFIG_CARTO_DEPLOY_XML,
            CONFIG_CARTO_FINALIZE_DIR,
            CONFIG_SYSTEM_FONT_CACHE,
        ],
    },
    {
        "name": "Renderd Service",
        "steps": [
            SETUP_RENDERD_PKG_CHECK,
            SETUP_RENDERD_DIRS,
            SETUP_RENDERD_SYSTEMD_FILE,
            CONFIG_RENDERD_CONF_FILE,
            SERVICE_RENDERD_ACTIVATE,
        ],
    },
    {
        "name": "OSRM Service & Data Processing",
        "steps": [
            SETUP_OSRM_DEPS,
            SETUP_OSRM_DIRS,
            SETUP_OSRM_DOWNLOAD_PBF,
            SETUP_OSRM_REGION_BOUNDARIES,
            DATAPROC_OSMIUM_EXTRACT_REGIONS,
            DATAPROC_OSRM_BUILD_GRAPHS_ALL_REGIONS,
            SETUP_OSRM_SYSTEMD_SERVICES_ALL_REGIONS,
            CONFIG_OSRM_ACTIVATE_SERVICES_ALL_REGIONS,
        ],
    },
    {
        "name": "Apache Service",
        "steps": [
            SETUP_APACHE_PKG_CHECK,
            CONFIG_APACHE_PORTS,
            CONFIG_APACHE_MOD_TILE_CONF,
            CONFIG_APACHE_TILE_SITE_CONF,
            CONFIG_APACHE_MODULES_SITES,
            SERVICE_APACHE_ACTIVATE,
        ],
    },
    {
        "name": "Nginx Service",
        "steps": [
            SETUP_NGINX_PKG_CHECK,
            CONFIG_NGINX_PROXY_SITE,
            CONFIG_NGINX_MANAGE_SITES,
            CONFIG_NGINX_TEST_CONFIG,
            SERVICE_NGINX_ACTIVATE,
        ],
    },
    {
        "name": "Certbot Service",
        "steps": [SETUP_CERTBOT_PACKAGES, CONFIG_CERTBOT_RUN],
    },
    {"name": "Application Content", "steps": [WEBSITE_CONTENT_DEPLOY_TAG]},
    {"name": "GTFS Data Pipeline", "steps": [GTFS_PROCESS_AND_SETUP_TAG]},
    {"name": "Raster Tile Pre-rendering", "steps": [RASTER_PREP_TAG]},
    {"name": "Systemd Reload", "steps": [SYSTEMD_RELOAD_TASK_TAG]},
]

task_execution_details_lookup: Dict[str, Tuple[str, int]] = {
    step_tag: (group_info["name"], step_idx + 1)
    for group_info in INSTALLATION_GROUPS_ORDER
    for step_idx, step_tag in enumerate(group_info["steps"])
}
task_execution_details_lookup.update({
    ALL_CORE_PREREQUISITES_GROUP_TAG: ("Comprehensive Prerequisites", 0),
    UFW_FULL_SETUP: ("Firewall Service (UFW)", 0),
    POSTGRES_FULL_SETUP: ("Database Service (PostgreSQL)", 0),
    CARTO_FULL_SETUP: ("Carto Service", 0),
    RENDERD_FULL_SETUP: ("Renderd Service", 0),
    NGINX_FULL_SETUP: ("Nginx Service", 0),
    PGTILESERV_FULL_SETUP: ("pg_tileserv Service", 0),
    OSRM_FULL_SETUP: ("OSRM Service & Data Processing", 0),
    APACHE_FULL_SETUP: ("Apache Service", 0),
    CERTBOT_FULL_SETUP: ("Certbot Service", 0),
})
group_order_lookup: Dict[str, int] = {
    group_info["name"]: index
    for index, group_info in enumerate(INSTALLATION_GROUPS_ORDER)
}


def get_dynamic_help(base_help: str, task_tag: str) -> str:
    details = task_execution_details_lookup.get(task_tag)
    if details and details[1] > 0:
        return f"{base_help} (Part of Group: '{details[0]}', Sub-step: {details[1]})"
    elif details and details[1] == 0:
        return f"{base_help} (Orchestrates Group: '{details[0]}')"
    return f"{base_help} (Specific task or component)"


def ufw_full_setup_sequence(
    app_cfg: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(
        f"--- {app_cfg.symbols.get('step', '➡️')} Starting UFW Full Setup ---",
        level="info",
        current_logger=logger_to_use,
        app_settings=app_cfg,
    )
    steps: List[Tuple[str, str, StepExecutorFunc]] = [
        (
            UFW_PACKAGE_CHECK_TAG,
            "Check UFW Package Installation",
            ensure_ufw_package_installed,
        ),
        (CONFIG_UFW_RULES, "Configure UFW Rules", apply_ufw_rules),
        (
            UFW_ACTIVATE_SERVICE_TAG,
            "Activate UFW Service",
            activate_ufw_service,
        ),
    ]
    for tag, desc, func in steps:
        if not execute_step(
            tag, desc, func, app_cfg, logger_to_use, cli_prompt_for_rerun
        ):
            raise RuntimeError(f"UFW step '{desc}' failed.")
    log_map_server(
        f"--- {app_cfg.symbols.get('success', '✅')} UFW Full Setup Completed ---",
        level="success",
        current_logger=logger_to_use,
        app_settings=app_cfg,
    )


def postgres_full_setup_sequence(
    app_cfg: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(
        f"--- {app_cfg.symbols.get('step', '➡️')} PostgreSQL Full Setup ---",
        level="info",
        current_logger=logger_to_use,
        app_settings=app_cfg,
    )
    steps: List[Tuple[str, str, StepExecutorFunc]] = [
        (
            SETUP_POSTGRES_PKG_CHECK,
            "Check PostgreSQL Packages",
            ensure_postgres_packages_are_installed,
        ),
        (
            CONFIG_POSTGRES_USER_DB,
            "Create PostgreSQL User & Database",
            create_postgres_user_and_db,
        ),
        (
            CONFIG_POSTGRES_EXTENSIONS,
            "Enable PostgreSQL Extensions",
            enable_postgres_extensions,
        ),
        (
            CONFIG_POSTGRES_PERMISSIONS,
            "Set PostgreSQL Permissions",
            set_postgres_permissions,
        ),
        (
            CONFIG_POSTGRESQL_CONF,
            "Customize postgresql.conf",
            customize_postgresql_conf,
        ),
        (CONFIG_PG_HBA_CONF, "Customize pg_hba.conf", customize_pg_hba_conf),
        (
            SERVICE_POSTGRES_RESTART_ENABLE,
            "Restart & Enable PostgreSQL",
            restart_and_enable_postgres_service,
        ),
    ]
    for tag, desc, func in steps:
        if not execute_step(
            tag, desc, func, app_cfg, logger_to_use, cli_prompt_for_rerun
        ):
            raise RuntimeError(f"PostgreSQL step '{desc}' failed.")
    log_map_server(
        f"--- {app_cfg.symbols.get('success', '✅')} PostgreSQL Full Setup Completed ---",
        level="success",
        current_logger=logger_to_use,
        app_settings=app_cfg,
    )


def carto_full_setup_sequence(
    app_cfg: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(
        f"--- {app_cfg.symbols.get('step', '➡️')} Carto Full Setup ---",
        level="info",
        current_logger=logger_to_use,
        app_settings=app_cfg,
    )
    compiled_xml_path_holder: Dict[str, Optional[str]] = {"path": None}

    def _compile_step(ac: AppSettings, cl: Optional[logging.Logger]) -> None:
        path_result = compile_osm_carto_stylesheet(ac, cl)
        if not path_result:
            raise RuntimeError(
                "compile_osm_carto_stylesheet did not return a valid path or failed."
            )
        compiled_xml_path_holder["path"] = path_result

    def _deploy_step(ac: AppSettings, cl: Optional[logging.Logger]) -> None:
        xml_path_to_deploy = compiled_xml_path_holder["path"]
        if not xml_path_to_deploy:
            raise RuntimeError(
                "Compiled XML path not set or is invalid for deployment."
            )
        deploy_mapnik_stylesheet(xml_path_to_deploy, ac, cl)

    steps: List[Tuple[str, str, StepExecutorFunc]] = [
        (SETUP_CARTO_CLI, "Install Carto CLI", install_carto_cli),
        (
            SETUP_CARTO_REPO,
            "Setup OSM-Carto Repository",
            setup_osm_carto_repository,
        ),
        (
            SETUP_CARTO_PREPARE_DIR,
            "Prepare Carto Directory",
            prepare_carto_directory_for_processing,
        ),
        (
            SETUP_CARTO_FETCH_DATA,
            "Fetch Carto External Data",
            fetch_carto_external_data,
        ),
        (CONFIG_CARTO_COMPILE, "Compile OSM Carto Stylesheet", _compile_step),
        (CONFIG_CARTO_DEPLOY_XML, "Deploy Mapnik Stylesheet", _deploy_step),
        (
            CONFIG_CARTO_FINALIZE_DIR,
            "Finalize Carto Directory",
            finalize_carto_directory_processing,
        ),
        (CONFIG_SYSTEM_FONT_CACHE, "Update Font Cache", update_font_cache),
    ]
    try:
        for tag, desc, func in steps:
            if not execute_step(
                tag, desc, func, app_cfg, logger_to_use, cli_prompt_for_rerun
            ):
                raise RuntimeError(f"Carto step '{desc}' failed.")
    except Exception as e:
        log_map_server(
            f"{app_cfg.symbols.get('error', '❌')} Error in Carto sequence: {e}. Finalizing.",
            level="error",
            current_logger=logger_to_use,
            app_settings=app_cfg,
        )
        try:
            finalize_carto_directory_processing(app_cfg, logger_to_use)
        except Exception as ef:
            log_map_server(
                f"{app_cfg.symbols.get('error', '❌')} Finalization error: {ef}",
                level="error",
                current_logger=logger_to_use,
                app_settings=app_cfg,
            )
        raise
    log_map_server(
        f"--- {app_cfg.symbols.get('success', '✅')} Carto Full Setup Completed ---",
        level="success",
        current_logger=logger_to_use,
        app_settings=app_cfg,
    )


def renderd_full_setup_sequence(
    app_cfg: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(
        f"--- {app_cfg.symbols.get('step', '➡️')} Renderd Full Setup ---",
        level="info",
        current_logger=logger_to_use,
        app_settings=app_cfg,
    )
    steps: List[Tuple[str, str, StepExecutorFunc]] = [
        (
            SETUP_RENDERD_PKG_CHECK,
            "Check Renderd Packages",
            ensure_renderd_packages_installed,
        ),
        (
            SETUP_RENDERD_DIRS,
            "Create Renderd Directories",
            create_renderd_directories,
        ),
        (
            SETUP_RENDERD_SYSTEMD_FILE,
            "Create Renderd Systemd File",
            create_renderd_systemd_service_file,
        ),
        (
            CONFIG_RENDERD_CONF_FILE,
            "Create renderd.conf",
            create_renderd_conf_file,
        ),
        (
            SERVICE_RENDERD_ACTIVATE,
            "Activate Renderd Service",
            activate_renderd_service,
        ),
    ]
    for tag, desc, func in steps:
        if not execute_step(
            tag, desc, func, app_cfg, logger_to_use, cli_prompt_for_rerun
        ):
            raise RuntimeError(f"Renderd step '{desc}' failed.")
    log_map_server(
        f"--- {app_cfg.symbols.get('success', '✅')} Renderd Full Setup Completed ---",
        level="success",
        current_logger=logger_to_use,
        app_settings=app_cfg,
    )


def apache_full_setup_sequence(
    app_cfg: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(
        f"--- {app_cfg.symbols.get('step', '➡️')} Apache Full Setup ---",
        level="info",
        current_logger=logger_to_use,
        app_settings=app_cfg,
    )
    steps: List[Tuple[str, str, StepExecutorFunc]] = [
        (
            SETUP_APACHE_PKG_CHECK,
            "Check Apache Packages",
            ensure_apache_packages_installed,
        ),
        (
            CONFIG_APACHE_PORTS,
            "Configure Apache Ports",
            configure_apache_ports,
        ),
        (
            CONFIG_APACHE_MOD_TILE_CONF,
            "Create mod_tile.conf",
            create_mod_tile_config,
        ),
        (
            CONFIG_APACHE_TILE_SITE_CONF,
            "Create Apache Tile Site",
            create_apache_tile_site_config,
        ),
        (
            CONFIG_APACHE_MODULES_SITES,
            "Manage Apache Modules/Sites",
            manage_apache_modules_and_sites,
        ),
        (
            SERVICE_APACHE_ACTIVATE,
            "Activate Apache Service",
            activate_apache_service,
        ),
    ]
    for tag, desc, func in steps:
        if not execute_step(
            tag, desc, func, app_cfg, logger_to_use, cli_prompt_for_rerun
        ):
            raise RuntimeError(f"Apache step '{desc}' failed.")
    log_map_server(
        f"--- {app_cfg.symbols.get('success', '✅')} Apache Full Setup Completed ---",
        level="success",
        current_logger=logger_to_use,
        app_settings=app_cfg,
    )


def nginx_full_setup_sequence(
    app_cfg: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(
        f"--- {app_cfg.symbols.get('step', '➡️')} Nginx Full Setup ---",
        level="info",
        current_logger=logger_to_use,
        app_settings=app_cfg,
    )
    steps: List[Tuple[str, str, StepExecutorFunc]] = [
        (
            SETUP_NGINX_PKG_CHECK,
            "Check Nginx Package",
            ensure_nginx_package_installed,
        ),
        (
            CONFIG_NGINX_PROXY_SITE,
            "Create Nginx Proxy Site",
            create_nginx_proxy_site_config,
        ),
        (CONFIG_NGINX_MANAGE_SITES, "Manage Nginx Sites", manage_nginx_sites),
        (
            CONFIG_NGINX_TEST_CONFIG,
            "Test Nginx Configuration",
            test_nginx_configuration,
        ),
        (
            SERVICE_NGINX_ACTIVATE,
            "Activate Nginx Service",
            activate_nginx_service,
        ),
    ]
    for tag, desc, func in steps:
        if not execute_step(
            tag, desc, func, app_cfg, logger_to_use, cli_prompt_for_rerun
        ):
            raise RuntimeError(f"Nginx step '{desc}' failed.")
    log_map_server(
        f"--- {app_cfg.symbols.get('success', '✅')} Nginx Full Setup Completed ---",
        level="success",
        current_logger=logger_to_use,
        app_settings=app_cfg,
    )


def certbot_full_setup_sequence(
    app_cfg: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(
        f"--- {app_cfg.symbols.get('step', '➡️')} Certbot Full Setup ---",
        level="info",
        current_logger=logger_to_use,
        app_settings=app_cfg,
    )
    steps: List[Tuple[str, str, StepExecutorFunc]] = [
        (
            SETUP_CERTBOT_PACKAGES,
            "Install Certbot Packages",
            install_certbot_packages,
        ),
        (CONFIG_CERTBOT_RUN, "Run Certbot for Nginx", run_certbot_nginx),
    ]
    for tag, desc, func in steps:  # pragma: no cover
        if not execute_step(
            tag, desc, func, app_cfg, logger_to_use, cli_prompt_for_rerun
        ):
            log_map_server(
                f"{app_cfg.symbols.get('warning', '!')} Certbot step '{desc}' failed/skipped.",
                level="warning",
                current_logger=logger_to_use,
                app_settings=app_cfg,
            )
            break
    log_map_server(
        f"--- {app_cfg.symbols.get('success', '✅')} Certbot Full Setup Attempted ---",
        level="success",
        current_logger=logger_to_use,
        app_settings=app_cfg,
    )


def pg_tileserv_full_setup_sequence(
    app_cfg: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(
        f"--- {app_cfg.symbols.get('step', '➡️')} pg_tileserv Full Setup ---",
        level="info",
        current_logger=logger_to_use,
        app_settings=app_cfg,
    )
    steps: List[Tuple[str, str, StepExecutorFunc]] = [
        (
            SETUP_PGTILESERV_DOWNLOAD_BINARY,
            "Download pg_tileserv Binary",
            download_and_install_pg_tileserv_binary,
        ),
        (
            SETUP_PGTILESERV_CREATE_USER,
            "Create pg_tileserv User",
            create_pg_tileserv_system_user,
        ),
        (
            SETUP_PGTILESERV_BINARY_PERMS,
            "Set pg_tileserv Permissions",
            setup_pg_tileserv_binary_permissions,
        ),
        (
            SETUP_PGTILESERV_SYSTEMD_FILE,
            "Create pg_tileserv Systemd File",
            create_pg_tileserv_systemd_service_file,
        ),
        (
            CONFIG_PGTS_CONFIG_FILE,
            "Create pg_tileserv config.toml",
            create_pg_tileserv_config_file,
        ),
        (
            SERVICE_PGTS_ACTIVATE,
            "Activate pg_tileserv Service",
            activate_pg_tileserv_service,
        ),
    ]
    for tag, desc, func in steps:
        if not execute_step(
            tag, desc, func, app_cfg, logger_to_use, cli_prompt_for_rerun
        ):
            raise RuntimeError(f"pg_tileserv step '{desc}' failed.")
    log_map_server(
        f"--- {app_cfg.symbols.get('success', '✅')} pg_tileserv Full Setup Completed ---",
        level="success",
        current_logger=logger_to_use,
        app_settings=app_cfg,
    )


def osrm_full_setup_sequence(
    app_cfg: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(
        f"--- {app_cfg.symbols.get('step', '➡️')} OSRM Full Setup & Data Processing ---",
        level="info",
        current_logger=logger_to_use,
        app_settings=app_cfg,
    )
    base_pbf_path_holder: Dict[str, Optional[str]] = {"path": None}

    def _download_pbf_step(
        ac: AppSettings, cl: Optional[logging.Logger]
    ) -> None:
        base_pbf_path_holder["path"] = download_base_pbf(ac, cl)

    regional_pbf_map_holder: Dict[str, Dict[str, str]] = {"map": {}}

    def _extract_regions_step(
        ac: AppSettings, cl: Optional[logging.Logger]
    ) -> None:
        pbf_path = base_pbf_path_holder["path"]
        if not pbf_path:
            raise RuntimeError(
                "Base PBF path not set or is invalid for extraction."
            )
        regional_pbf_map_holder["map"] = extract_regional_pbfs_with_osmium(
            pbf_path, ac, cl
        )

    infra_steps: List[Tuple[str, str, StepExecutorFunc]] = [
        (
            SETUP_OSRM_DEPS,
            "Ensure OSRM Dependencies",
            ensure_osrm_dependencies,
        ),
        (
            SETUP_OSRM_DIRS,
            "Setup OSRM Data Directories",
            setup_osrm_data_directories,
        ),
        (SETUP_OSRM_DOWNLOAD_PBF, "Download Base PBF", _download_pbf_step),
        (
            SETUP_OSRM_REGION_BOUNDARIES,
            "Prepare Region Boundaries",
            prepare_region_boundaries,
        ),
    ]
    for tag, desc, func in infra_steps:
        if not execute_step(
            tag, desc, func, app_cfg, logger_to_use, cli_prompt_for_rerun
        ):
            raise RuntimeError(f"OSRM infra step '{desc}' failed.")
    if not execute_step(
        DATAPROC_OSMIUM_EXTRACT_REGIONS,
        "Extract Regional PBFs",
        _extract_regions_step,
        app_cfg,
        logger_to_use,
        cli_prompt_for_rerun,
    ):
        raise RuntimeError("Osmium regional PBF extraction failed.")
    regional_map = regional_pbf_map_holder.get("map", {})
    if not regional_map:  # pragma: no cover
        log_map_server(
            f"{app_cfg.symbols.get('warning', '!')} No regional PBFs extracted. Skipping OSRM graph building.",
            level="warning",
            current_logger=logger_to_use,
            app_settings=app_cfg,
        )
        return
    processed_regions_count = 0
    for rn_key, rp_val_path in regional_map.items():

        def _build(
            ac: AppSettings,
            cl: Optional[logging.Logger],
            r: str = rn_key,
            p: str = rp_val_path,
        ) -> None:
            if not build_osrm_graphs_for_region(r, p, ac, cl):
                raise RuntimeError(
                    f"Failed to build OSRM graphs for region {r}"
                )

        current_build_tag = f"DATAPROC_OSRM_BUILD_GRAPH_{rn_key.upper()}"
        if not execute_step(
            current_build_tag,
            f"Build OSRM Graphs for {rn_key}",
            _build,
            app_cfg,
            logger_to_use,
            cli_prompt_for_rerun,
        ):
            continue

        def _create_svc(
            ac: AppSettings, cl: Optional[logging.Logger], r: str = rn_key
        ) -> None:
            create_osrm_routed_service_file(r, ac, cl)

        current_service_create_tag = (
            f"SETUP_OSRM_SYSTEMD_SERVICE_{rn_key.upper()}"
        )
        if not execute_step(
            current_service_create_tag,
            f"Create OSRM Service File for {rn_key}",
            _create_svc,
            app_cfg,
            logger_to_use,
            cli_prompt_for_rerun,
        ):
            continue

        def _activate_svc(
            ac: AppSettings, cl: Optional[logging.Logger], r: str = rn_key
        ) -> None:
            activate_osrm_routed_service(r, ac, cl)

        current_service_activate_tag = (
            f"CONFIG_OSRM_ACTIVATE_SERVICE_{rn_key.upper()}"
        )
        if not execute_step(
            current_service_activate_tag,
            f"Activate OSRM Service for {rn_key}",
            _activate_svc,
            app_cfg,
            logger_to_use,
            cli_prompt_for_rerun,
        ):
            continue
        processed_regions_count += 1
    if processed_regions_count:
        log_map_server(
            f"--- {app_cfg.symbols.get('success', '✅')} OSRM Setup Completed for {processed_regions_count} region(s) ---",
            level="success",
            current_logger=logger_to_use,
            app_settings=app_cfg,
        )
    else:
        log_map_server(
            f"{app_cfg.symbols.get('warning', '!')} No OSRM services successfully processed for any region.",
            level="warning",
            current_logger=logger_to_use,
            app_settings=app_cfg,
        )


def _wrapped_core_prerequisites_group(
    app_settings: AppSettings, logger_instance: Optional[logging.Logger]
) -> None:
    if not core_prerequisites_group(app_settings, logger_instance):
        raise RuntimeError("Core prerequisites group failed overall.")


def _wrapped_systemd_reload_step_group(
    app_settings: AppSettings, logger_instance: Optional[logging.Logger]
) -> None:
    if not systemd_reload_step_group(app_settings, logger_instance):
        raise RuntimeError(
            "Systemd reload step group failed."
        )  # pragma: no cover


def _wrapped_data_prep_group(
    app_settings: AppSettings, logger_instance: Optional[logging.Logger]
) -> None:
    if not data_prep_group(app_settings, logger_instance):
        raise RuntimeError("Data preparation group failed overall.")


def systemd_reload_step_group(
    app_cfg: AppSettings,
    current_logger_instance: Optional[logging.Logger] = None,
) -> bool:
    logger_to_use = (
        current_logger_instance if current_logger_instance else logger
    )
    return execute_step(
        SYSTEMD_RELOAD_TASK_TAG,
        "Reload Systemd Daemon (Core Action)",
        systemd_reload,
        app_cfg,
        logger_to_use,
        cli_prompt_for_rerun,
    )


def run_full_gtfs_module_wrapper(
    app_cfg: AppSettings, calling_logger: Optional[logging.Logger]
) -> None:
    process_and_setup_gtfs(
        app_settings=app_cfg, orchestrator_logger=calling_logger
    )


# Helper to map task flags/groups to relevant package lists from static_config
def get_packages_for_tasks(
    requested_cli_args: argparse.Namespace, app_settings: AppSettings
) -> Set[str]:
    """
    Determines the set of relevant Debian packages based on active CLI flags.
    """
    relevant_pkgs: Set[str] = set()

    # Mapping from CLI flag destinations (or conceptual group names) to package lists
    # This needs to be comprehensive.
    flag_to_pkg_lists_map: Dict[str, List[List[str]]] = {
        "run_all_core_prerequisites": [  # --prereqs group
            static_config.CORE_PREREQ_PACKAGES,
            static_config.PYTHON_SYSTEM_PACKAGES,
            static_config.POSTGRES_PACKAGES,
            static_config.MAPPING_PACKAGES,
            static_config.FONT_PACKAGES,
            [
                "unattended-upgrades",
                "tzdata",
            ],  # Explicitly add these if not in CORE_PREREQ_PACKAGES
        ],
        "ufw": [["ufw"]],  # --ufw orchestrator
        "postgres": [
            static_config.POSTGRES_PACKAGES
        ],  # --postgres orchestrator
        "renderd": [["renderd", "mapnik-utils"]],  # --renderd orchestrator
        "apache": [
            ["apache2", "libapache2-mod-tile"]
        ],  # --apache orchestrator
        "nginx": [["nginx"]],  # --nginx orchestrator
        "certbot": [
            ["certbot", "python3-certbot-nginx"]
        ],  # --certbot orchestrator
        # Note: carto, osrm, pg_tileserv might not install system packages via apt in their main flow,
        # but their dependencies (like Node.js for Carto, Docker for OSRM) are covered by --prereqs.
        # If they had direct package dependencies for their setup functions, list them here.
        # For example, if --osrm also implied needing 'osmium-tool', and it wasn't in CORE_PREREQ_PACKAGES
        # "osrm": [["osmium-tool"]],
    }

    # Add packages for individual task flags if they are set
    # This complements the group flags.
    # (This logic might need refinement based on how granular your task flags are vs. group flags)
    individual_task_flag_to_pkgs: Dict[str, List[str]] = {
        # if 'ufw_pkg_check' implies 'ufw' package, and it's not covered by a group flag if run standalone
        "ufw_pkg_check": ["ufw"],
        "postgres_pkg_check": static_config.POSTGRES_PACKAGES,
        # Assuming SETUP_POSTGRES_PKG_CHECK flag is postgres_pkg_check
        "renderd_pkg_check": ["renderd", "mapnik-utils"],
        "apache_pkg_check": ["apache2", "libapache2-mod-tile"],
        "nginx_pkg_check": ["nginx"],
        "certbot_pkg_install": ["certbot", "python3-certbot-nginx"],
        # Assuming SETUP_CERTBOT_PACKAGES flag is certbot_pkg_install
        # Individual core prereq tasks also map to their respective package lists
        # This ensures if run_all_core_prerequisites isn't set, but individual core steps are,
        # their packages are considered.
        "core_conflicts": [],  # No direct package list, but part of prereqs
        "docker_install": [],  # Handled by install_docker_engine, no direct static list here
        "nodejs_install": [],  # Handled by install_nodejs_lts
    }

    # Check group flags (like --prereqs, --postgres, etc.)
    for flag_name, list_of_pkg_lists in flag_to_pkg_lists_map.items():
        if getattr(requested_cli_args, flag_name, False):
            for pkg_list in list_of_pkg_lists:
                relevant_pkgs.update(pkg_list)

    # Check individual task flags (more granular, if any imply specific packages)
    for flag_name, pkg_list in individual_task_flag_to_pkgs.items():
        if getattr(requested_cli_args, flag_name, False):
            relevant_pkgs.update(pkg_list)

    # If --full is specified, consider all packages that have preseed definitions.
    # Or, more simply, if --full, it implies all groups, so the above logic should catch them.
    if getattr(requested_cli_args, "full", False):
        for _flag_name, list_of_pkg_lists in flag_to_pkg_lists_map.items():
            for pkg_list in list_of_pkg_lists:
                relevant_pkgs.update(pkg_list)
        # Ensure all core packages are included if --full is run, as they are fundamental
        relevant_pkgs.update(static_config.CORE_PREREQ_PACKAGES)
        relevant_pkgs.update(static_config.PYTHON_SYSTEM_PACKAGES)
        relevant_pkgs.update(static_config.POSTGRES_PACKAGES)
        relevant_pkgs.update(static_config.MAPPING_PACKAGES)
        relevant_pkgs.update(static_config.FONT_PACKAGES)
        relevant_pkgs.add("unattended-upgrades")
        relevant_pkgs.add("tzdata")

    # If no specific task flags were set that imply packages,
    # then we default to outputting all known preseed data.
    # The `generate_preseed_yaml` function will handle this logic.
    # This function just returns the identified packages based on flags.

    return relevant_pkgs


def generate_preseed_yaml_for_tasks(
    app_cfg: AppSettings,
    parsed_args: argparse.Namespace,  # Parsed CLI arguments
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Generates and prints preseed YAML data relevant to the tasks specified
    in parsed_args, or all known preseed data if no specific tasks are implied.
    """
    logger_to_use = current_logger if current_logger else logger
    symbols = app_cfg.symbols
    preseed_data_to_output: Dict[str, Dict[str, str]] = {}

    # Check if specific tasks/groups were provided directly to --generate-preseed-yaml
    specific_tasks = (
        parsed_args.generate_preseed_yaml
        if isinstance(parsed_args.generate_preseed_yaml, list)
        else []
    )

    # If specific tasks were provided directly to --generate-preseed-yaml
    if specific_tasks:
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Generating preseed values for specified tasks/groups: {', '.join(specific_tasks)}",
            "info",
            logger_to_use,
            app_cfg,
        )

        # Create a temporary namespace with the specified tasks set to True
        temp_args = argparse.Namespace()
        for arg_name, arg_value in vars(parsed_args).items():
            setattr(temp_args, arg_name, arg_value)

        # Set the specified tasks to True in the temporary namespace
        for task in specific_tasks:
            # Convert task names like "postgres" to the corresponding CLI flag
            task_flag = task.replace("-", "_")
            setattr(temp_args, task_flag, True)

        # Get packages for the specified tasks
        relevant_packages = get_packages_for_tasks(temp_args, app_cfg)

        if relevant_packages:
            log_map_server(
                f"{symbols.get('info', 'ℹ️')} Found packages for specified tasks: {', '.join(sorted(list(relevant_packages)))}",
                "info",
                logger_to_use,
                app_cfg,
            )
            for (
                pkg_name,
                preseed_values,
            ) in app_cfg.package_preseeding_values.items():
                if pkg_name in relevant_packages:
                    preseed_data_to_output[pkg_name] = preseed_values

            # Add placeholder comments for packages that don't have preseed data
            missing_packages = [
                pkg
                for pkg in relevant_packages
                if pkg not in app_cfg.package_preseeding_values
            ]
            if missing_packages:
                log_map_server(
                    f"{symbols.get('info', 'ℹ️')} Adding placeholder comments for packages without preseed data: {', '.join(sorted(missing_packages))}",
                    "info",
                    logger_to_use,
                    app_cfg,
                )
                # We'll add these as comments in the YAML output
        else:
            log_map_server(
                f"{symbols.get('warning', '!')} No packages found for specified tasks: {', '.join(specific_tasks)}",
                "warning",
                logger_to_use,
                app_cfg,
            )
    else:
        # Original logic for when no specific tasks are provided to --generate-preseed-yaml
        # Determine if any task-related flags were passed
        user_requested_specific_tasks = False
        if (
            parsed_args.full
            or parsed_args.run_all_core_prerequisites
            or parsed_args.ufw
            or parsed_args.postgres
            or parsed_args.pgtileserv
            or parsed_args.carto
            or parsed_args.renderd
            or parsed_args.osrm
            or parsed_args.apache
            or parsed_args.nginx
            or parsed_args.certbot
            or parsed_args.gtfs_prep
            or parsed_args.raster_prep
            or parsed_args.website_setup
            or parsed_args.services
            or parsed_args.data
        ):
            user_requested_specific_tasks = True

        relevant_packages = get_packages_for_tasks(parsed_args, app_cfg)

        if user_requested_specific_tasks and relevant_packages:
            log_map_server(
                f"{symbols.get('info', 'ℹ️')} Generating preseed values relevant to specified tasks for packages: {', '.join(sorted(list(relevant_packages)))}",
                "info",
                logger_to_use,
                app_cfg,
            )
            for (
                pkg_name,
                preseed_values,
            ) in app_cfg.package_preseeding_values.items():
                if pkg_name in relevant_packages:
                    preseed_data_to_output[pkg_name] = preseed_values
        else:
            log_map_server(
                f"{symbols.get('info', 'ℹ️')} No specific tasks implying preseedable packages were requested, or no relevant packages found for tasks. Generating all known default preseed values.",
                "info",
                logger_to_use,
                app_cfg,
            )
            preseed_data_to_output = app_cfg.package_preseeding_values

    if not preseed_data_to_output:
        log_map_server(
            f"{symbols.get('warning', '!')} No preseed data to output. Either no relevant packages for specified tasks, or no default preseed data defined.",
            "warning",
            logger_to_use,
            app_cfg,
        )
    else:
        # Prepare the YAML output
        output_data = {"package_preseeding_values": preseed_data_to_output}

        # Add placeholder comments for missing packages
        if "missing_packages" in locals() and missing_packages:
            print("\n--- Start of Suggested Preseed YAML ---")
            yaml.dump(
                output_data,
                sys.stdout,
                indent=2,
                sort_keys=False,
                default_flow_style=False,
            )
            print("--- End of Suggested Preseed YAML ---")

            # Print placeholder comments for packages without preseed data
            print(
                "\n# Packages without preseed data (consider adding if needed):"
            )
            for pkg in sorted(missing_packages):
                print(
                    f"# {pkg}: # TODO: Part of selected tasks. Investigate and add preseed data if needed."
                )
        else:
            print("\n--- Start of Suggested Preseed YAML ---")
            yaml.dump(
                output_data,
                sys.stdout,
                indent=2,
                sort_keys=False,
                default_flow_style=False,
            )
            print("--- End of Suggested Preseed YAML ---")

        print(
            "\n# Instructions: Review and copy the 'package_preseeding_values' section",
            file=sys.stderr,
        )
        print(
            "# (including the key itself) into your config.yaml to apply these preseed values.",
            file=sys.stderr,
        )
        print(
            "# Only uncomment or include the packages and settings you wish to preseed.",
            file=sys.stderr,
        )


def main_map_server_entry(cli_args_list: Optional[List[str]] = None) -> int:
    global APP_CONFIG
    parser = argparse.ArgumentParser(
        description="Map Server Installer Script",
        epilog="Example: python3 ./installer/main_installer.py --full -v mymap.example.com",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=False,
    )
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help="Show this help message and exit.",
    )
    parser.add_argument(
        "--generate-preseed-yaml",
        nargs="*",
        metavar="TASK_OR_GROUP",
        help="Generate package preseeding data as YAML and exit. Without arguments, shows all default preseed values. "
        "With specific task/group names (e.g., 'postgres', 'core_prereqs'), filters output to only show "
        "preseed data relevant to those tasks. Will include placeholder comments for packages without preseed data.",
    )
    parser.add_argument(
        "--full", action="store_true", help="Run full installation process."
    )
    parser.add_argument(
        "--view-config",
        action="store_true",
        help="View current configuration settings and exit.",
    )
    parser.add_argument(
        "--view-state",
        action="store_true",
        help="View completed installation steps and exit.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="View completed installation steps and exit.",
    )
    parser.add_argument(
        "--clear-state",
        action="store_true",
        help="Clear all progress state and exit.",
    )
    parser.add_argument(
        "--config-file",
        default="config.yaml",
        help="Path to YAML configuration file (default: config.yaml).",
    )
    config_group = parser.add_argument_group(
        "Configuration Overrides (CLI > YAML > ENV > Defaults)"
    )
    config_group.add_argument(
        "-a",
        "--admin-group-ip",
        default=None,
        help=f"Admin IP (CIDR). Default: {ADMIN_GROUP_IP_DEFAULT}",
    )
    config_group.add_argument(
        "-f",
        "--gtfs-feed-url",
        default=None,
        help=f"GTFS URL. Default: {GTFS_FEED_URL_DEFAULT}",
    )
    config_group.add_argument(
        "-v",
        "--vm-ip-or-domain",
        default=None,
        help=f"Public IP/FQDN. Default: {VM_IP_OR_DOMAIN_DEFAULT}",
    )
    config_group.add_argument(
        "-b",
        "--pg-tileserv-binary-location",
        default=None,
        help=f"pg_tileserv URL. Default: {PG_TILESERV_BINARY_LOCATION_DEFAULT}",
    )
    config_group.add_argument(
        "-l",
        "--log-prefix",
        default=None,
        help=f"Log prefix. Default: {LOG_PREFIX_DEFAULT}",
    )
    config_group.add_argument(
        "--container-runtime-command",
        default=None,
        help=f"Container runtime. Default: {CONTAINER_RUNTIME_COMMAND_DEFAULT}",
    )
    config_group.add_argument(
        "--osrm-image-tag",
        default=None,
        help=f"OSRM Docker image. Default: {OSRM_IMAGE_TAG_DEFAULT}",
    )
    config_group.add_argument(
        "--apache-listen-port",
        type=int,
        default=None,
        help=f"Apache listen port. Default: {APACHE_LISTEN_PORT_DEFAULT}",
    )
    pg_group = parser.add_argument_group("PostgreSQL Overrides")
    pg_group.add_argument(
        "-H",
        "--pghost",
        default=None,
        help=f"Host. Default: {PGHOST_DEFAULT}",
    )
    pg_group.add_argument(
        "-P",
        "--pgport",
        default=None,
        type=int,
        help=f"Port. Default: {PGPORT_DEFAULT}",
    )
    pg_group.add_argument(
        "-D",
        "--pgdatabase",
        default=None,
        help=f"Database. Default: {PGDATABASE_DEFAULT}",
    )
    pg_group.add_argument(
        "-U",
        "--pguser",
        default=None,
        help=f"User. Default: {PGUSER_DEFAULT}",
    )
    pg_group.add_argument(
        "-W", "--pgpassword", default=None, help="Password."
    )

    task_flags_definitions: List[Tuple[str, str, str]] = [
        (
            "boot_verbosity",
            PREREQ_BOOT_VERBOSITY_TAG,
            "Boot verbosity setup.",
        ),
        (
            "core_conflicts",
            PREREQ_CORE_CONFLICTS_TAG,
            "Core conflict removal.",
        ),
        ("docker_install", PREREQ_DOCKER_ENGINE_TAG, "Docker installation."),
        ("nodejs_install", PREREQ_NODEJS_LTS_TAG, "Node.js installation."),
        ("ufw_pkg_check", UFW_PACKAGE_CHECK_TAG, "UFW Package Check."),
        ("ufw_rules", CONFIG_UFW_RULES, "Configure UFW Rules."),
        ("ufw_activate", UFW_ACTIVATE_SERVICE_TAG, "Activate UFW Service."),
        ("ufw", UFW_FULL_SETUP, "UFW full setup."),
        ("postgres", POSTGRES_FULL_SETUP, "PostgreSQL full setup."),
        ("carto", CARTO_FULL_SETUP, "Carto full setup."),
        ("renderd", RENDERD_FULL_SETUP, "Renderd full setup."),
        ("apache", APACHE_FULL_SETUP, "Apache & mod_tile full setup."),
        ("nginx", NGINX_FULL_SETUP, "Nginx full setup."),
        ("certbot", CERTBOT_FULL_SETUP, "Certbot full setup."),
        ("pgtileserv", PGTILESERV_FULL_SETUP, "pg_tileserv full setup."),
        ("osrm", OSRM_FULL_SETUP, "OSRM full setup & data processing."),
        ("gtfs_prep", GTFS_PROCESS_AND_SETUP_TAG, "Full GTFS Pipeline."),
        ("raster_prep", RASTER_PREP_TAG, "Raster tile pre-rendering."),
        ("website_setup", WEBSITE_CONTENT_DEPLOY_TAG, "Deploy test website."),
        (
            "task_systemd_reload",
            SYSTEMD_RELOAD_TASK_TAG,
            "Systemd reload task.",
        ),
    ]
    task_group = parser.add_argument_group("Individual Task Flags")
    for dest_name, task_tag_const, base_desc in task_flags_definitions:
        task_group.add_argument(
            f"--{dest_name.replace('_', '-')}",
            action="store_true",
            dest=dest_name,
            help=get_dynamic_help(base_desc, task_tag_const),
        )
    prereqs_help_detail = "Run 'Comprehensive Prerequisites' group. Includes: --boot-verbosity, --core-conflicts, --docker-install, --nodejs-install, and setup for essential utilities, Python, PostgreSQL, mapping & font packages, and unattended upgrades."
    service_orchestrator_flags = [
        f"--{key.replace('_', '-')}"
        for key in [
            "ufw",
            "postgres",
            "pgtileserv",
            "carto",
            "renderd",
            "osrm",
            "apache",
            "nginx",
            "certbot",
            "website-setup",
        ]
    ]
    services_help_detail = (
        "Run setup for ALL services. Includes: "
        + ", ".join(service_orchestrator_flags)
        + ", and a final systemd reload."
    )
    data_help_detail = "Run all data preparation tasks. Includes: --gtfs-prep (Full GTFS Pipeline) and --raster-prep (Raster tile pre-rendering)."
    group_flags_grp = parser.add_argument_group("Group Task Flags")
    group_flags_grp.add_argument(
        "--prereqs",
        dest="run_all_core_prerequisites",
        action="store_true",
        help=prereqs_help_detail,
    )
    group_flags_grp.add_argument(
        "--services", action="store_true", help=services_help_detail
    )
    group_flags_grp.add_argument(
        "--data", action="store_true", help=data_help_detail
    )
    group_flags_grp.add_argument(
        "--systemd-reload",
        dest="group_systemd_reload_flag",
        action="store_true",
        help="Run systemd reload task (as a group action). Same as --task-systemd-reload.",
    )
    dev_grp = parser.add_argument_group("Developer Options")
    dev_grp.add_argument(
        "--dev-override-all-settings",
        action="store_true",
        dest="dev_override_unsafe_password",
        help="Override safety checks for development environments. Allows use of default/unsafe passwords and automatically sets vm_ip_or_domain to the primary IP address if it's set to 'example.com'.",
    )

    parsed_cli_args = parser.parse_args(
        cli_args_list if cli_args_list is not None else sys.argv[1:]
    )
    try:
        APP_CONFIG = load_app_settings(
            parsed_cli_args, parsed_cli_args.config_file
        )

        if APP_CONFIG.vm_ip_or_domain == VM_IP_OR_DOMAIN_DEFAULT:
            if not APP_CONFIG.dev_override_unsafe_password:
                log_map_server(
                    f"{APP_CONFIG.symbols.get('error', '❌')} vm_ip_or_domain is set to '{VM_IP_OR_DOMAIN_DEFAULT}'. "
                    f"This is unsafe for production use. Please set a proper domain or IP address, "
                    f"or use --dev-override-all-settings for development environments.",
                    "critical",
                    current_logger=logger,
                    app_settings=APP_CONFIG,
                )
                return 1
            else:
                primary_ip = get_primary_ip_address(APP_CONFIG, logger)
                if primary_ip:
                    APP_CONFIG.vm_ip_or_domain = primary_ip
                    log_map_server(
                        f"{APP_CONFIG.symbols.get('info', 'ℹ️')} vm_ip_or_domain was '{VM_IP_OR_DOMAIN_DEFAULT}' but --dev-override-all-settings "
                        f"was specified. Using primary IP address: {primary_ip}",
                        "info",
                        current_logger=logger,
                        app_settings=APP_CONFIG,
                    )
                else:
                    log_map_server(
                        f"{APP_CONFIG.symbols.get('error', '❌')} Could not determine primary IP address to replace '{VM_IP_OR_DOMAIN_DEFAULT}'. "
                        f"Please set vm_ip_or_domain manually.",
                        "critical",
                        current_logger=logger,
                        app_settings=APP_CONFIG,
                    )
                    return 1
    except SystemExit as e:  # pragma: no cover
        print(
            f"CRITICAL: Failed to load or validate application configuration: {e}",
            file=sys.stderr,
        )
        return 1

    common_setup_logging(
        log_level=logging.INFO,
        log_to_console=True,
        log_prefix=APP_CONFIG.log_prefix,
    )
    logger.info(
        f"Successfully loaded and validated configuration. Log prefix: {APP_CONFIG.log_prefix}"
    )

    # Handle --generate-preseed-yaml if present
    if (
        parsed_cli_args.generate_preseed_yaml is not None
    ):  # Check if the argument exists, not if it's True
        logger.info(
            f"{APP_CONFIG.symbols.get('yaml', '📜')} Generating preseed YAML based on specified tasks or defaults..."
        )
        # PyYAML is needed here, ensure it's a project dependency
        try:
            import yaml  # noqa: F401
        except ImportError:  # pragma: no cover
            logger.critical(
                f"{APP_CONFIG.symbols.get('error', '❌')} PyYAML is not installed. Cannot generate preseed YAML. Please add 'PyYAML' to your project dependencies."
            )
            return 1

        # Pass the list of specified tasks/groups to the function
        generate_preseed_yaml_for_tasks(APP_CONFIG, parsed_cli_args, logger)
        return 0  # Exit after generating YAML

    log_map_server(
        message=f"{APP_CONFIG.symbols.get('sparkles', '✨')} Map Server Setup (v{static_config.SCRIPT_VERSION}) HASH:{get_current_script_hash(static_config.OSM_PROJECT_ROOT, APP_CONFIG, logger) or 'N/A'} ...",
        level="info",
        current_logger=logger,
        app_settings=APP_CONFIG,
    )
    if (
        APP_CONFIG.pg.password == PGPASSWORD_DEFAULT
        and not parsed_cli_args.view_config
        and not APP_CONFIG.dev_override_unsafe_password
    ):
        log_map_server(
            message=f"{APP_CONFIG.symbols.get('warning', '⚠️')} WARNING: Default PostgreSQL password in use.",
            level="warning",
            current_logger=logger,
            app_settings=APP_CONFIG,
        )
    if os.geteuid() != 0:
        log_map_server(
            message=f"{APP_CONFIG.symbols.get('info', 'ℹ️')} Script not root. 'sudo' will be used.",
            level="info",
            current_logger=logger,
            app_settings=APP_CONFIG,
        )
    else:
        log_map_server(
            message=f"{APP_CONFIG.symbols.get('info', 'ℹ️')} Script is root.",
            level="info",
            current_logger=logger,
            app_settings=APP_CONFIG,
        )

    initialize_state_system(APP_CONFIG, logger)
    setup_pgpass(APP_CONFIG, logger)

    if parsed_cli_args.view_config:
        view_configuration(APP_CONFIG, logger)
        return 0
    if parsed_cli_args.view_state or parsed_cli_args.status:
        completed = view_completed_steps(APP_CONFIG, logger)
        log_map_server(
            message=f"{APP_CONFIG.symbols.get('info', 'ℹ️')} Completed steps from {static_config.STATE_FILE_PATH}:",
            level="info",
            current_logger=logger,
            app_settings=APP_CONFIG,
        )
        if completed:
            for i, s_item in enumerate(completed):
                print(f"  {i + 1}. {s_item}")
        else:
            log_map_server(
                message=f"{APP_CONFIG.symbols.get('info', 'ℹ️')} No steps completed.",
                level="info",
                current_logger=logger,
                app_settings=APP_CONFIG,
            )
        return 0
    if parsed_cli_args.clear_state:  # pragma: no cover
        if cli_prompt_for_rerun(
            f"Clear state from {static_config.STATE_FILE_PATH}?",
            APP_CONFIG,
            logger,
        ):
            h = get_current_script_hash(
                static_config.OSM_PROJECT_ROOT, APP_CONFIG, logger
            )
            clear_state_file(
                app_settings=APP_CONFIG,
                script_hash_to_write=h,
                current_logger=logger,
            )
        else:
            log_map_server(
                message=f"{APP_CONFIG.symbols.get('info', 'ℹ️')} State clearing cancelled.",
                level="info",
                current_logger=logger,
                app_settings=APP_CONFIG,
            )
        return 0

    # ... (rest of your main_map_server_entry logic for executing tasks) ...
    defined_tasks_callable_map: Dict[str, StepExecutorFunc] = {
        "boot_verbosity": prereq_boot_verbosity,
        "core_conflicts": core_conflict_removal,
        "docker_install": install_docker_engine,
        "nodejs_install": install_nodejs_lts,
        "run_all_core_prerequisites": _wrapped_core_prerequisites_group,
        "ufw_pkg_check": ensure_ufw_package_installed,
        "ufw_rules": apply_ufw_rules,
        "ufw_activate": activate_ufw_service,
        "ufw": ufw_full_setup_sequence,
        "postgres": postgres_full_setup_sequence,
        "carto": carto_full_setup_sequence,
        "renderd": renderd_full_setup_sequence,
        "apache": apache_full_setup_sequence,
        "nginx": nginx_full_setup_sequence,
        "certbot": certbot_full_setup_sequence,
        "pgtileserv": pg_tileserv_full_setup_sequence,
        "osrm": osrm_full_setup_sequence,
        "gtfs_prep": run_full_gtfs_module_wrapper,
        "raster_prep": raster_tile_prerender,
        "website_setup": deploy_test_website_content,
        "task_systemd_reload": systemd_reload,
    }
    cli_flag_to_task_details: Dict[str, Tuple[str, str]] = {
        item[0]: (item[1], item[2]) for item in task_flags_definitions
    }
    cli_flag_to_task_details.update({
        "run_all_core_prerequisites": (
            ALL_CORE_PREREQUISITES_GROUP_TAG,
            "Comprehensive Prerequisites",
        ),
        "ufw": (UFW_FULL_SETUP, "UFW Full Setup"),
        "postgres": (POSTGRES_FULL_SETUP, "PostgreSQL Full Setup"),
        "carto": (CARTO_FULL_SETUP, "Carto Full Setup"),
        "renderd": (RENDERD_FULL_SETUP, "Renderd Full Setup"),
        "apache": (APACHE_FULL_SETUP, "Apache Full Setup"),
        "nginx": (NGINX_FULL_SETUP, "Nginx Full Setup"),
        "certbot": (CERTBOT_FULL_SETUP, "Certbot Full Setup"),
        "pgtileserv": (PGTILESERV_FULL_SETUP, "pg_tileserv Full Setup"),
        "osrm": (OSRM_FULL_SETUP, "OSRM Full Setup"),
        "website_setup": (WEBSITE_CONTENT_DEPLOY_TAG, "Deploy test website"),
    })

    overall_success = True
    action_taken = False
    tasks_to_run: List[Dict[str, Any]] = []
    for arg_dest_name, was_flag_set in vars(parsed_cli_args).items():
        if (
            was_flag_set
            and arg_dest_name in defined_tasks_callable_map
            and arg_dest_name in cli_flag_to_task_details
        ):
            action_taken = True
            task_tag, task_desc = cli_flag_to_task_details[arg_dest_name]
            step_func = defined_tasks_callable_map[arg_dest_name]
            if not any(t["tag"] == task_tag for t in tasks_to_run):
                tasks_to_run.append({
                    "tag": task_tag,
                    "desc": task_desc,
                    "func": step_func,
                })
    if parsed_cli_args.run_all_core_prerequisites and not any(
        t["tag"] == ALL_CORE_PREREQUISITES_GROUP_TAG for t in tasks_to_run
    ):
        action_taken = True
        tag, desc = cli_flag_to_task_details["run_all_core_prerequisites"]
        func = defined_tasks_callable_map["run_all_core_prerequisites"]
        tasks_to_run.insert(0, {"tag": tag, "desc": desc, "func": func})
    if tasks_to_run:

        def get_sort_key(task_item: Dict[str, Any]) -> Tuple[int, int]:
            task_tag = task_item["tag"]
            details = task_execution_details_lookup.get(task_tag)
            if details:
                group_name, step_index_in_group = details
                group_main_order = group_order_lookup.get(
                    group_name, sys.maxsize
                )
                return (group_main_order, step_index_in_group)
            return (sys.maxsize, 0)

        tasks_to_run.sort(key=get_sort_key)
        log_map_server(
            message=f"{APP_CONFIG.symbols.get('rocket', '🚀')} Running Specified Tasks/Groups (Sorted by Execution Order)",
            level="info",
            current_logger=logger,
            app_settings=APP_CONFIG,
        )
        for task in tasks_to_run:
            if not overall_success:
                log_map_server(
                    message=f"Skipping '{task['desc']}' due to prior failure.",
                    level="warning",
                    current_logger=logger,
                    app_settings=APP_CONFIG,
                )
                continue
            if not execute_step(
                task["tag"],
                task["desc"],
                task["func"],
                APP_CONFIG,
                logger,
                cli_prompt_for_rerun,
            ):
                overall_success = False
    elif parsed_cli_args.full:
        action_taken = True
        log_map_server(
            message=f"{APP_CONFIG.symbols.get('rocket', '🚀')} Starting Full Installation",
            level="info",
            current_logger=logger,
            app_settings=APP_CONFIG,
        )
        full_install_phases: List[Tuple[str, str, StepExecutorFunc]] = [
            (
                ALL_CORE_PREREQUISITES_GROUP_TAG,
                "Comprehensive Prerequisites",
                _wrapped_core_prerequisites_group,
            ),
            (UFW_FULL_SETUP, "UFW Full Setup", ufw_full_setup_sequence),
            (
                POSTGRES_FULL_SETUP,
                "PostgreSQL Full Setup",
                postgres_full_setup_sequence,
            ),
            (
                PGTILESERV_FULL_SETUP,
                "pg_tileserv Full Setup",
                pg_tileserv_full_setup_sequence,
            ),
            (CARTO_FULL_SETUP, "Carto Full Setup", carto_full_setup_sequence),
            (
                RENDERD_FULL_SETUP,
                "Renderd Full Setup",
                renderd_full_setup_sequence,
            ),
            (
                OSRM_FULL_SETUP,
                "OSRM Full Setup & Data Processing",
                osrm_full_setup_sequence,
            ),
            (
                APACHE_FULL_SETUP,
                "Apache Full Setup",
                apache_full_setup_sequence,
            ),
            (NGINX_FULL_SETUP, "Nginx Full Setup", nginx_full_setup_sequence),
            (
                CERTBOT_FULL_SETUP,
                "Certbot Full Setup",
                certbot_full_setup_sequence,
            ),
            (
                WEBSITE_CONTENT_DEPLOY_TAG,
                "Deploy Website Content",
                deploy_test_website_content,
            ),
            (
                GTFS_PROCESS_AND_SETUP_TAG,
                "GTFS Data Pipeline",
                run_full_gtfs_module_wrapper,
            ),
            (
                RASTER_PREP_TAG,
                "Raster Tile Pre-rendering",
                raster_tile_prerender,
            ),
            (
                SYSTEMD_RELOAD_TASK_TAG,
                "Systemd Reload After All Services",
                _wrapped_systemd_reload_step_group,
            ),
        ]
        for tag, desc, phase_func in full_install_phases:
            if not overall_success:
                log_map_server(
                    message=f"Skipping '{desc}' due to prior failure.",
                    level="warning",
                    current_logger=logger,
                    app_settings=APP_CONFIG,
                )
                continue
            log_map_server(
                message=f"--- Executing: {desc} ({tag}) ---",
                level="info",
                current_logger=logger,
                app_settings=APP_CONFIG,
            )
            if not execute_step(
                tag,
                desc,
                phase_func,
                APP_CONFIG,
                logger,
                cli_prompt_for_rerun,
            ):
                overall_success = False
                log_map_server(
                    message=f"Phase '{desc}' failed.",
                    level="error",
                    current_logger=logger,
                    app_settings=APP_CONFIG,
                )
                break
    elif parsed_cli_args.services:  # pragma: no cover
        action_taken = True
        log_map_server(
            message=f"{APP_CONFIG.symbols.get('rocket', '🚀')} Running All Service Setups",
            level="info",
            current_logger=logger,
            app_settings=APP_CONFIG,
        )
        service_orchestrator_cli_keys = [
            "ufw",
            "postgres",
            "pgtileserv",
            "carto",
            "renderd",
            "osrm",
            "apache",
            "nginx",
            "certbot",
            "website_setup",
        ]
        for key in service_orchestrator_cli_keys:
            if not overall_success:
                break
            if key not in cli_flag_to_task_details:
                logger.error(
                    f"Developer error: Key '{key}' for services group not found in cli_flag_to_task_details."
                )
                overall_success = False
                break
            tag, desc = cli_flag_to_task_details[key]
            if key not in defined_tasks_callable_map:
                logger.error(
                    f"Developer error: Key '{key}' for services group not found in defined_tasks_callable_map."
                )
                overall_success = False
                break
            func = defined_tasks_callable_map[key]
            if not execute_step(
                tag, desc, func, APP_CONFIG, logger, cli_prompt_for_rerun
            ):
                overall_success = False
        if overall_success:
            if not execute_step(
                SYSTEMD_RELOAD_TASK_TAG,
                "Systemd Reload After Services",
                _wrapped_systemd_reload_step_group,
                APP_CONFIG,
                logger,
                cli_prompt_for_rerun,
            ):
                overall_success = False
    elif parsed_cli_args.data:  # pragma: no cover
        action_taken = True
        log_map_server(
            message=f"{APP_CONFIG.symbols.get('rocket', '🚀')} Running Data Tasks (via data_prep_group)",
            level="info",
            current_logger=logger,
            app_settings=APP_CONFIG,
        )
        if not execute_step(
            "DATAPROC_GROUP_MAIN",
            "Data Preparation Group",
            _wrapped_data_prep_group,
            APP_CONFIG,
            logger,
            cli_prompt_for_rerun,
        ):
            overall_success = False
    elif parsed_cli_args.group_systemd_reload_flag:  # pragma: no cover
        action_taken = True
        if not execute_step(
            SYSTEMD_RELOAD_TASK_TAG,
            "Systemd Reload (Group CLI Flag)",
            _wrapped_systemd_reload_step_group,
            APP_CONFIG,
            logger,
            cli_prompt_for_rerun,
        ):
            overall_success = False

    if not action_taken and not (
        parsed_cli_args.view_config
        or parsed_cli_args.view_state
        or parsed_cli_args.clear_state
        or parsed_cli_args.generate_preseed_yaml
    ):  # Added generate_preseed_yaml here
        log_map_server(
            message=f"{APP_CONFIG.symbols.get('info', 'ℹ️')} No action specified. Displaying help.",
            level="info",
            current_logger=logger,
            app_settings=APP_CONFIG,
        )
        parser.print_help(sys.stderr)
        return 2
    if not action_taken and not (
        parsed_cli_args.view_config
        or parsed_cli_args.view_state
        or parsed_cli_args.clear_state
        or parsed_cli_args.generate_preseed_yaml is not None
    ):
        log_map_server(
            message=f"{APP_CONFIG.symbols.get('info', 'ℹ️')} No action specified. Displaying help.",
            level="info",
            current_logger=logger,
            app_settings=APP_CONFIG,
        )
        parser.print_help(sys.stderr)
        return 2

    if not overall_success:
        log_map_server(
            message=f"{APP_CONFIG.symbols.get('critical', '🔥')} One or more steps failed.",
            level="critical",
            current_logger=logger,
            app_settings=APP_CONFIG,
        )
        return 1
    if (
        action_taken
        or parsed_cli_args.view_config
        or parsed_cli_args.view_state
        or parsed_cli_args.clear_state
        or parsed_cli_args.generate_preseed_yaml is not None
    ):
        log_map_server(
            message=f"{APP_CONFIG.symbols.get('sparkles', '✨')} Operation(s) completed.",
            level="success",
            current_logger=logger,
            app_settings=APP_CONFIG,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main_map_server_entry())
