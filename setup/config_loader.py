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
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml  # PyYAML - ensure this is in dependencies

# Assuming your Pydantic models are in setup.config_models
# Adjust import if structure is different
from .config_models import AppSettings, PostgresSettings


def _deep_update(source: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deeply updates a dictionary with values from another dictionary.
    'overrides' take precedence. Values from `overrides` that are None are ignored,
    unless the corresponding key does not exist in `source`.
    """
    for key, value in overrides.items():
        if isinstance(value, dict) and key in source and isinstance(source[key], dict):
            source[key] = _deep_update(source[key], value)
        elif value is not None:  # Only update if the override value is not None
            source[key] = value
        elif key not in source and value is None:  # If key is new and value is None, add it
            source[key] = value
    return source


def load_app_settings(
        cli_args: Optional[argparse.Namespace] = None,
        config_file_path: str = "config.yaml",
) -> AppSettings:
    """
    Loads application settings with the following precedence:
    1. Pydantic Model Defaults.
    2. Values from YAML configuration file (overrides defaults).
    3. Environment Variables (Pydantic BaseSettings loads these; values from YAML for the
       same fields will generally take precedence if both are specified, depending on how
       BaseSettings merges __init__ kwargs with ENV).
       To be precise: Pydantic BaseSettings loads ENV, then we override with YAML, then with CLI.
    4. Command-Line Arguments (highest precedence, overrides all else).

    Args:
        cli_args: Parsed command-line arguments (from argparse).
        config_file_path: Path to the YAML configuration file.

    Returns:
        An instance of AppSettings with the fully resolved configuration.
    """

    # 1. Start with Pydantic defaults.
    #    BaseSettings also loads from actual environment variables and .env files here.
    #    So, `settings_after_env_and_defaults` now holds: Model Defaults < .env file < Environment Variables
    settings_after_env_and_defaults = AppSettings()
    current_values_dict = settings_after_env_and_defaults.model_dump(exclude_defaults=False)

    # 2. Override with values from YAML configuration file.
    #    YAML values will override anything loaded from defaults or environment variables up to this point.
    yaml_config_path = Path(config_file_path)
    if yaml_config_path.exists() and yaml_config_path.is_file():
        try:
            with open(yaml_config_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)
            if yaml_data and isinstance(yaml_data, dict):
                current_values_dict = _deep_update(current_values_dict, yaml_data)
            elif yaml_data is not None:
                print(
                    f"Warning: Config file '{yaml_config_path}' does not contain a valid YAML dictionary. Ignoring.",
                    file=sys.stderr,
                )
        except yaml.YAMLError as e:
            print(
                f"Warning: Could not parse YAML config file '{yaml_config_path}': {e}. Using defaults and environment variables.",
                file=sys.stderr,
            )
        except IOError as e:
            print(
                f"Warning: Could not read config file '{yaml_config_path}': {e}. Using defaults and environment variables.",
                file=sys.stderr,
            )
    else:
        print(
            f"Info: Configuration file '{yaml_config_path}' not found. Using defaults, environment variables, and CLI args.",
            file=sys.stderr)

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
                mapped_cli_values["gtfs_feed_url"] = str(cli_value)  # Ensure HttpUrl can parse
            elif cli_key == "vm_ip_or_domain":
                mapped_cli_values["vm_ip_or_domain"] = cli_value
            elif cli_key == "pg_tileserv_binary_location":
                mapped_cli_values["pg_tileserv_binary_location"] = str(cli_value)
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
                pg_cli_values["port"] = int(cli_value)  # argparse might give str
            elif cli_key == "pgdatabase":
                pg_cli_values["database"] = cli_value
            elif cli_key == "pguser":
                pg_cli_values["user"] = cli_value
            elif cli_key == "pgpassword":
                pg_cli_values["password"] = cli_value
            # Add other CLI args to AppSettings field mappings here if necessary

        if pg_cli_values:
            if "pg" not in current_values_dict or not isinstance(current_values_dict["pg"], dict):
                current_values_dict["pg"] = {}  # Initialize if not present
            current_values_dict["pg"] = _deep_update(current_values_dict["pg"], pg_cli_values)

        current_values_dict = _deep_update(current_values_dict, mapped_cli_values)

    # 4. Create the final AppSettings instance, which will also validate all values.
    try:
        final_settings = AppSettings(**current_values_dict)
    except Exception as e:  # Catch Pydantic validation errors etc.
        print(f"Error: Configuration validation failed: {e}", file=sys.stderr)
        # Potentially exit or raise a more specific configuration error
        raise SystemExit(f"Configuration error: {e}")

    # Optional: Log the final configuration source for sensitive fields like password
    # For example, log if password came from env, file, or default, without logging the password itself.
    # This can be complex to trace perfectly without more involved logic.

    return final_settings