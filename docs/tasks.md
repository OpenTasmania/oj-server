# Development Tasks

This document outlines the development tasks for the Open Journey Server project, consolidating the previous `plan.md`
and `tasks.md` files. The tasks are prioritized to build upon the new Kubernetes-based architecture.

## Short-term

The immediate priority is to continue building on the new architecture, focusing on data processing and core
functionalities.

### System Integration and Improvements

- [ ] **Task 7: Update Downstream Data Consumers**
    - [ ] Modify the `pg_tileserv` configuration to query the new `transport_*` canonical tables, not the legacy
      `gtfs_*` tables.
- [ ] **Task 8: Implement Monitoring and Observability**
    - [ ] Implement structured, centralized logging for all services.
- [ ] Add Prometheus metrics collection to the static ETL pipeline.

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
