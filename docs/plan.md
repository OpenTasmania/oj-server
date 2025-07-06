# **Open Journey Planner Server Improvement Plan**

## **1. Introduction**

This document outlines a comprehensive improvement plan for the Open Journey Planner Server project based on an analysis of the
current codebase, architecture, and identified needs. The plan is organized by key areas of the system and includes
rationale for each proposed change.

## **2. Project Goals and Constraints**

### **2.1 Core Project Goals**

The Open Journey Planner Server aims to:

1. Provide a complete self-hosted OpenStreetMap system
2. Ingest and serve OpenStreetMap (OSM) data for base maps and routing networks
3. Serve both vector and raster map tiles
4. Provide turn-by-turn routing via OSRM
5. Support multiple data sources like GTFS, NexTex, TransXchange, GTFS-RT, SIRI
6. Make all data queryable through PostgreSQL/PostGIS
7. Run on a dedicated Debian system with minimal setup complexity

### **2.2 Key Constraints**

The project operates under the following constraints:

1. **Technical Constraints**
    * Must run on Debian 13 "Trixie" system
    * Requires Python 3.13 for development and runtime
    * Uses `uv` for package management and virtual environments
    * Must support both vector tiles (via pg_tileserv) and raster tiles (via classic OSM stack)

2. **Operational Constraints**
    * Installation process must be streamlined and reliable
    * System must be maintainable by users with moderate technical skills
    * Services must be properly secured (firewall, HTTPS, etc.)
    * Data processing pipelines must handle errors gracefully

3. **Performance Constraints**
    * Must efficiently handle large OSM datasets
    * Routing calculations must be performant
    * Tile serving must be optimized for reasonable response times

## **3. Architecture Improvements**

### **3.1 Installer Architecture**

**Current State**: The installer is implemented as a monolithic script with some modularization.

**Proposed Changes**:

* Implement a plugin-based system for the installer to improve modularity
* **Rationale**: This will make it easier to add new components, maintain existing ones, and allow users to customize
  their installation.

**Implementation Steps**:

1. Create a plugin registry system in the installer
2. Refactor existing installation modules as plugins
3. Implement dependency resolution between plugins
4. Update documentation to reflect the new architecture

### **3.2 Service Architecture**

**Current State**: Services are managed individually with some interdependencies.

**Proposed Changes**:

* Complete the implementation of the services/configurators and services/installers packages
* Create a service discovery mechanism
* Implement a unified service management interface
* **Rationale**: This will improve service reliability, make the system more maintainable, and provide better visibility
  into service health.

**Implementation Steps**:

1. Define a common service interface
2. Implement service health checks
3. Create a service dependency graph
4. Develop a unified management dashboard

### **3.3 Data Processing Architecture**

**Current State**: Data processing is handled by separate components with limited standardization.

**Proposed Changes**:

* **Static Data Pipeline**: Adopt a **Pluggable ETL Processor** architecture for static transit data (GTFS, NeTEx,
  etc.). All data will be transformed and loaded into a single, standardized, and format-agnostic **Canonical Database
  Schema**. This creates a single source of truth for all static data within the PostgreSQL database.
* **Real-time Data Service**: Implement a **Pluggable Processor Architecture** for real-time transit feeds (GTFS-RT,
  SIRI, etc.). A continuously running service will ingest data, where specialized plugins transform each format into a *
  *Canonical Data Model**. This standardized data is then cached and made available through an API.
* **Rationale**: This modular, pluggable approach decouples the application's core logic from the complexity of
  individual data formats. It improves maintainability, simplifies the addition of new data sources, and ensures that
  downstream services like map rendering and APIs can consume data in a consistent, predictable way.

**Implementation Steps**:

1. Design the Canonical Database Schema for static data and the Canonical Data Model for real-time data.
2. Refactor the existing GTFS processor to be the first plugin for the new static ETL pipeline.
3. Build the core real-time service, including the orchestrator, cache, and API.
4. Develop the first real-time processor plugin for GTFS-RT.

## **4. Code Quality Improvements**

### **4.1 Testing Strategy**

**Current State**: Testing is configured but coverage may be incomplete.

**Proposed Changes**:

* Increase test coverage to at least 80% for all modules
* Implement integration tests for service interactions
* Create end-to-end tests for complete workflows
* **Rationale**: This will improve reliability, reduce regressions, and make it easier to add new features.

**Implementation Steps**:

1. Identify critical paths requiring test coverage
2. Implement unit tests for core functionality
3. Create integration tests for service interactions
4. Develop end-to-end tests for key workflows

