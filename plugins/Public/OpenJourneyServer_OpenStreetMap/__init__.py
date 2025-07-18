#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenJourneyServer-OpenStreetMap Plugin for OpenJourney Server

This plugin provides OpenJourneyServer-OpenStreetMap tile rendering capabilities for the OpenJourney server.
It manages the renderd service, tile caching, and integration with the mapping stack including
Mapnik, mod_tile, and Apache for serving raster tiles.
"""

from .plugin import OpenStreetMapPlugin, OpenStreetMapMigration001

__version__ = "1.0.0"
__author__ = "OpenJourney Team"
__description__ = "OpenJourneyServer-OpenStreetMap tile rendering plugin for OpenJourney Server"

__all__ = ["OpenStreetMapPlugin", "OpenStreetMapMigration001"]
