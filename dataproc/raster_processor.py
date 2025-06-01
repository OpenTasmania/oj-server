# dataproc/raster_processor.py
# -*- coding: utf-8 -*-
"""
Handles raster tile pre-rendering tasks.
"""
import logging
import os
import subprocess
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)


def raster_tile_prerender(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    renderd_cfg = app_settings.renderd

    log_map_server(
        f"{symbols.get('step', '➡️')} Starting raster tile pre-rendering...",
        "info",
        logger_to_use,
        app_settings,
    )

    try:
        renderd_status_cmd = ["systemctl", "is-active", "renderd.service"]
        result = run_elevated_command(
            renderd_status_cmd,
            app_settings,
            capture_output=True,
            check=False,
            current_logger=logger_to_use,
        )
        if result.returncode != 0 or result.stdout.strip() != "active":
            log_map_server(
                f"{symbols.get('error', '❌')} renderd service not active (status: {result.stdout.strip()}). Cannot pre-render.",
                "error",
                logger_to_use,
                app_settings,
            )
            raise RuntimeError(
                "renderd service is not active for tile pre-rendering."
            )
        log_map_server(
            f"{symbols.get('success', '✅')} renderd service active. Proceeding with pre-rendering.",
            "success",
            logger_to_use,
            app_settings,
        )
    except (
            Exception
    ) as e:  # Includes CalledProcessError from run_elevated_command if check=True was used
        log_map_server(
            f"{symbols.get('error', '❌')} Error checking renderd status: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        raise

    num_threads_str = "0"
    if renderd_cfg.num_threads_multiplier > 0:
        cpu_c = os.cpu_count()
        calculated_threads = int(
            (cpu_c or 1) * renderd_cfg.num_threads_multiplier
        )
        num_threads_str = str(max(1, calculated_threads))

    render_list_base_cmd = [
        "render_list",
        "--all",
        "--num-threads",
        num_threads_str,
        f"--socket={renderd_cfg.socket_path}",
    ]

    zoom_ranges = [
        {"min": 0, "max": 5, "desc": "low-resolution (Zoom 0-5)"},
        {"min": 6, "max": 12, "desc": "mid-resolution (Zoom 6-12)"},
    ]

    for z_range in zoom_ranges:
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Queuing {z_range['desc']} raster tiles for rendering...",
            "info",
            logger_to_use,
            app_settings,
        )
        cmd_zoom_range = render_list_base_cmd + [
            f"--min-zoom={z_range['min']}",
            f"--max-zoom={z_range['max']}",
        ]
        try:
            run_elevated_command(
                cmd_zoom_range, app_settings, current_logger=logger_to_use
            )
            log_map_server(
                f"{symbols.get('success', '✅')} Successfully queued {z_range['desc']} tiles.",
                "success",
                logger_to_use,
                app_settings,
            )
        except subprocess.CalledProcessError as e:
            log_map_server(
                f"{symbols.get('error', '❌')} Failed to queue {z_range['desc']} tiles: {e.stderr or e.stdout or e}",
                "error",
                logger_to_use,
                app_settings,
            )
            if z_range["min"] < 6:
                log_map_server(
                    f"{symbols.get('warning', '!')} Low-resolution tile queuing failed. Subsequent ranges might also fail.",
                    "warning",
                    logger_to_use,
                    app_settings,
                )
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '❌')} Unexpected error queuing {z_range['desc']} tiles: {e}",
                "error",
                logger_to_use,
                app_settings,
                exc_info=True,
            )
            raise

    log_map_server(
        f"{symbols.get('info', 'ℹ️')} All tile rendering tasks queued. Monitor renderd logs.",
        "info",
        logger_to_use,
        app_settings,
    )
