### **Phase 1: Additive Migration (File Creation and Editing)**

**Goal:** Prepare the new Kubernetes-native configuration by creating and editing files. No existing files will be removed or executed.

-----

**Step 1.1: Create the Data Processor Container Files**

* **Objective:** Create the necessary files to define a container for the GTFS data processing logic.
* **File Actions:**
    1.  Create a new directory: `data_processor`.
    2.  Create a new file: `data_processor/Dockerfile`. Populate it with the following content:
        ```dockerfile
        # Use a slim Python base image
        FROM python:3.9-slim

        # Set the working directory in the container
        WORKDIR /app

        # Copy and install Python dependencies
        COPY requirements.txt .
        RUN pip install --no-cache-dir -r requirements.txt

        # Copy the necessary application code
        COPY common/ ./common/
        COPY installer/processors/ ./installer/processors/

        # The container will be executed by a run script
        COPY data_processor/run.py .
        CMD ["python", "run.py"]
        ```
    3.  Create a new file: `data_processor/run.py`. This script will act as the entrypoint to start the GTFS processing. Populate it with:
        ```python
        # data_processor/run.py
        import os
        from installer.processors.plugins.importers.transit.gtfs.gtfs_process import run_gtfs_setup

        if __name__ == "__main__":
            print("Starting GTFS data processing...")
            # This script now expects a config file at /config/config.yaml
            # which will be provided by a Kubernetes ConfigMap.
            run_gtfs_setup(os.environ.get("CONFIG_FILE_PATH", "/config/config.yaml"))
            print("GTFS data processing finished.")
        ```

-----

**Step 1.2: Create the OSRM Kubernetes Job Manifest**

* **Objective:** Define a Kubernetes `Job` that will perform the OSRM data processing, replacing the logic from `osrm_configurator.py`.
* **File Actions:**
    1.  Create a new file: `kubernetes/components/osrm/processing-job.yaml`.
    2.  Populate it with the following `Job` definition. This configuration is derived from the commands found in `installer/components/osrm/osrm_configurator.py`:
        ```yaml
        apiVersion: batch/v1
        kind: Job
        metadata:
          name: osrm-processing-job
          namespace: ojp
        spec:
          template:
            spec:
              containers:
              - name: osrm-processor
                image: osrm/osrm-backend:v5.27.0
                command: ["/bin/sh", "-c"]
                args:
                  - >
                    osrm-extract -p /opt/car.lua /data/region.osm.pbf &&
                    osrm-partition /data/region.osrm &&
                    osrm-customize /data/region.osrm
                volumeMounts:
                - name: osrm-data
                  mountPath: /data
              restartPolicy: Never
              volumes:
              - name: osrm-data
                persistentVolumeClaim:
                  claimName: osrm-pvc
          backoffLimit: 4
        ```

-----

**Step 1.3: Verify Postgres Initialization Script**

* **Objective:** Ensure the Kubernetes Postgres init script (`init-postgis.sh`) replicates all setup actions from the old `postgres_configurator.py`. This is a critical step.
* **File Actions:**
    1.  **Analyze** `installer/components/postgres/postgres_configurator.py` to identify the exact names of the database(s), user(s), and PostgreSQL extensions it creates.
    2.  **Review** `kubernetes/components/postgres/init-postgis.sh`.
    3.  **Modify** `kubernetes/components/postgres/init-postgis.sh` to ensure it performs the identical setup. Add any missing `psql` commands to create users or enable extensions.

-----

**Step 1.4: Update Kubernetes Configurations**

