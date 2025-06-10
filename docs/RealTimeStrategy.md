# **Instructional Manual: Architecting a Pluggable Realtime Transit Data Service**

## **1. Introduction and Vision**

To significantly enhance the capabilities of the transit server, this document outlines the architecture for a new,
dynamic data processing service. The vision is to ingest, process, and display real-time information from a wide variety
of public transit data standards, such as SIRI, NeTEx, TransXchange, and GTFS-RT.

The foundation of this architecture is built on principles of modularity and extensibility. By planning for multiple
data formats from the outset, we will create a robust, future-proof system that can be easily extended to support new
data sources without requiring a complete redesign.

## **2. Core Architectural Principles**

A successful multi-format system must be designed to manage complexity effectively. Two fundamental principles will
guide our architecture: a **Pluggable Processor Model** and a **Canonical Data Model**.

* **Principle 1: Pluggable Processor Architecture**
  Instead of a single, monolithic application, the system will be designed as a core service that loads one or more
  independent "processor plugins." Each plugin will be a self-contained module responsible for handling a single data
  format. For example, there will be a dedicated processor for SIRI, another for GTFS-RT, and so on. A central
  orchestrator will manage these plugins, allowing the system's capabilities to be extended simply by adding a new
  processor module.

* **Principle 2: The Canonical Data Model**
  This is the most critical principle for ensuring scalability and maintainability. All data, regardless of its source
  format (e.g., SIRI XML, GTFS-RT Protobuf), must be transformed by its specific processor into a **single,
  standardized, internal format**. This internal format is the "Canonical Data Model."

  The use of a canonical model decouples the complexity of external data sources from the application's core logic. The
  API and the frontend map will only ever interact with this clean, predictable, and uniform data structure, making them
  simpler to build and maintain.

## **3. Defining the Canonical Data Model**

The first step in development must be to define the schema for the Canonical Data Model. This model will serve as the
universal language for all real-time information within the application. It should be simple and contain only the
essential fields required for display and interaction on the map.

Conceptual examples of canonical data structures include:

* **`CanonicalVehiclePosition`**:
    * `vehicleId`: A unique identifier for the vehicle.
    * `tripId`: The identifier of the trip the vehicle is currently serving.
    * `routeId`: The identifier of the route associated with the trip.
    * `latitude`: The vehicle's geographical latitude.
    * `longitude`: The vehicle's geographical longitude.
    * `bearing`: The direction of travel in degrees (0-359).
    * `speed`: The vehicle's speed in meters per second.
    * `timestamp`: The timestamp of the last update in a standard format (e.g., UTC ISO 8601).
    * `sourceFeedId`: The unique ID of the feed this data originated from, as defined in the configuration.

* **`CanonicalServiceAlert`**:
    * `alertId`: A unique identifier for the alert.
    * `headerText`: A concise summary or title of the alert.
    * `descriptionText`: The full text of the service alert.
    * `affectedEntities`: A list identifying the specific routes, stops, or trips affected by the alert.
    * `sourceFeedId`: The ID of the feed this alert originated from.

## **4. Implementation Blueprint**

This section outlines the high-level components of the proposed real-time data service.

* **4.1. Configuration (`config.yaml`)**
  The system's configuration file must be updated to manage the various real-time feeds. A new top-level `realtime`
  section should be introduced. It will contain a list of `feeds`, where each feed entry must specify its `type` to
  enable the orchestrator to load the correct processor plugin.

    * **Conceptual `config.yaml` Structure:**
        ```yaml
        realtime:
          polling_interval_seconds: 30
          service_listen_port: 8001
          feeds:
            - id: "act_vehicle_positions"
              type: "gtfs-rt-vehicle-positions"
              enabled: true
              url: "URL_TO_GTFS-RT_VEHICLE_POSITIONS.pb"

            - id: "nsw_siri_vm"
              type: "siri-vm"
              enabled: true
              url: "URL_TO_SIRI_ENDPOINT"
              # Format-specific parameters, like API keys or request filters
              api_key_env_var: "NSW_TRANSPORT_API_KEY"
              request_parameters:
                MonitoringRef: "all"
        ```

* **4.2. Backend Service Architecture**
  A new, continuously running backend service should be created within the `/processors` module.

    * **The Orchestrator**: The central component of the service. Its responsibilities are to read the configuration,
      instantiate the necessary processor plugins for all enabled feeds, and manage the main polling loop that triggers
      data fetching and processing.
    * **The Processor Interface**: An abstract class that defines a strict contract for all processor plugins. It must
      mandate the implementation of key methods, such as a `process()` method that returns data conforming to the
      Canonical Data Model.
    * **Processor Plugins**: Each plugin is a concrete implementation of the Processor Interface, containing the
      highly-specialized logic for one data format. Its duties include:
        1. **Fetching**: Connecting to the data source using the appropriate protocol (e.g., HTTP GET, SOAP POST).
        2. **Parsing**: Decoding the raw data using the correct library (e.g., a Protobuf parser for GTFS-RT, an XML
           parser for SIRI).
        3. **Transforming**: Converting the parsed, format-specific data into the application's universal Canonical Data
           Model.
    * **Data Cache**: A simple, thread-safe, in-memory cache that stores the canonical data produced by all active
      processors. The orchestrator is responsible for updating this cache after each processing cycle.

* **4.3. API and Frontend Integration**
  The processed and standardized data must be made available to the web front end.

    * **Internal API**: A lightweight web service (e.g., using FastAPI) will provide an internal API endpoint (e.g.,
      `/api/v1/realtime`). This endpoint will simply read the contents of the Data Cache and return it as a single,
      consolidated JSON response.
    * **Nginx Proxy**: The existing Nginx reverse proxy will be configured to expose this internal API to the frontend
      via a public-facing path, such as `/realtime/`.
    * **Frontend Map**: The client-side JavaScript on the map page will periodically poll the `/realtime/` endpoint.
      Because the API always returns data in the same canonical format, the frontend logic for displaying vehicles,
      alerts, and other information is universal and does not need to be aware of the original source formats.

## **5. Recommended Development Roadmap**

A phased implementation is recommended to manage development effort and validate the architecture progressively.

1. **Phase 1: Foundation**: Define and finalize the Canonical Data Model structures. Build the core service components:
   the Orchestrator, the Processor Interface, the Data Cache, and the internal API service.
2. **Phase 2: First Implementation**: Build the first processor plugin for a single, well-understood format (e.g.,
   GTFS-RT Vehicle Positions).
3. **Phase 3: End-to-End Integration**: Integrate the API with the frontend. Configure the Nginx proxy and update the
   map's JavaScript to fetch and display the real-time data from the first processor. This validates the entire
   pipeline.
4. **Phase 4: Expansion**: With the core system in place, iteratively develop and add new processor plugins for other
   data formats (SIRI, NeTEx, etc.) as required. Each new addition will be a self-contained module, demonstrating the
   power and flexibility of the pluggable architecture.