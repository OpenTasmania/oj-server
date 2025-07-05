### **LLM Refactoring Prompt**

**Primary Goal:**

Refactor the Python-based installer framework by merging separate `installer` and `configurator` classes into single, unified component classes. This refactoring will resolve component registration conflicts and ensure all components fully adhere to the `BaseComponent` abstract class design.

**Project Context & Analysis:**

The framework, located in `ot-osm-osrm-server/installer/components/`, contains numerous components that fall into two categories:

1.  **Paired Components:** These components split their logic across two files: an `..._installer.py` file for installation methods (`install`, `uninstall`, `is_installed`) and a corresponding `..._configurator.py` file for configuration methods (`configure`, `unconfigure`, `is_configured`). This separation causes registration conflicts. The pairs to be merged are:
    * `apache`
    * `carto`
    * `certbot`
    * `data_processing`
    * `nginx`
    * `osrm`
    * `pg_tileserv`
    * `postgres`
    * `renderd`
    * `ufw`

2.  **Standalone Components:** These components exist as a single file and may not fully implement the required six-method interface from `BaseComponent`. They need to be standardized. The standalone components are:
    * `docker` (`docker_installer.py`)
    * `gtfs` (`gtfs_configurator.py`)
    * `nodejs` (`nodejs_installer.py`)
    * `pgadmin` (`pgadmin_installer.py`)
    * `pgagent` (`pgagent_installer.py`)
    * `prerequisites` (`prerequisites_installer.py`)

**Technical Standardization Note:**
A minor inconsistency exists in the codebase between `@InstallerRegistry.register` and `@ComponentRegistry.register`. The single, unified standard to be used for all components is **`@ComponentRegistry.register`**.

**Your Task:**

Perform a systematic refactoring of every component according to the instructions below.

---

### **Part 1: Merge Paired Components**

For each of the **Paired Components** listed above (`apache`, `carto`, etc.):

1.  **Select Base File:** Use the `..._installer.py` file as the target for the merged code.
2.  **Merge Imports:** Copy all unique import statements from the `..._configurator.py` file to the top of the `..._installer.py` file. Organize the imports logically and remove any duplicates.
3.  **Merge Class Logic:**
    * Copy all methods from the configurator class (e.g., `NginxConfigurator`) into the installer class (e.g., `NginxInstaller`). This includes `configure`, `unconfigure`, `is_configured`, and all private helper methods (e.g., `_create_nginx_proxy_site_config`).
    * **Replace** any placeholder configuration methods in the installer class with the complete implementations from the configurator class.
4.  **Update Decorator:**
    * Ensure the decorator is `@ComponentRegistry.register(...)`.
    * Merge the `metadata` dictionaries from both decorators. The final metadata should be a union of both. If any keys conflict, the installer's metadata values should take precedence.
    * Update the `description` in the metadata to reflect the combined role, for example: `"Installer and configurator for the Nginx web server and reverse proxy."`.
5.  **Update Docstrings:** Modify the class docstring of the merged installer class to clearly state its dual role as both an installer and a configurator.

---

### **Part 2: Standardize Standalone Components**

For each of the **Standalone Components** listed above (`docker`, `gtfs`, etc.):

1.  **File & Class Naming:**
    * If a component is a configurator-only (i.e., `gtfs`), you must rename the file from `gtfs_configurator.py` to `gtfs_installer.py` and the class from `GtfsConfigurator` to `GtfsInstaller` for consistency.
2.  **Ensure `BaseComponent` Compliance:**
    * Verify that the class implements all six required methods from `BaseComponent`: `install`, `uninstall`, `is_installed`, `configure`, `unconfigure`, and `is_configured`.
    * For any missing methods, add them to the class. The methods for components that do not require configuration or installation logic should return `True` and log an informational message. For example:
        ```python
        def configure(self) -> bool:
            """
            Configures the component.

            Returns:
                True, as this component requires no specific configuration step.
            """
            self.logger.info("Configuration for %s is not required.", self.__class__.__name__)
            return True
        ```

---

### **Output Requirements**

Your final output must be a single response containing a clear, actionable set of instructions. Structure your response sequentially, component by component. For each component you modify, you must provide:

1.  A markdown header indicating the component (e.g., `### Merged 'nginx' Component` or `### Standardized 'docker' Component`).
2.  The **full, complete, and final code** for the updated `..._installer.py` file, presented in a single, properly formatted Python code block.
3.  For merged components, you **must** add an explicit instruction to **delete** the now-redundant `..._configurator.py` file.
4.  If a file was renamed (like `gtfs`), state the original and new filenames clearly.