* **Objective:** Integrate the new data processing jobs and their configurations into the main Kubernetes configuration using Kustomize.
* **File Actions:**
    1.  **Create a `ConfigMap`** to provide the `config.yaml` to the GTFS processing job. Create a new file: `kubernetes/components/data_processing/configmap.yaml`.
        ```yaml
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: ojp-config
          namespace: ojp
        data:
          config.yaml: |
            # config.yaml
            # Default configuration settings for the OpenStreetMap Server Setup.
            # Users can override these settings by editing this file.
            # Environment variables and CLI arguments can also override these settings.

            # General Application Settings
            admin_group_ip: "192.168.128.0/22"
            gtfs_feed_url: "https://www.transport.act.gov.au/googletransit/google_transit.zip"
            # IMPORTANT: Change this to your server's actual FQDN or IP.
            # If left as "example.com", the installer will error unless --dev-override is specified, in which case it will use the primary IP address.
            vm_ip_or_domain: "example.com"
            pg_tileserv_binary_location: "https://postgisftw.s3.amazonaws.com/pg_tileserv_latest_linux.zip"
            log_prefix: "[OJP-SERVER-SETUP]" # Log prefix for the main installer script

            # Developer Flags
            dev_override_unsafe_password: false # Set to true only for development to override safety checks, including allowing default DB password

            # Containerization Settings
            container_runtime_command: "docker" # e.g., "docker" or "podman"
            osrm_image_tag: "osrm/osrm-backend:latest" # OSRM Docker image to use

            # ----------------------------------------------------------------------
            # pgAdmin and pgAgent Configuration
            # ----------------------------------------------------------------------
            pgadmin:
              # Not yet available for debian trixie
              install: false

            pgagent:
              # Not yet available for debian trixie
              install: true

            postgres:
              host: "127.0.0.1"
              port: 5432
              database: "gis"
              user: "osmuser"
              # password: "yourStrongPasswordHere" # IMPORTANT: It's highly recommended to set the PG_PASSWORD
              # environment variable instead of hardcoding the password here.
              # Pydantic will pick up PG_PASSWORD from the environment.

              # Template for pg_hba.conf content.
              # Placeholders like {pg_database}, {pg_user}, {admin_group_ip}, {script_hash}
              # will be formatted by the setup script using other configuration values.
              # Use YAML's literal block scalar style for multi-line strings.
              hba_template: |
                # pg_hba.conf configured by script V{script_hash}
                # TYPE  DATABASE        USER            ADDRESS                 METHOD
                local   all             postgres                                peer
                local   all             all                                     peer
                local   {pg_database}    {pg_user}                                scram-sha-256
                host    all             all             127.0.0.1/32            scram-sha-256
                host    {pg_database}    {pg_user}        127.0.0.1/32            scram-sha-256
                host    {pg_database}    {pg_user}        {admin_group_ip}       scram-sha-256
                host    all             all             ::1/128                 scram-sha-256
                host    {pg_database}    {pg_user}        ::1/128                 scram-sha-256
              # Template for additions to postgresql.conf.
              # Supports placeholder {script_hash}.
              postgresql_conf_additions_template: |
                # --- TRANSIT SERVER CUSTOMISATIONS - Appended by script V{script_hash} ---
                listen_addresses = '*'
                shared_buffers = 2GB
                work_mem = 256MB
                maintenance_work_mem = 2GB
                checkpoint_timeout = 15min
                max_wal_size = 4GB
                min_wal_size = 2GB
                checkpoint_completion_target = 0.9
                effective_cache_size = 6GB
                logging_collector = on
                log_directory = 'log'
                log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
                log_min_duration_statement = 250ms
                # --- END TRANSIT SERVER CUSTOMISATIONS ---

            # Apache Web Server Settings
            apache:
              listen_port: 8080

              # ModTile settings
              mod_tile_request_timeout: 5
              mod_tile_missing_request_timeout: 30
              mod_tile_max_load_old: 2
              mod_tile_max_load_missing: 5

              mod_tile_conf_template: |
                # mod_tile.conf - Generated by script V{script_hash}
                LoadModule tile_module /usr/lib/apache2/modules/mod_tile.so

                ModTileRenderdSocketName /var/run/renderd/renderd.sock
                ModTileEnableStats On
                ModTileBulkMode Off
                ModTileRequestTimeout {mod_tile_request_timeout}
                ModTileMissingRequestTimeout {mod_tile_missing_request_timeout}
                ModTileMaxLoadOld {mod_tile_max_load_old}
                ModTileMaxLoadMissing {mod_tile_max_load_missing}

                <IfModule mod_expires.c>
                    ExpiresActive On
                    ExpiresByType image/png "access plus 1 month"
                </IfModule>
                <IfModule mod_headers.c>
                    Header set Cache-Control "max-age=2592000, public"
                </IfModule>

              tile_site_template: |
                # Apache tile serving site - Generated by script V{script_hash}
                <VirtualHost *:{apache_listen_port}>
                    ServerName {server_name_apache}
                    ServerAdmin {admin_email_apache}

                    # The URI /hot/ should match the URI in renderd.conf (e.g., [default] URI=/hot/).
                    AddTileConfig /hot/ default

                    ErrorLog ${{APACHE_LOG_DIR}}/tiles_error.log
                    CustomLog ${{APACHE_LOG_DIR}}/tiles_access.log combined
                </VirtualHost>

            nginx:
              proxy_conf_name_base: "transit_proxy" # Base name for the conf file, e.g. transit_proxy.conf
              proxy_site_template: |
                # Nginx reverse proxy site - Generated by script V{script_hash}
                # For server: {server_name_nginx}

                server {{
                    listen 80 default_server;
                    listen [::]:80 default_server;

                    # SSL settings below are typically managed by Certbot if you run it.
                    # listen 443 ssl http2 default_server;
                    # listen [::]:443 ssl http2 default_server;
                    # ssl_certificate /etc/letsencrypt/live/{server_name_nginx}/fullchain.pem;
                    # ssl_certificate_key /etc/letsencrypt/live/{server_name_nginx}/privkey.pem;
                    # include /etc/letsencrypt/options-ssl-nginx.conf;
                    # ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

                    server_name {server_name_nginx}; # Placeholder, will be replaced by app_settings.vm_ip_or_domain

                    access_log /var/log/nginx/{proxy_conf_filename_base}.access.log;
                    error_log /var/log/nginx/{proxy_conf_filename_base}.error.log;

                    proxy_http_version 1.1;
                    proxy_set_header Upgrade $http_upgrade;
                    proxy_set_header Connection "upgrade";
                    proxy_set_header Host $host;
                    proxy_set_header X-Real-IP $remote_addr;
                    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                    proxy_set_header X-Forwarded-Proto $scheme;
                    proxy_buffering off;

                    location /vector/ {{
                        proxy_pass http://localhost:{pg_tileserv_port};
                    }}
                    location /raster/hot/ {{
                        proxy_pass http://localhost:{apache_port}/hot/;
                    }}
                    location /route/v1/ {{ # Assumes car profile
                        proxy_pass http://localhost:{osrm_port_car}/route/v1/;
                    }}
                    location / {{
                        root {website_root_dir};
                        index index.html index.htm;
                        try_files $uri $uri/ /index.html =404;
                    }}
                }}

            pg_tileserv:
              binary_url: "https://postgisftw.s3.amazonaws.com/pg_tileserv_latest_linux.zip"
              system_user: "pgtileserv_user"
              binary_install_path: "/usr/local/bin/pg_tileserv" # Default install location
              config_dir: "/etc/pg_tileserv"
              config_filename: "config.toml"

              http_host: "0.0.0.0"
              http_port: 7800
              default_max_features: 10000
              publish_schemas: "public,gtfs"
              uri_prefix: "/vector" # Must match Nginx location block for pg_tileserv
              development_mode: false
              allow_function_sources: true

              config_template: |
                # pg_tileserv config generated by script V{script_hash}
                HttpHost = "{pg_tileserv_http_host}"
                HttpPort = {pg_tileserv_http_port}
                DatabaseURL = "{db_url_for_pg_tileserv}"
                DefaultMaxFeatures = {pg_tileserv_default_max_features}
                PublishSchemas = "{pg_tileserv_publish_schemas}"
                URIPrefix = "{pg_tileserv_uri_prefix}"
                DevelopmentMode = {pg_tileserv_development_mode_bool}
                AllowFunctionSources = {pg_tileserv_allow_function_sources_bool}

              systemd_template: |
                [Unit]
                Description=pg_tileserv - Vector Tile Server for PostGIS
                Documentation=https://github.com/CrunchyData/pg_tileserv
                Wants=network-online.target postgresql.service
                After=network-online.target postgresql.service

                [Service]
                User={pg_tileserv_system_user}
                # Assumes group is same as user, or define separately
                Group={pg_tileserv_system_group}
                Environment="DATABASE_URL={pg_tileserv_systemd_environment}"
                ExecStart={pg_tileserv_binary_path} --config {pg_tileserv_config_file_path_systemd}
                Restart=on-failure
                RestartSec=5s
                StandardOutput=journal
                StandardError=journal
                SyslogIdentifier=pg_tileserv

                [Install]
                WantedBy=multi-user.target
                # File created by script V{script_hash}

            renderd:
              num_threads_multiplier: 1
              tile_cache_dir: "/var/lib/mod_tile"
              run_dir: "/var/run/renderd" # For socket and stats file
              socket_path: "/var/run/renderd/renderd.sock"
              mapnik_xml_stylesheet_path: "/usr/local/share/maps/style/openstreetmap-carto/mapnik.xml"
              mapnik_plugins_dir_override: /usr/lib/x86_64-linux-gnu/mapnik/4.0/input/
              uri_path_segment: "hot" # Used in renderd.conf URI and Nginx/Apache proxy paths

              renderd_conf_template: |
                # {renderd_conf_path} - Generated by script V{script_hash}
                [renderd]
                num_threads={num_threads_renderd}
                tile_dir={renderd_tile_cache_dir}
                stats_file={renderd_run_dir}/renderd.stats
                font_dir_recurse=1

                [mapnik]
                plugins_dir={mapnik_plugins_dir}
                font_dir=/usr/share/fonts/
                font_dir_recurse=1

                [default]
                URI=/{renderd_uri_path_segment}/
                XML={mapnik_xml_stylesheet_path}
                HOST={renderd_host}
                TILESIZE=256

            # OSRM upstream port(s) for Nginx proxying
            osrm:
              car_profile_port: 5000
              # bicycle_profile_port: 5001 # Example if you had another

            osrm_service:
              car_profile_default_host_port: 5000 # Host port Nginx will proxy to for car profile
              container_osrm_port: 5000         # OSRM's internal port in the container
              image_tag: "osrm/osrm-backend:latest"
              extra_routed_args: "--algorithm MLD --max-matching-size 2000" # Example extra args
              systemd_template: |
                [Unit]
                Description=OSRM Routed service for region: {region_name}
                After=docker.service network-online.target
                Wants=docker.service

                [Service]
                Restart=always
                RestartSec=5
                ExecStartPre=-/usr/bin/{container_runtime_command} stop osrm-routed-{region_name}
                ExecStartPre=-/usr/bin/{container_runtime_command} rm osrm-routed-{region_name}
                ExecStart=/usr/bin/{container_runtime_command} run --rm --name osrm-routed-{region_name} \
                    -p 127.0.0.1:{host_port_for_region}:{container_osrm_port} \
                    -v "{host_osrm_data_dir_for_region}":"/data_processing":ro \
                    {osrm_image_tag} osrm-routed "/data_processing/{osrm_filename_in_container}" --max-table-size {max_table_size_routed} {extra_osrm_routed_args}

                ExecStop=/usr/bin/{container_runtime_command} stop osrm-routed-{region_name}

                [Install]
                WantedBy=multi-user.target
                # File created by script V{script_hash} for region {region_name}

            # OSRM Data Processing Settings
            osrm_data:
              base_dir: "/opt/osm_data"
              processed_dir: "/opt/osrm_processed_data"
              base_pbf_url: "https://download.geofabrik.de/australia-oceania/australia-latest.osm.pbf"
              base_pbf_filename: "australia-latest.osm.pbf"
              profile_script_in_container: "/opt/car.lua" # Standard OSRM car profile

            certbot:
              # admin_email: null # Example: "your-email@example.com" (If null or not provided, an email will be derived from vm_ip_or_domain)
              use_hsts: false            # Set to true to enable HSTS with Certbot
              use_staple_ocsp: false     # Set to true to enable OCSP Stapling with Certbot
              use_uir: false             # Set to true to request --uir flag from Certbot (less common)


            webapp:
              root_dir: "/var/www/html/map_test_page"
              index_filename: "index.html"
              default_scheme: "http" # Will be 'https' if Certbot runs successfully
              nginx_external_port: 80 # Port Nginx uses for HTTP (or 443 for HTTPS after Certbot)

              index_html_template: |
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <title>Transit System Map Test - V{script_version_short}</title>
                    <meta charset="utf-8"/>
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <link rel="stylesheet" href="{scheme}://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
                    <script src="{scheme}://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
                    <link href='{scheme}://unpkg.com/maplibre-gl@4.1.0/dist/maplibre-gl.css' rel='stylesheet' />
                    <script src='{scheme}://unpkg.com/maplibre-gl@4.1.0/dist/maplibre-gl.js'></script>
                    <style>
                        body {{ margin: 0; padding: 0; font-family: sans-serif; }}
                        #map-container {{ display: flex; flex-direction: column; height: 100vh; }}
                        .map-area {{ flex: 1; border: 1px solid #ccc; margin-bottom: 10px; min-height: 40vh; }}
                        .info {{ padding: 10px; background: #f4f4f4; border-bottom: 1px solid #ddd; margin-bottom:10px; }}
                        h2, h3 {{ margin-top: 0; }}
                        @media (min-width: 768px) {{
                            #map-container {{ flex-direction: row; }}
                            .map-area {{ flex: 1; min-height: initial; height: auto; }}
                            .map-area:first-of-type {{ margin-right: 5px; margin-bottom: 0; }}
                            .map-area:last-of-type {{ margin-left: 5px; margin-bottom: 0; }}
                        }}
                    </style>
                </head>
                <body>
                <div class="info">
                    <h2>Map Test Page</h2>
                    <p>Testing Raster Tiles (Leaflet) and Vector Tiles (MapLibre GL JS).</p>
                    <p>Server Host: <strong>{vm_ip_or_domain}</strong> (Scheme: {scheme}://, Nginx Port: {nginx_port})</p>
                    <p><i>Access URLs assume Nginx proxy is correctly configured. Map data is centered on Hobart, Tasmania.</i></p>
                </div>
                <div id="map-container">
                    <div id="map-raster" class="map-area"><h3>Raster Tiles (Leaflet) - OSM Base</h3></div>
                    <div id="map-vector" class="map-area"><h3>Vector Tiles (MapLibre GL JS) - GTFS Stops & Shapes</h3></div>
                </div>
                <script>
                    // --- Raster Map (Leaflet) ---
                    try {{
                        var rasterMap = L.map('map-raster').setView([-42.8826, 147.3257], 13);
                        L.tileLayer('{scheme}://{vm_ip_or_domain}:{nginx_port}/raster/{renderd_uri_path_segment}/{{z}}/{{x}}/{{y}}.png', {{
                            maxZoom: 19,
                            attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, Tiles by Local Server'
                        }}).addTo(rasterMap);
                        L.marker([-42.8826, 147.3257]).addTo(rasterMap).bindPopup('Hobart (Raster View)');
                    }} catch(e) {{ console.error("Leaflet map error: ", e); document.getElementById('map-raster').innerHTML = "Error initializing raster map: " + e.message; }}

                    // --- Vector Map (MapLibre GL JS) ---
                    try {{
                        var vectorMap = new maplibregl.Map({{
                            container: 'map-vector',
                            style: {{
                                'version': 8,
                                'sources': {{
                                    'pgtileserv_stops': {{
                                        'type': 'vector',
                                        'tiles': ['{scheme}://{vm_ip_or_domain}:{nginx_port}{pg_tileserv_uri_prefix}/public.gtfs_stops/{{z}}/{{x}}/{{y}}.pbf'],
                                        'maxzoom': 16 }},
                                    'pgtileserv_shapes': {{
                                        'type': 'vector',
                                        'tiles': ['{scheme}://{vm_ip_or_domain}:{nginx_port}{pg_tileserv_uri_prefix}/public.gtfs_shapes_lines/{{z}}/{{x}}/{{y}}.pbf'],
                                        'maxzoom': 16 }} }},
                                'layers': [
                                    {{ 'id': 'background', 'type': 'background', 'paint': {{ 'background-color': '#f0f2f5' }} }},
                                    {{ 'id': 'routes-lines', 'type': 'line', 'source': 'pgtileserv_shapes', 'source-layer': 'public.gtfs_shapes_lines',
                                       'layout': {{ 'line-join': 'round', 'line-cap': 'round' }},
                                       'paint': {{ 'line-color': '#e3342f', 'line-width': 2.5, 'line-opacity': 0.8 }} }},
                                    {{ 'id': 'stops-circles', 'type': 'circle', 'source': 'pgtileserv_stops', 'source-layer': 'public.gtfs_stops',
                                       'paint': {{ 'circle-radius': 4, 'circle-color': '#3490dc', 'circle-stroke-width': 1, 'circle-stroke-color': '#ffffff' }} }} ]
                            }}, center: [147.3257, -42.8826], zoom: 12 }});
                        vectorMap.addControl(new maplibregl.NavigationControl());
                    }} catch (e) {{ console.error("MapLibre GL map error:", e); document.getElementById('map-vector').innerHTML = "Error initializing vector map: " + e.message; }}
                </script>
                </body>
                </html>
            package_preseeding_values:
              tzdata:
                tzdata/Areas: select Australia
                tzdata/Zones/Australia: select Hobart
              unattended-upgrades:
                unattended-upgrades/enable_auto_updates: true boolean
        ```
    2.  **Modify `kubernetes/components/data_processing/data_processing.yaml`:** Change this file to define the Job for the GTFS processor and mount the `ConfigMap` as a volume.
        ```yaml
        apiVersion: batch/v1
        kind: Job
        metadata:
          name: gtfs-processing-job
          namespace: ojp
        spec:
          template:
            spec:
              containers:
              - name: gtfs-processor
                image: ojp/data-processor:latest
                volumeMounts:
                - name: config-volume
                  mountPath: /config
              volumes:
              - name: config-volume
                configMap:
                  name: ojp-config
              restartPolicy: Never
          backoffLimit: 4
        ```
    3.  **Modify `kubernetes/components/osrm/kustomization.yaml`:** Add the new processing job to the list of resources.
        ```yaml
        # kubernetes/components/osrm/kustomization.yaml
        resources:
          - pvc.yaml
          - deployment.yaml
          - service.yaml
          - processing-job.yaml # <-- ADD THIS LINE
        ```
    4.  **Create `kubernetes/components/data_processing/kustomization.yaml`** to bundle the job and its config.
        ```yaml
        # kubernetes/components/data_processing/kustomization.yaml
        resources:
          - data_processing.yaml
          - configmap.yaml
        ```

