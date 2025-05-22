#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main entry point for the Map Server Setup.
This script now delegates to the main application logic in the 'setup' package.
"""
import sys
import os

# Ensure the 'setup' directory (and its parent for potential sibling packages like gtfs_processor)
# are discoverable. The current script's directory should contain the 'setup' package.
SCRIPT_DIR_LAUNCHER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR_LAUNCHER)

if __name__ == "__main__":
    try:
        # Attempt to import the main entry function from the setup package
        from setup.main import main_map_server_entry
        # Call the main entry function and exit with its return code
        sys.exit(main_map_server_entry())
    except ImportError as e:
        print(f"CRITICAL ERROR: Could not import the main setup module.", file=sys.stderr)
        print(f"  Ensure that the 'setup' directory exists alongside this script, with an '__init__.py' file,", file=sys.stderr)
        print(f"  and that 'setup/main.py' contains 'main_map_server_entry'.", file=sys.stderr)
        print(f"  Details: {e}", file=sys.stderr)
        print(f"  Current sys.path: {sys.path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Catch any other unexpected critical errors during the very initial startup.
        import traceback
        print(f"CRITICAL UNHANDLED ERROR during script startup: {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        sys.exit(1)