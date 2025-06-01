# common/network_utils.py
# -*- coding: utf-8 -*-
"""
Network-related utility functions.
"""
import logging
import re
from typing import Optional

from setup.config_models import AppSettings
from .command_utils import log_map_server

module_logger = logging.getLogger(__name__)


def validate_cidr(
        cidr: str,
        app_settings: AppSettings,
        current_logger: Optional[logging.Logger] = None,
) -> bool:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols

    if not isinstance(cidr, str):
        log_map_server(
            f"{symbols.get('error', '❌')} Invalid input for CIDR validation: not a string.",
            "error",
            logger_to_use,
            app_settings,
        )
        return False

    # Regex for basic CIDR format xxx.xxx.xxx.xxx/yy
    match = re.fullmatch(
        r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$", cidr
    )
    if not match:
        log_map_server(
            f"{symbols.get('warning', '!')} CIDR '{cidr}' has invalid format.",
            "warning",
            logger_to_use,
            app_settings,
        )
        return False

    ip_part, prefix_str = cidr.split("/")
    try:
        prefix = int(prefix_str)
        if not (0 <= prefix <= 32):  # Validate prefix range
            log_map_server(
                f"{symbols.get('warning', '!')} CIDR prefix '/{prefix}' is out of range (0-32).",
                "warning",
                logger_to_use,
                app_settings,
            )
            return False

        octets_str = ip_part.split(".")
        if (
                len(octets_str) != 4
        ):  # Should be caught by regex, but good for robustness
            log_map_server(
                f"{symbols.get('warning', '!')} CIDR IP part '{ip_part}' does not have 4 octets.",
                "warning",
                logger_to_use,
                app_settings,
            )
            return False
        for o_str in octets_str:  # Validate each octet range
            octet_val = int(o_str)
            if not (0 <= octet_val <= 255):
                log_map_server(
                    f"{symbols.get('warning', '!')} CIDR IP octet '{octet_val}' is out of range (0-255).",
                    "warning",
                    logger_to_use,
                    app_settings,
                )
                return False
        return True  # All checks passed
    except ValueError:  # If int() conversion fails for prefix or octets
        log_map_server(
            f"{symbols.get('warning', '!')} CIDR '{cidr}' contains non-integer parts.",
            "warning",
            logger_to_use,
            app_settings,
        )
        return False
