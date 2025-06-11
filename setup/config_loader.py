# setup/config_loader.py
# -*- coding: utf-8 -*-
"""
Configuration loader for the application.

Handles loading settings from Pydantic model defaults, YAML files,
environment variables, and command-line arguments, applying a specific
order of precedence:
1. Pydantic Model Defaults
2. YAML Configuration File
3. Environment Variables (via Pydantic's BaseSettings initialization if not overridden by YAML)
4. Command-Line Arguments
"""

import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml  # PyYAML - ensure this is in dependencies

# Assuming your Pydantic models are in setup.config_models
# Adjust import if structure is different
from .config_models import AppSettings

module_logger = logging.getLogger(__name__)

CONFIG_DIR = "config_files"


def _deep_update(
    source: Dict[str, Any], overrides: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Deeply updates a dictionary with values from another dictionary.
    'overrides' take precedence. Values from `overrides` that are None are ignored,
    unless the corresponding key does not exist in `source`.
    """
    for key, value in overrides.items():
        if (
            isinstance(value, dict)
            and key in source
            and isinstance(source[key], dict)
        ):
            source[key] = _deep_update(source[key], value)
        elif (
            value is not None
        ):  # Only update if the override value is not None
            source[key] = value
        elif (
            key not in source and value is None
        ):  # If key is new and value is None, add it
            source[key] = value
    return source


def _deep_merge_dicts(
    d1: Dict[str, Any], d2: Dict[str, Any]
) -> Dict[str, Any]:
    """Recursively merges d2 into d1."""
    for k, v in d2.items():
        if k in d1 and isinstance(d1[k], dict) and isinstance(v, dict):
            d1[k] = _deep_merge_dicts(d1[k], v)
        else:
            d1[k] = v
    return d1


def load_app_settings(
    cli_args: Optional[argparse.Namespace] = None,
    config_file_path: str = "config.yaml",
    current_logger: Optional[logging.Logger] = None,
) -> AppSettings:
    """
    Loads application settings with the following precedence:
    1. Pydantic Model Defaults.
    2. Values from YAML configuration file (overrides defaults).
       - First looks for service-specific config files in /config_files
       - Falls back to sections in the main config.yaml if not found
    3. Environment Variables (Pydantic BaseSettings loads these; values from YAML for the
       same fields will generally take precedence if both are specified, depending on how
       BaseSettings merges __init__ kwargs with ENV).
       To be precise: Pydantic BaseSettings loads ENV, then we override with YAML, then with CLI.
    4. Command-Line Arguments (highest precedence, overrides all else).

    Args:
        cli_args: Parsed command-line arguments (from argparse).
        config_file_path: Path to the YAML configuration file.
        current_logger: Optional logger to use instead of the module logger.

    Returns:
        An instance of AppSettings with the fully resolved configuration.
    """
    logger_to_use = current_logger if current_logger else module_logger

    # 1. Start with Pydantic defaults.
    #    BaseSettings also loads from actual environment variables and .env files here.
    #    So, `settings_after_env_and_defaults` now holds: Model Defaults < .env file < Environment Variables
    settings_after_env_and_defaults = AppSettings()
    current_values_dict = settings_after_env_and_defaults.model_dump(
        exclude_defaults=False
    )

    # Get the project root path
    project_root = Path.cwd()
    if not (project_root / CONFIG_DIR).exists():
        # Try to find the project root by looking for the config_files directory
        parent_dir = project_root.parent
        while parent_dir != project_root:
            if (parent_dir / CONFIG_DIR).exists():
                project_root = parent_dir
                break
            project_root = parent_dir
            parent_dir = parent_dir.parent

    # 2. Override with values from YAML configuration files.
    #    First, load the main config file to get the base configuration.
    yaml_config_path = Path(config_file_path)
    if yaml_config_path.exists() and yaml_config_path.is_file():
        try:
            with open(yaml_config_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)
            if yaml_data and isinstance(yaml_data, dict):
                current_values_dict = _deep_update(
                    current_values_dict, yaml_data
                )
                logger_to_use.info(
                    f"Loaded main configuration from {yaml_config_path}"
                )
            elif yaml_data is not None:
                logger_to_use.warning(
                    f"Config file '{yaml_config_path}' does not contain a valid YAML dictionary. Ignoring."
                )
        except yaml.YAMLError as e:
            logger_to_use.warning(
                f"Could not parse YAML config file '{yaml_config_path}': {e}. Using defaults and environment variables."
            )
        except IOError as e:
            logger_to_use.warning(
                f"Could not read config file '{yaml_config_path}': {e}. Using defaults and environment variables."
            )
    else:
        logger_to_use.info(
            f"Configuration file '{yaml_config_path}' not found. Using defaults, environment variables, and CLI args."
        )

    # Now, try to load service-specific config files for each service
    # List of services to check for specific config files
    services = [
        "pg_tileserv",
        "postgres",
        "apache",
        "nginx",
        "osrm_service",
        "osrm_data",
        "renderd",
        "certbot",
        "webapp",
    ]

    for service in services:
        # Load service-specific config if available
        service_config = load_service_config(
            service, project_root, config_file_path, logger_to_use
        )

        if service_config:
            # If we have a service-specific config, update the current values
            if service in current_values_dict:
                # If the service key already exists in the main config, update it
                if isinstance(
                    current_values_dict[service], dict
                ) and isinstance(service_config, dict):
                    current_values_dict[service] = _deep_update(
                        current_values_dict[service], service_config
                    )
                else:
                    # If the service key exists but isn't a dict, or the service_config isn't a dict,
                    # replace it entirely
                    current_values_dict[service] = service_config
            else:
                # If the service key doesn't exist in the main config, add it
                current_values_dict[service] = service_config

    # 3. Override with Command-Line Arguments (highest precedence).
    if cli_args:
        cli_arg_dict = vars(cli_args)

        # Map CLI arguments to AppSettings fields.
        # This needs to be specific to how your argparse arguments are defined.
        mapped_cli_values: Dict[str, Any] = {}
        pg_cli_values: Dict[str, Any] = {}

        for cli_key, cli_value in cli_arg_dict.items():
            if cli_value is None:  # Skip args not provided by user
                continue

            # Top-level AppSettings fields
            if cli_key == "admin_group_ip":
                mapped_cli_values["admin_group_ip"] = cli_value
            elif cli_key == "gtfs_feed_url":
                mapped_cli_values["gtfs_feed_url"] = str(
                    cli_value
                )  # Ensure HttpUrl can parse
            elif cli_key == "vm_ip_or_domain":
                mapped_cli_values["vm_ip_or_domain"] = cli_value
            elif cli_key == "pg_tileserv_binary_location":
                mapped_cli_values["pg_tileserv_binary_location"] = str(
                    cli_value
                )
            elif cli_key == "log_prefix":
                mapped_cli_values["log_prefix"] = cli_value
            elif cli_key == "dev_override_unsafe_password":
                mapped_cli_values["dev_override_unsafe_password"] = cli_value
            elif cli_key == "container_runtime_command":
                mapped_cli_values["container_runtime_command"] = cli_value
            elif cli_key == "osrm_image_tag":
                mapped_cli_values["osrm_image_tag"] = cli_value

            # Nested PostgresSettings fields
            elif cli_key == "pghost":
                pg_cli_values["host"] = cli_value
            elif cli_key == "pgport":
                pg_cli_values["port"] = int(
                    cli_value
                )  # argparse might give str
            elif cli_key == "pgdatabase":
                pg_cli_values["database"] = cli_value
            elif cli_key == "pguser":
                pg_cli_values["user"] = cli_value
            elif cli_key == "pgpassword":
                pg_cli_values["password"] = cli_value
            # Add other CLI args to AppSettings field mappings here if necessary

        if pg_cli_values:
            if "pg" not in current_values_dict or not isinstance(
                current_values_dict["pg"], dict
            ):
                current_values_dict["pg"] = {}  # Initialize if not present
            current_values_dict["pg"] = _deep_update(
                current_values_dict["pg"], pg_cli_values
            )

        current_values_dict = _deep_update(
            current_values_dict, mapped_cli_values
        )

    # 4. Create the final AppSettings instance, which will also validate all values.
    try:
        final_settings = AppSettings(**current_values_dict)
    except Exception as e:  # Catch Pydantic validation errors etc.
        logger_to_use.error(f"Configuration validation failed: {e}")
        # Potentially exit or raise a more specific configuration error
        raise SystemExit(f"Configuration error: {e}") from e

    # Optional: Log the final configuration source for sensitive fields like password
    # For example, log if password came from env, file, or default, without logging the password itself.
    # This can be complex to trace perfectly without more involved logic.
    logger_to_use.info(
        "Successfully loaded and validated application settings"
    )

    return final_settings


def load_config_from_directory(project_root: Path) -> Dict[str, Any]:
    """
    Loads and merges all YAML configuration files from the config_files directory.

    Args:
        project_root: The root path of the project.

    Returns:
        A single dictionary containing the merged configuration.
    """
    config_path = project_root / CONFIG_DIR
    merged_config: Dict[str, Any] = {}

    if not config_path.is_dir():
        # Handle error: configuration directory not found
        raise FileNotFoundError(
            f"Configuration directory not found at: {config_path}"
        )

    # Sort files alphabetically to ensure a predictable merge order
    config_files = sorted(config_path.glob("*.yaml"))

    for file_path in config_files:
        with open(file_path, "r") as f:
            try:
                single_config = yaml.safe_load(f)
                if single_config and isinstance(single_config, dict):
                    # Use a deep merge to handle nested dictionaries correctly
                    merged_config = _deep_merge_dicts(
                        merged_config, single_config
                    )
            except yaml.YAMLError as e:
                # Handle YAML parsing errors
                module_logger.error(
                    f"Error parsing YAML file {file_path}: {e}"
                )
                raise

    return merged_config


def load_service_config(
    service_name: str,
    project_root: Path,
    main_config_path: str = "config.yaml",
    current_logger: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    """
    Loads configuration for a specific service. First looks for a service-specific
    config file in the config_files directory. If not found, falls back to the
    section in the main config.yaml file.

    Args:
        service_name: The name of the service to load configuration for.
        project_root: The root path of the project.
        main_config_path: Path to the main configuration file (default: "config.yaml").
        current_logger: Optional logger to use instead of the module logger.

    Returns:
        A dictionary containing the service configuration.
    """
    logger_to_use = current_logger if current_logger else module_logger

    # First, try to load from service-specific config file
    config_dir_path = project_root / CONFIG_DIR
    service_config_path = config_dir_path / f"{service_name}.yaml"

    service_config: Dict[str, Any] = {}

    # Check if service-specific config file exists
    if service_config_path.exists() and service_config_path.is_file():
        try:
            with open(service_config_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)

            if yaml_data and isinstance(yaml_data, dict):
                service_config = yaml_data
                logger_to_use.info(
                    f"Loaded configuration for {service_name} from {service_config_path}"
                )
            else:
                logger_to_use.warning(
                    f"Service config file '{service_config_path}' does not contain a valid YAML dictionary. "
                    f"Falling back to main config."
                )
        except yaml.YAMLError as e:
            logger_to_use.warning(
                f"Could not parse service config file '{service_config_path}': {e}. "
                f"Falling back to main config."
            )
        except IOError as e:
            logger_to_use.warning(
                f"Could not read service config file '{service_config_path}': {e}. "
                f"Falling back to main config."
            )
    else:
        logger_to_use.info(
            f"Service-specific config file for '{service_name}' not found at {service_config_path}. "
            f"Falling back to main config."
        )

    # If service config is empty or not found, try to load from main config
    if not service_config:
        main_config_file_path = Path(main_config_path)
        if main_config_file_path.exists() and main_config_file_path.is_file():
            try:
                with open(main_config_file_path, "r", encoding="utf-8") as f:
                    yaml_data = yaml.safe_load(f)

                if (
                    yaml_data
                    and isinstance(yaml_data, dict)
                    and service_name in yaml_data
                ):
                    service_config = yaml_data[service_name]
                    logger_to_use.info(
                        f"Loaded configuration for {service_name} from section in {main_config_file_path}"
                    )
                else:
                    logger_to_use.warning(
                        f"No configuration section for '{service_name}' found in {main_config_file_path}."
                    )
            except yaml.YAMLError as e:
                logger_to_use.error(
                    f"Could not parse main config file '{main_config_file_path}': {e}."
                )
                raise
            except IOError as e:
                logger_to_use.error(
                    f"Could not read main config file '{main_config_file_path}': {e}."
                )
                raise
        else:
            logger_to_use.error(
                f"Main configuration file '{main_config_file_path}' not found."
            )
            raise FileNotFoundError(
                f"Configuration file '{main_config_file_path}' not found."
            )

    return service_config
