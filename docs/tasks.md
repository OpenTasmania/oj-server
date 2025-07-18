# Development Tasks

This document outlines the development tasks for the Open Journey Server project, consolidating the previous `plan.md`
and `tasks.md` files. The tasks are prioritized to build upon the new Kubernetes-based architecture.

## Short-term

The immediate priority is to continue building on the new architecture, focusing on data processing and core
functionalities.

### Foundational Data Architecture: Static Pipeline

- [x] **Task 1: Build the Static ETL Orchestrator**

### Installer & Code Quality

- [ ] **Task 2: Create Architecture Documentation**
    - [ ] Create and publish comprehensive architecture diagrams for the new Static and Real-time data pipelines.

---

## Medium-term

With the static data foundation in place, the focus shifts to building the **Real-time Data Service** and updating
existing services to use the new canonical data.

### Real-time Data Service

- [ ] **Task 3: Design the Canonical Data Model**
    - [ ] Define and finalize the data structures for `CanonicalVehiclePosition` and `CanonicalServiceAlert`.
- [ ] **Task 4: Build the Core Real-time Service Components**
    - [ ] Implement the **Orchestrator** to manage the polling loop based on the `realtime` section in `config.yaml`.
    - [ ] Implement a thread-safe, in-memory **Data Cache** to store the canonical data.
    - [ ] Create a lightweight FastAPI service to expose the cache via an internal `/api/v1/realtime` endpoint.
- [ ] **Task 5: Build the First Real-time Plugin (GTFS-RT)**
    - [ ] Implement the `ProcessorInterface` for real-time plugins.
    - [ ] Write the logic to fetch, decode (Protobuf), and transform GTFS-RT Vehicle Position data into the
      `CanonicalVehiclePosition` model.
- [ ] **Task 6: Complete the End-to-End Integration**
    - [ ] Configure the Nginx reverse proxy to expose the internal real-time API at a public `/realtime/` path.
    - [ ] Update the frontend map's JavaScript to poll this new endpoint and display live vehicle data.

### System Integration and Improvements

- [ ] **Task 7: Update Downstream Data Consumers**
    - [ ] Modify the `pg_tileserv` configuration to query the new `transport_*` canonical tables, not the legacy
      `gtfs_*` tables.
- [ ] **Task 8: Implement Monitoring and Observability**
    - [ ] Implement structured, centralized logging for all services.
    - [ ] Add Prometheus metrics collection to the new real-time service and the static ETL pipeline.

---

## Long-term

With the core pluggable frameworks for both static and real-time data fully operational, the final phase focuses on
expansion and adding high-value features.

### Expansion: Adding New Data Sources

- [ ] **Task 9: Develop NeTEx Static Processor Plugin**
    - [ ] Implement a new processor that can parse and transform NeTEx data into the Canonical Database Schema.
- [ ] **Task 10: Develop SIRI-VM Real-time Processor Plugin**
    - [ ] Implement a new processor that can connect to a SIRI endpoint, parse the XML, and transform it into the
      Canonical Data Model.

### Advanced Features

- [ ] **Task 11: Implement Advanced Routing**
    - [ ] Add support for walking and cycling profiles to OSRM.
    - [ ] Begin research into integrating traffic-aware routing.

### UI/UX

- [ ] **Task 12: Enhance the Installation UI**
    - [ ] Develop a full web-based UI for the Kubernetes installer to provide a more user-friendly experience.
