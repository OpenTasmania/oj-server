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

import yaml

from common.constants_loader import get_constant

from .config_models import AppSettings

module_logger = logging.getLogger(__name__)

CONFIG_DIR = "config_files"


def _deep_update(
    source: Dict[str, Any], overrides: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Recursively updates a dictionary `source` with values from another dictionary
    `overrides`. If a key exists in both dictionaries and its corresponding value
    is a dictionary, the function updates the nested dictionary recursively.
    Otherwise, it replaces or adds the value for the key in the `source` with the
    value from `overrides`.

    Parameters:
        source: Dict[str, Any]
            The dictionary to be updated. This dictionary gets modified in place.
        overrides: Dict[str, Any]
            The dictionary containing values to update or add to the `source`.

    Returns:
        Dict[str, Any]:
            The updated dictionary after applying all `overrides` to the input `source`.
    """
    for key, value in overrides.items():
        if (
            isinstance(value, dict)
            and key in source
            and isinstance(source[key], dict)
        ):
            source[key] = _deep_update(source[key], value)
        elif value is not None:
            source[key] = value
        elif (
            key not in source and value is None
        ):  # If key is new and value is None, add it
            source[key] = value
    return source


def _deep_merge_dicts(
    d1: Dict[str, Any], d2: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Recursively merges two dictionaries.

    This function takes two dictionaries and recursively merges the second dictionary
    into the first. If a certain key exists in both dictionaries and the values for
    that key are also dictionaries, it merges those sub-dictionaries. Otherwise, the
    value from the second dictionary will overwrite the value in the first.

    Parameters:
        d1: Dict[str, Any]
            The first dictionary to be merged. This dictionary will be modified in
            place with the merged values.
        d2: Dict[str, Any]
            The second dictionary to merge into the first dictionary.

    Returns:
        Dict[str, Any]: The resulting merged dictionary.
    """
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

    yaml_config_path = project_root / config_file_path
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
        service_config = load_service_config(
            service, project_root, config_file_path, logger_to_use
        )

        if service_config:
            if service in current_values_dict:
                if isinstance(
                    current_values_dict[service], dict
                ) and isinstance(service_config, dict):
                    current_values_dict[service] = _deep_update(
                        current_values_dict[service], service_config
                    )
                else:
                    current_values_dict[service] = service_config
            else:
                current_values_dict[service] = service_config

    if cli_args:
        cli_arg_dict = vars(cli_args)

        mapped_cli_values: Dict[str, Any] = {}
        pg_cli_values: Dict[str, Any] = {}

        for cli_key, cli_value in cli_arg_dict.items():
            if cli_value is None:
                continue

            if cli_key == "admin_group_ip":
                mapped_cli_values["admin_group_ip"] = cli_value
            elif cli_key == "gtfs_feed_url":
                mapped_cli_values["gtfs_feed_url"] = str(cli_value)
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

            elif cli_key == "pghost":
                pg_cli_values["host"] = cli_value
            elif cli_key == "pgport":
                pg_cli_values["port"] = int(cli_value)
            elif cli_key == "pgdatabase":
                pg_cli_values["database"] = cli_value
            elif cli_key == "pguser":
                pg_cli_values["user"] = cli_value
            elif cli_key == "pgpassword":
                pg_cli_values["password"] = cli_value

        if pg_cli_values:
            if "pg" not in current_values_dict or not isinstance(
                current_values_dict["pg"], dict
            ):
                current_values_dict["pg"] = {}
            current_values_dict["pg"] = _deep_update(
                current_values_dict["pg"], pg_cli_values
            )

        current_values_dict = _deep_update(
            current_values_dict, mapped_cli_values
        )

    if "pgadmin" not in current_values_dict:
        current_values_dict["pgadmin"] = {}

    if "install" not in current_values_dict["pgadmin"]:
        current_values_dict["pgadmin"]["install"] = get_constant(
            "features.pgadmin_enabled", False
        )

    if "pgagent" not in current_values_dict:
        current_values_dict["pgagent"] = {}

    if "install" not in current_values_dict["pgagent"]:
        current_values_dict["pgagent"]["install"] = get_constant(
            "features.pgagent_enabled", False
        )

    try:
        final_settings = AppSettings(**current_values_dict)
    except Exception as e:  # Catch Pydantic validation errors etc.
        logger_to_use.error(f"Configuration validation failed: {e}")
        raise SystemExit(f"Configuration error: {e}") from e

    logger_to_use.info(
        "Successfully loaded and validated application settings"
    )

    return final_settings


def load_service_config(
    service_name: str,
    project_root: Path,
    main_config_path: str = "config.yaml",
    current_logger: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    """
    Loads the configuration for the given service either from a service-specific
    configuration file or from a section in the main configuration file. If neither
    exists or cannot be loaded, defaults or empty configurations may be returned.

    Args:
        service_name (str): Name of the service for which configuration is being loaded.
        project_root (Path): Path to the root of the project where configuration
            files are expected to be located.
        main_config_path (str, optional): Filename of the primary configuration file,
            default is 'config.yaml'.
        current_logger (logging.Logger, optional): Logger instance to use. If not provided,
            the module's logger is used.

    Returns:
        Dict[str, Any]: A dictionary containing the loaded configuration for the given service.
    """
    logger_to_use = current_logger if current_logger else module_logger

    config_dir_path = project_root / CONFIG_DIR
    service_config_path = config_dir_path / f"{service_name}.yaml"

    service_config: Dict[str, Any] = {}

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

    if not service_config:
        main_config_file_path = project_root / main_config_path
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
            logger_to_use.warning(  # Changed to warning as it might not be a fatal error if config is optional
                f"Main configuration file '{main_config_file_path}' not found."
            )

    return service_config


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
        raise FileNotFoundError(
            f"Configuration directory not found at: {config_path}"
        )

    config_files = sorted(config_path.glob("*.yaml"))

    for file_path in config_files:
        with open(file_path, "r") as f:
            try:
                single_config = yaml.safe_load(f)
                if single_config and isinstance(single_config, dict):
                    merged_config = _deep_merge_dicts(
                        merged_config, single_config
                    )
            except yaml.YAMLError as e:
                module_logger.error(
                    f"Error parsing YAML file {file_path}: {e}"
                )
                raise

    return merged_config


def is_feature_enabled(feature_name: str, default: bool = False) -> bool:
    """
    Check if a feature is enabled in the constants.

    Args:
        feature_name: The name of the feature to check
        default: Default value to return if the feature flag is not found

    Returns:
        True if the feature is enabled, False otherwise
    """
    result = get_constant(f"features.{feature_name}", default)
    return bool(result)


def get_task(task_name: str) -> Optional[Dict[str, Any]]:
    """
    Get a task by name.

    Args:
        task_name: The name of the task to get

    Returns:
        The task dictionary or None if not found
    """
    tasks = get_constant("tasks", {})
    if not isinstance(tasks, dict):
        return None
    return tasks.get(task_name)


def get_step(step_name: str) -> Optional[Dict[str, Any]]:
    """
    Get a step by name.

    Args:
        step_name: The name of the step to get

    Returns:
        The step dictionary or None if not found
    """
    steps = get_constant("steps", {})
    if not isinstance(steps, dict):
        return None
    return steps.get(step_name)


def is_task_enabled(task_name: str) -> bool:
    """
    Check if a task is enabled.

    Args:
        task_name: The name of the task to check

    Returns:
        True if the task is enabled, False otherwise
    """
    task = get_task(task_name)
    if task is None:
        module_logger.warning(f"Task '{task_name}' not found")
        return False

    enabled_value = task.get("enabled", False)
    return bool(enabled_value)
