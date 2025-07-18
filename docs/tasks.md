# Development Tasks

This document outlines the development tasks for the Open Journey Server project, consolidating the previous `plan.md`
and `tasks.md` files. The tasks are prioritized to build upon the new Kubernetes-based architecture.

## Short-term

The immediate priority is to continue building on the new architecture, focusing on data processing and core
functionalities.

### Foundational Data Architecture: Static Pipeline

- [ ] **Task 1: Design and Implement the Canonical Database Schema**
    - [ ] Define the final tables, columns, and data types for core concepts like `transport_stops`, `transport_routes`,
      `transport_trips`, `transport_schedule`, and `transport_shapes`.
    - [ ] Establish foreign key relationships and constraints.
    - [ ] Create the SQL script to deploy the new schema to PostGIS.
- [ ] **Task 2: Refactor the GTFS Processor as the First Plugin**
    - [ ] Create a formal `ProcessorInterface` abstract base class that defines the required methods (`extract`,
      `transform`, `load`) for all future static processors.
    - [ ] Adapt the existing GTFS processing logic to conform to this new interface.
    - [ ] Rewrite the transformation step to map the GTFS data to the new **Canonical Database Schema** instead of the
      old `gtfs_*` tables.
- [ ] **Task 3: Build the Static ETL Orchestrator**
    - [ ] Develop the main entry point script (`run_static_etl.py`).
    - [ ] Implement logic to read the new `static_feeds` list from `config.yaml`.
    - [ ] Implement the plugin loader, which dynamically instantiates and runs the correct processor based on the `type`
      specified for each feed in the config.

### Installer & Code Quality

- [ ] **Task 4: Improve Test Coverage and Documentation**
    - [ ] Write unit tests for all functions within the `common/` utility modules to reach >80% coverage.
    - [ ] Create and publish comprehensive architecture diagrams for the new Static and Real-time data pipelines.

---

## Medium-term

With the static data foundation in place, the focus shifts to building the **Real-time Data Service** and updating
existing services to use the new canonical data.

### Real-time Data Service

- [ ] **Task 5: Design the Canonical Data Model**
    - [ ] Define and finalize the data structures for `CanonicalVehiclePosition` and `CanonicalServiceAlert`.
- [ ] **Task 6: Build the Core Real-time Service Components**
    - [ ] Implement the **Orchestrator** to manage the polling loop based on the `realtime` section in `config.yaml`.
    - [ ] Implement a thread-safe, in-memory **Data Cache** to store the canonical data.
    - [ ] Create a lightweight FastAPI service to expose the cache via an internal `/api/v1/realtime` endpoint.
- [ ] **Task 7: Build the First Real-time Plugin (GTFS-RT)**
    - [ ] Implement the `ProcessorInterface` for real-time plugins.
    - [ ] Write the logic to fetch, decode (Protobuf), and transform GTFS-RT Vehicle Position data into the
      `CanonicalVehiclePosition` model.
- [ ] **Task 8: Complete the End-to-End Integration**
    - [ ] Configure the Nginx reverse proxy to expose the internal real-time API at a public `/realtime/` path.
    - [ ] Update the frontend map's JavaScript to poll this new endpoint and display live vehicle data.

### System Integration and Improvements

- [ ] **Task 9: Update Downstream Data Consumers**
    - [ ] Modify the `pg_tileserv` configuration to query the new `transport_*` canonical tables, not the legacy
      `gtfs_*` tables.
- [ ] **Task 10: Implement Monitoring and Observability**
    - [ ] Implement structured, centralized logging for all services.
    - [ ] Add Prometheus metrics collection to the new real-time service and the static ETL pipeline.

---

## Long-term

With the core pluggable frameworks for both static and real-time data fully operational, the final phase focuses on
expansion and adding high-value features.

### Expansion: Adding New Data Sources

- [ ] **Task 11: Develop NeTEx Static Processor Plugin**
    - [ ] Implement a new processor that can parse and transform NeTEx data into the Canonical Database Schema.
- [ ] **Task 12: Develop SIRI-VM Real-time Processor Plugin**
    - [ ] Implement a new processor that can connect to a SIRI endpoint, parse the XML, and transform it into the
      Canonical Data Model.

### Advanced Features

- [ ] **Task 13: Implement Advanced Routing**
    - [ ] Add support for walking and cycling profiles to OSRM.
    - [ ] Begin research into integrating traffic-aware routing.

### UI/UX

- [ ] **Task 14: Enhance the Installation UI**
    - [ ] Develop a full web-based UI for the Kubernetes installer to provide a more user-friendly experience.