-----

### **Phase 2: Manual Testing Instructions**

This phase is not to be processed by any LLM. If you encounter this phase, you are to stop immediately. Do not proceed.

**Goal:** Provide you with the exact commands to build the new container, deploy the system, and verify its operation.

-----

**Step 2.1: Build the Data Processor Container**

* **Action:** From the root directory of the `ojp-server` project, run the following Docker command to build the container image defined in Phase 1.
  ```bash
  docker build -t ojp/data_processor:latest -f ./data_processor/Dockerfile .
  ```
  *If using MicroK8s, load the image into the cluster's internal registry:*
  ```bash
  docker save ojp/data-processor:latest | microk8s ctr image import -
  ```

**Step 2.2: Deploy the System**

* **Action:** Use the new installer script to deploy the full system to your test environment (e.g., MicroK8s). This command will apply all the Kubernetes manifests, including the new `Jobs`.
  ```bash
  python install_kubernetes.py deploy --env local
  ```

**Step 2.3: Verify the Deployment**

* **Action:** Check that the data processing jobs have run successfully.
    * **Check Job Status:**
      ```bash
      microk8s kubectl get jobs -n ojp
      ```
      *(You should see `osrm-processing-job` and `gtfs-processing-job` with a `COMPLETIONS` of `1/1`)*.
    * **Check Job Logs:**
      ```bash
      # Get the pod name for each job
      microk8s kubectl get pods -n ojp | grep 'processing-job'

      # View the logs of a specific pod
      microk8s kubectl logs -n ojp [pod-name-for-osrm-job]
      microk8s kubectl logs -n ojp [pod-name-for-gtfs-job]
      ```
    * **Verify Postgres:** `exec` into the Postgres pod to ensure the database was initialized correctly by the `init-postgis.sh` script.

-----

### **Phase 3: Final Cleanup**

**Goal:** If the user has confirmed the new system works as expected, remove the legacy installer files.

-----

**Step 3.1: Remove Deprecated Files**

* **Pre-condition:** Phase 2 was completed successfully.
* **File Actions:** Delete the following files and directories:
    * `install.py`
    * The entire `installer/` directory
    * The entire `bootstrap/` directory

**Step 3.2: Update Documentation**

* **File Actions:**
    * Modify `README.md` to remove all references to `install.py` and its workflow.
    * Delete the now-obsolete `docs/plan.md`.