### **4.2 Documentation Improvements**

**Current State**: Documentation exists but may be incomplete or outdated in some areas.

**Proposed Changes**:

* Create comprehensive API documentation
* Improve inline code documentation
* Create architecture diagrams
* Document data flows
* **Rationale**: This will improve developer onboarding, make the system more maintainable, and reduce support burden.

**Implementation Steps**:

1. Audit existing documentation
2. Create documentation templates
3. Generate API documentation
4. Create architecture and data flow diagrams

### **4.3 Code Organization**

**Current State**: Code organization varies across the codebase.

**Proposed Changes**:

* Standardize module and package structure
* Refactor large modules into smaller, focused ones
* Implement consistent naming conventions
* Remove duplicate code
* **Rationale**:Improve maintainability, reduce bugs, and make the codebase more approachable for new contributors.

**Implementation Steps**:

1. Define coding standards
2. Identify and refactor large modules
3. Create shared utilities for common functionality
4. Implement linting to enforce standards

## **5. Feature Improvements**

### **5.1 Installation Process**

**Current State**: Installation is now handled by two approaches:
1. The traditional Python script (`install.py`) with various options (deprecated)
2. The new Kubernetes-based installer (`install_kubernetes.py`) with interactive menu and command-line options (recommended)

**Completed Changes**:

* ✓ Implemented a Kubernetes-based deployment approach using Kustomize
* ✓ Created an interactive menu-driven installation interface
* ✓ Added support for different environments (local, production)
* ✓ Implemented progress reporting and verbose/debug modes
* ✓ Added ability to create custom Debian installer images for AMD64 and Raspberry Pi

**Proposed Future Changes**:

* Implement a rollback mechanism for failed installations
* Create a full web-based installation UI
* Add support for additional non-Debian distributions
* **Rationale**: Further improve user experience, reduce installation failures, and broaden the potential user base.

**Implementation Steps**:

1. Enhance the Kubernetes installer with additional rollback capabilities
2. Develop a web frontend for the existing Kubernetes installer
3. Extend platform support beyond Debian-based systems

### **5.2 Transit Data Processing**

**Current State**: Basic GTFS processing is implemented.

**Proposed Changes**:

* **Static Data Pipeline**: Execute the phased development plan to refactor the GTFS processor as the first plugin in
  the new ETL framework. Following this, expand capabilities by building new processor plugins for other standards like
  NeTEx and TransXchange.
* **Real-time Data Service**: Build and launch the new real-time service. The first implementation will focus on
  creating a processor for GTFS-RT Vehicle Positions and integrating it end-to-end with the frontend map. Subsequent
  phases will add plugins for other real-time formats like SIRI.
* **Rationale**: This will greatly enhance the server's capabilities by supporting a wide range of static and real-time
  transit data, providing users with a much richer and more dynamic map.

**Implementation Steps**:

1. Implement the Canonical Database Schema for static schedules.
2. Develop the static ETL orchestrator and adapt the GTFS processor.
3. Define the Canonical Data Model for real-time information.
4. Build the real-time service orchestrator, data cache, internal API, and the first GTFS-RT processor.
5. Integrate the real-time API with the frontend map.

### **5.3 Mapping and Routing**

**Current State**: Basic mapping and routing functionality is implemented.

**Proposed Changes**:

* Support additional routing profiles
* Implement traffic-aware routing
* Add support for custom map styles
* Implement advanced routing features, including static routing
* **Rationale**: Improve routing quality, provide more options for users, and make the system more competitive with
  commercial offerings.

**Implementation Steps**:

1. Add support for walking, cycling profiles
2. Implement historical traffic data integration
3. Create a map style editor
4. Add support for turn restrictions and other advanced features

## **6. DevOps Improvements**

### **6.1 CI/CD Pipeline**

**Current State**: Basic CI/CD is configured, and containerization support has been implemented through the Kubernetes installer.

**Completed Changes**:

* ✓ Implemented containerization support through the Kubernetes-based deployment
* ✓ Added ability to build OCI-compliant container images
* ✓ Created deployment automation through the Kubernetes installer

**Proposed Future Changes**:

* Implement automated testing in CI pipeline
* Add static code analysis
* Enhance automated deployment with GitOps practices
* Expand container registry integration
* **Rationale**: Further improve code quality, reduce deployment errors, and make it easier to contribute to the project.

**Implementation Steps**:

1. Configure automated testing in CI
2. Add static analysis tools
3. Implement GitOps workflow for Kubernetes deployments
4. Enhance container image building and publishing pipeline

