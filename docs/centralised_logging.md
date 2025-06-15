## **Application Logging Strategy**

### Overview

This document outlines the application's centralized logging system. The strategy is built upon Python's standard
`logging` library to ensure a consistent, maintainable, and well-documented approach to logging across the entire
application.

The system is designed with three core components:

1. **Centralized Configuration**: A single point of initialization for the application's logging behavior.
2. **Standard Implementation**: A consistent pattern for how logging is implemented in every module.
3. **TUI Integration**: A dedicated log handler for displaying log messages in the Text-based User Interface (TUI).

---

### 1. How Logging Works

#### Centralized Configuration

Logging for the entire application is initialized in a single location: **`install.py`**.

This script calls the `setup_logging` function from `common/core_utils.py` at the beginning of the application
lifecycle. This approach ensures that all subsequent modules and processes inherit the same logging configuration,
including the format, logging level, and output handlers. This is the **only** place where the logging system should be
configured.

#### Standard Implementation in Modules

To maintain consistency, all Python modules across the application adhere to the following standard practices.

* **Step 1: Import the Logging Module**
  A reference to Python's built-in `logging` module is included at the top of each file.
    ```python
    import logging
    ```

* **Step 2: Get a Logger Instance**
  A module-level logger instance is created in each file. Using the `__name__` variable ensures that log messages are
  automatically tagged with their source module (e.g., `common.command_utils`), making it easy to trace the origin of a
  log entry.
    ```python
    logger = logging.getLogger(__name__)
    ```

* **Step 3: Use Logger Methods Instead of `print()`**
  All `print()` statements intended for logging application events, status updates, or errors have been replaced with
  calls to the appropriate logger method. This allows messages to be routed through the centralized system and filtered
  by severity.

    * For general information: `logger.info("Starting process...")`
    * For warnings: `logger.warning("Configuration not found, using defaults.")`
    * For non-critical errors: `logger.error("Failed to process a specific item.")`

* **Step 4: Standardized Exception Handling**
  To ensure that exceptions are logged with a full stack trace, `try...except` blocks use `logger.exception()`. This
  method automatically captures the exception details and logs them at the `ERROR` level.

    * **Standard Implementation:**
        ```python
        try:
            # some risky operation
        except Exception:
            logger.exception("An unexpected error occurred during the operation.")
        ```

---

### 2. TUI Log Handler

The application features a Text-based User Interface (TUI) that displays real-time log output. This is managed by the
`TuiLogHandler` class located in `ui/tui_logging.py`.

* **Function**: This handler captures log records emitted from anywhere in the application and directs them to the
  `LogDisplay` widget in the TUI.
* **Threading**: The handler is thread-safe. If a log event originates from a background thread, the handler uses the
  `urwid.MainLoop.alarm` method to ensure the UI is updated safely from the main thread.
* **Formatting**: The `TuiLogHandler` currently uses its own `logging.Formatter` to style messages within the TUI.

---

### 3. Modules Using Centralized Logging

The standard logging implementation described above is used in the following modules:

**Core and Common Utilities**

* `common/command_utils.py`
* `common/system_utils.py`
* `common/network_utils.py`
* `common/pgpass_utils.py`
* `common/file_utils.py`

**Setup and Configuration**

* `setup/cli_handler.py`
* `setup/core_prerequisites.py`
* `setup/step_executor.py`
* `setup/state_manager.py`
* `setup/configure/nginx_configurator.py`
* ...and all other configurator files.

**Installers**

* `installer/main_installer.py`
* `installer/nodejs_installer.py`
* `installer/docker_installer.py`
* ...and all other installer files.

**Data Processors**

* `processors/data_handling/data_processing.py`
* `processors/data_handling/raster_processor.py`
* ...and all other processor files.

**Bootstrap Installer**

* `bootstrap_installer/bs_pydantic.py`
* `bootstrap_installer/bs_apt.py`
* `bootstrap_installer/bs_prereqs.py`
* ...and all other bootstrap installer files.

**User Interface**

* `ui/tui_application.py`

**Tests**

* `tests/test_app_settings.py`
* `tests/osrm/test_osrm_port_mapping.py`

---

### 4. Potential Improvements

While the current system provides a solid foundation, the following improvements could enhance its flexibility and
maintainability:

* **Refactor `TuiLogHandler`**: The original plan to centralize logging included simplifying the `TuiLogHandler`.
  Currently, the handler defines its own formatter and contains manual thread-handling logic. This could be refactored
  to rely on the centralized configuration from `install.py`, which would reduce code duplication and simplify
  maintenance.
* **Externalize Log Configuration**: Logging settings (e.g., log level, file output path) could be moved from the code
  into a configuration file (`config.yaml`). This would allow users or administrators to adjust log verbosity without
  needing to modify the source code.
* **Adopt Structured Logging**: For more advanced log analysis, the system could be enhanced to output logs in a
  structured format like JSON. This would make logs machine-readable and easier to ingest into log analysis platforms.
* **Periodic Code Audit**: A periodic audit could be performed to search the codebase for any new `print()` statements
  that may have been added for debugging or logging, ensuring they are converted to use the proper `logger` methods.