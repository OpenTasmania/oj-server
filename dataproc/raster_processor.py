# dataproc/raster_processor.py
# -*- coding: utf-8 -*-
"""
Handles raster tile pre-rendering tasks.
"""
import logging
import os
import subprocess
from typing import Optional

# Assuming common utilities are in common/
from common.command_utils import log_map_server, run_elevated_command
# Assuming config.py is in setup/ or project root and accessible
from setup import config

module_logger = logging.getLogger(__name__)


def raster_tile_prerender(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Pre-render raster tiles using render_list for different zoom level ranges.
    Ensures renderd service is active before starting.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Starting raster tile pre-rendering...",
        "info",
        logger_to_use,
    )

    # Check if renderd service is active
    try:
        renderd_status_cmd = ["systemctl", "is-active", "renderd.service"]
        result = run_elevated_command(
            renderd_status_cmd,
            capture_output=True,
            check=False,
            current_logger=logger_to_use
        )
        if result.returncode != 0 or result.stdout.strip() != "active":
            log_map_server(
                f"{config.SYMBOLS['error']} renderd service is not active (status: {result.stdout.strip()}). "
                "Cannot pre-render tiles. Please ensure renderd is set up and running.",
                "error",
                logger_to_use,
            )
            raise RuntimeError("renderd service is not active. Cannot pre-render tiles.")
        log_map_server(
            f"{config.SYMBOLS['success']} renderd service is active. Proceeding with tile pre-rendering.",
            "success",
            logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Error checking renderd status: {e.stderr or e.stdout or e}",
            "error",
            logger_to_use,
        )
        raise RuntimeError(f"Error checking renderd status: {e}")
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Unexpected error checking renderd status: {e}",
            "error",
            logger_to_use,
        )
        raise

    num_threads = str(os.cpu_count() or 1)

    render_list_base_cmd = [
        "render_list",
        "--all",
        "--num-threads", num_threads,
        "--socket=/var/run/renderd/renderd.sock"
    ]

    # Stage 1: Low-resolution tiles (Zoom 0-5)
    log_map_server(
        f"{config.SYMBOLS['info']} Queuing low-resolution raster tiles (Zoom 0-5) for rendering...",
        "info",
        logger_to_use,
    )
    cmd_low_res = render_list_base_cmd + ["--min-zoom=0", "--max-zoom=5"]
    try:
        run_elevated_command(cmd_low_res, current_logger=logger_to_use)
        log_map_server(
            f"{config.SYMBOLS['success']} Successfully queued low-resolution tiles (Zoom 0-5). "
            "renderd will process these in the background.",
            "success",
            logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to queue low-resolution tiles: {e.stderr or e.stdout or e}",
            "error",
            logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['warning']} Continuing to queue high-resolution tiles despite low-resolution queueing error.",
            "warning",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Unexpected error queuing low-resolution tiles: {e}",
            "error",
            logger_to_use,
        )
        raise

    # Stage 2: High-resolution tiles (Zoom 6-12)
    log_map_server(
        f"{config.SYMBOLS['info']} Queuing high-resolution raster tiles (Zoom 6-12) for rendering...",
        "info",
        logger_to_use,
    )
    cmd_high_res = render_list_base_cmd + ["--min-zoom=6", "--max-zoom=12"]
    try:
        run_elevated_command(cmd_high_res, current_logger=logger_to_use)
        log_map_server(
            f"{config.SYMBOLS['success']} Successfully queued high-resolution tiles (Zoom 6-12). "
            "renderd will process these in the background.",
            "success",
            logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to queue high-resolution tiles: {e.stderr or e.stdout or e}",
            "error",
            logger_to_use,
        )
        raise RuntimeError(f"Failed to queue high-resolution tiles: {e}")
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Unexpected error queuing high-resolution tiles: {e}",
            "error",
            logger_to_use,
        )
        raise

    log_map_server(
        f"{config.SYMBOLS['info']} All tile rendering tasks have been queued. "
        "Monitor renderd logs and system load for progress. This can take a very long time.",
        "info",
        logger_to_use,
    )
