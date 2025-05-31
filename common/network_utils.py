# common/network_utils.py
# -*- coding: utf-8 -*-
"""
Network-related utility functions.
"""
import logging
import re
from typing import Optional
from setup import config # Assuming config.py is still accessible like this
from .command_utils import log_map_server # common.command_utils

module_logger = logging.getLogger(__name__)

def validate_cidr(
    cidr: str, current_logger: Optional[logging.Logger] = None
) -> bool:
    """
    Validate a CIDR (Classless Inter-Domain Routing) notation IP address range.
    Checks for format xxx.xxx.xxx.xxx/yy and valid ranges for octets and prefix.
    """
    logger_to_use = current_logger if current_logger else module_logger
    if not isinstance(cidr, str):
        log_map_server(
            f"{config.SYMBOLS['error']} Invalid input for CIDR validation: not a string.",
            "error",
            logger_to_use,
        )
        return False

    match = re.fullmatch(
        r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$", cidr
    )
    if not match:
        log_map_server(
            f"{config.SYMBOLS['warning']} CIDR '{cidr}' has invalid format.",
            "warning",
            logger_to_use,
        )
        return False

    ip_part, prefix_str = cidr.split("/")
    try:
        prefix = int(prefix_str)
        if not (0 <= prefix <= 32):
            log_map_server(
                f"{config.SYMBOLS['warning']} CIDR prefix '/{prefix}' is out of range (0-32).",
                "warning",
                logger_to_use,
            )
            return False

        octets_str = ip_part.split(".")
        if len(octets_str) != 4:
            log_map_server(
                f"{config.SYMBOLS['warning']} CIDR IP part '{ip_part}' does not have 4 octets.",
                "warning",
                logger_to_use,
            )
            return False
        for o_str in octets_str:
            octet_val = int(o_str)
            if not (0 <= octet_val <= 255):
                log_map_server(
                    f"{config.SYMBOLS['warning']} CIDR IP octet '{octet_val}' is out of range (0-255).",
                    "warning",
                    logger_to_use,
                )
                return False
        return True
    except ValueError:
        log_map_server(
            f"{config.SYMBOLS['warning']} CIDR '{cidr}' contains non-integer parts.",
            "warning",
            logger_to_use,
        )
        return False