### **6.2 Monitoring and Observability**

**Current State**: Limited monitoring capabilities.

**Proposed Changes**:

* Implement centralized logging
* Add metrics collection
* Create dashboards
* Implement alerting
* **Rationale**: Improve system reliability, make it easier to diagnose issues, and reduce downtime.

**Implementation Steps**:

1. Implement structured logging
2. Add metrics collection
3. Create monitoring dashboards
4. Configure alerting for critical issues

## **7. Security Improvements**

**Current State**: Basic security measures are in place.

**Proposed Changes**:

* Implement proper authentication and authorization
* Add HTTPS support by default
* Implement rate limiting
* Add security headers
* Implement security scanning
* **Rationale**: Protect user data, prevent abuse, and ensure compliance with security best practices.

**Implementation Steps**:

1. Design authentication system
2. Configure HTTPS by default
3. Implement rate limiting for APIs
4. Add security headers to HTTP responses
5. Configure security scanning in CI

## **8. Performance Improvements**

**Current State**: Performance optimizations may be incomplete, but the foundation for horizontal scaling has been established with the Kubernetes-based deployment.

**Completed Changes**:

* ✓ Added support for horizontal scaling through the Kubernetes architecture
* ✓ Implemented containerization to enable better resource isolation and management
* ✓ Created the foundation for distributed deployments across multiple nodes

**Proposed Future Changes**:

* Optimize database queries
* Implement caching strategies
* Optimize tile rendering
* Implement parallel processing for data operations
* Enhance Kubernetes resource management
* **Rationale**: Further improve user experience, reduce resource usage, and allow the system to handle larger datasets.

**Implementation Steps**:

1. Identify performance bottlenecks in the current deployment
2. Optimize critical database queries
3. Implement caching for frequently accessed data
4. Add parallel processing for data imports
5. Fine-tune Kubernetes resource requests and limits
6. Implement horizontal pod autoscaling for key components

## **9. Implementation Roadmap**

The improvements outlined above should be prioritized as follows:

1. **Short-term (1-3 months)**
    * **Data Architecture (Static Pipeline Foundation)**: Define the Canonical Database Schema. Refactor the existing
      GTFS pipeline to function as the first plugin, loading data into the new canonical tables. Build the ETL
      orchestrator script to manage the process.
    * **Installer & Code Quality** ✓: Implemented the Kubernetes-based installer architecture with `install_kubernetes.py`, 
      providing a modular approach using Kustomize. Continue to improve testing, documentation, and code organization.

2. **Medium-term (3-6 months)**
    * **Data Architecture (Real-time Service Foundation)**: Define and finalize the Canonical Data Model for real-time
      information. Build the core service components: the Orchestrator, Processor Interface, Data Cache, and internal
      API.
    * **Data Architecture (First End-to-End Implementation)**: Build the first processor plugin for GTFS-RT Vehicle
      Positions. Integrate the real-time API with the frontend, configure the Nginx proxy, and update the map's
      JavaScript to display the data.
    * **System Improvements**: Implement service architecture improvements, create monitoring and observability
      infrastructure, and implement security hardening.
    * **Data Consumers**: Update downstream services, such as the `pg_tileserv` configuration, to query the new
      canonical static data tables.

3. **Long-term (6-12 months)**
    * **Data Architecture (Expansion)**: Iteratively develop and add new processor plugins for other data formats (SIRI,
      NeTEx, TransXchange, etc.) as required, for both the real-time and static data pipelines.
    * **Feature & UI Development**: Develop advanced routing features. ✓ Basic installation UI implemented via the 
      interactive menu in `install_kubernetes.py`; continue to enhance with a full web-based interface.
    * **Scalability** ✓: Implemented foundation for horizontal scaling through the Kubernetes architecture. Continue to 
      enhance with fine-tuned resource management and autoscaling.
    * **Platform Support** ✓: Added support for AMD64 and Raspberry Pi platforms through custom Debian installer images. 
      Continue to expand to additional platforms.

This roadmap balances immediate needs with long-term goals and considers the dependencies between different
improvements.

## **10. Conclusion**

The Open Journey Planner Server project has a solid foundation but can benefit significantly from the improvements outlined in this
plan. By focusing on a modular and canonical data architecture, while also improving code quality, features, DevOps,
security, and performance, the project can become more robust, maintainable, and user-friendly.

Implementation should proceed incrementally, with regular feedback from users and contributors to ensure that the
improvements meet the needs of the community.
