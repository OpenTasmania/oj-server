# OpenJourney Server Architecture Documentation

This document provides comprehensive architecture diagrams and documentation for the OpenJourney Server's data
processing pipelines.

## Overview

The OpenJourney Server implements a pluggable, microservices-based architecture for processing both static and real-time
transit data. The system is designed around two main data pipelines:

1. **Static ETL Pipeline** - Processes static transit data (GTFS, NeTEx) into a canonical database schema

## Static ETL Pipeline Architecture

The Static ETL Pipeline is responsible for processing static transit data feeds and transforming them into a canonical
database schema.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Static ETL Pipeline                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐    ┌──────────────────────────────────────────────────┐   │
│  │   config.yaml   │    │              Static ETL Orchestrator             │   │
│  │                 │    │                                                  │   │
│  │ static_feeds:   │───▶│  • Reads configuration                          │   │
│  │ - ACT_GTFS      │    │  • Loads processor plugins dynamically          │   │
│  │   type: gtfs    │    │  • Manages ETL workflow                         │   │
│  │   source: URL   │    │  • Handles scheduling and execution             │   │
│  │   enabled: true │    │                                                  │   │
│  └─────────────────┘    └──────────────────┬───────────────────────────────┘   │
│                                            │                                   │
│                                            ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    Processor Interface                                  │   │
│  │                                                                         │   │
│  │  Abstract Base Class defining:                                         │   │
│  │  • extract(source_path) → raw_data                                     │   │
│  │  • transform(raw_data) → canonical_data                                │   │
│  │  • load(canonical_data) → database                                     │   │
│  │  • validate_source(), get_source_info(), cleanup()                    │   │
│  └─────────────────────┬───────────────────────────────────────────────────┘   │
│                        │                                                       │
│                        ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    Processor Registry                                   │   │
│  │                                                                         │   │
│  │  • Dynamic plugin discovery and loading                                │   │
│  │  • Processor registration and retrieval                                │   │
│  │  • Format-based processor matching                                     │   │
│  └─────────────────────┬───────────────────────────────────────────────────┘   │
│                        │                                                       │
│                        ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    Data Processors (Plugins)                           │   │
│  │                                                                         │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │   │
│  │  │   GTFS Plugin   │  │  NeTEx Plugin   │  │  Future Plugin  │        │   │
│  │  │                 │  │   (Planned)     │  │   (Extensible)  │        │   │
│  │  │ • Extract ZIP   │  │ • Extract XML   │  │ • Custom Logic  │        │   │
│  │  │ • Parse GTFS    │  │ • Parse NeTEx   │  │ • Any Format    │        │   │
│  │  │ • Transform to  │  │ • Transform to  │  │ • Transform to  │        │   │
│  │  │   Canonical     │  │   Canonical     │  │   Canonical     │        │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘        │   │
│  └─────────────────────┬───────────────────────────────────────────────────┘   │
│                        │                                                       │
│                        ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                 Canonical Database Schema                               │   │
│  │                                                                         │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │   │
│  │  │ transport_stops │  │transport_routes │  │transport_trips  │        │   │
│  │  │                 │  │                 │  │                 │        │   │
│  │  │ • stop_id       │  │ • route_id      │  │ • trip_id       │        │   │
│  │  │ • stop_name     │  │ • route_name    │  │ • route_id      │        │   │
│  │  │ • location      │  │ • route_type    │  │ • service_id    │        │   │
│  │  │ • geometry      │  │ • geometry      │  │ • schedule      │        │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘        │   │
│  │                                                                         │   │
│  │  ┌─────────────────┐  ┌─────────────────┐                              │   │
│  │  │transport_shapes │  │transport_schedule│                             │   │
│  │  │                 │  │                 │                              │   │
│  │  │ • shape_id      │  │ • trip_id       │                              │   │
│  │  │ • geometry      │  │ • stop_sequence │                              │   │
│  │  │ • sequence      │  │ • arrival_time  │                              │   │
│  │  └─────────────────┘  └─────────────────┘                              │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. Static ETL Orchestrator

- **Location**: `plugins/Public/OpenJourneyServer_Dataprocessing/run_static_etl.py`
- **Purpose**: Main entry point for static data processing
- **Responsibilities**:
    - Load configuration from `config.yaml`
    - Discover and load processor plugins
    - Execute ETL workflows for configured feeds
    - Handle scheduling and error management
    - Support dry-run mode for testing

#### 2. Processor Interface

- **Location**: `common/processor_interface.py`
- **Purpose**: Abstract base class defining the contract for all data processors
- **Key Methods**:
    - `extract()`: Download and extract data from source
    - `transform()`: Convert raw data to canonical format
    - `load()`: Insert transformed data into database
    - `validate_source()`: Verify data source integrity
    - `cleanup()`: Remove temporary files

#### 3. Processor Registry

- **Purpose**: Dynamic plugin management system
- **Responsibilities**:
    - Discover processor plugins at runtime
    - Register and manage processor instances
    - Match processors to data sources by format
    - Provide processor lookup and listing capabilities

#### 4. Data Processors (Plugins)

- **Current**: GTFS processor (implemented)
- **Planned**: NeTEx processor
- **Architecture**: Pluggable system allowing easy addition of new data formats

#### 5. Canonical Database Schema

- **Purpose**: Standardized database schema for all transit data
- **Tables**:
    - `transport_stops`: Transit stops and stations
    - `transport_routes`: Transit routes and lines
    - `transport_trips`: Individual trip instances
    - `transport_shapes`: Route geometries
    - `transport_schedule`: Stop times and schedules

### Data Flow

1. **Configuration Loading**: Orchestrator reads `static_feeds` from `config.yaml`
2. **Plugin Discovery**: Registry discovers and loads available processors
3. **Source Processing**: For each enabled feed:
    - Processor extracts data from source URL
    - Raw data is transformed to canonical format
    - Canonical data is loaded into database
4. **Validation**: Data integrity checks and cleanup
5. **Scheduling**: Process runs on configured schedule (daily, etc.)

---

## System Integration

### Database Integration

- **Static Data**: Stored in PostgreSQL with PostGIS extensions
- **Real-time Data**: Cached in memory, optionally persisted for analytics
- **Canonical Schema**: Unified data model for both static and real-time data

### Service Architecture

- **Microservices**: Each pipeline runs as independent service
- **Kubernetes**: Container orchestration for scalability
- **Nginx**: Reverse proxy for API gateway functionality
- **Monitoring**: Prometheus metrics and centralized logging

### Configuration Management

- **Single Config**: `config.yaml` contains all pipeline configurations
- **Environment Variables**: Override config values for different environments
- **Validation**: Pydantic models ensure configuration integrity

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            Kubernetes Cluster                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        Ingress Controller                               │   │
│  │                                                                         │   │
│  │  • SSL Termination                                                     │   │
│  │  • Load Balancing                                                      │   │
│  │  • Request Routing                                                     │   │
│  └─────────────────────┬───────────────────────────────────────────────────┘   │
│                        │                                                       │
│                        ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        Nginx Service                                    │   │
│  │                                                                         │   │
│  │  • Reverse Proxy                                                       │   │
│  │  • Static File Serving                                                 │   │
│  │  • API Gateway                                                         │   │
│  └─────────────────────┬───────────────────────────────────────────────────┘   │
│                        │                                                       │
│           ┌────────────┼────────────┐                                          │
│           ▼            ▼            ▼                                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                             │
│  │Static ETL   │ │Real-time    │ │Frontend     │                             │
│  │Service      │ │Service      │ │Service      │                             │
│  │             │ │             │ │             │                             │
│  │• CronJob    │ │• Deployment │ │• Static     │                             │
│  │• Scheduled  │ │• Always On  │ │• Files      │                             │
│  │• Batch      │ │• Polling    │ │• SPA        │                             │
│  └─────────────┘ └─────────────┘ └─────────────┘                             │
│           │            │                                                      │
│           └────────────┼──────────────────────────────────────────────────┐   │
│                        ▼                                                  │   │
│  ┌─────────────────────────────────────────────────────────────────────┐ │   │
│  │                    PostgreSQL Database                              │ │   │
│  │                                                                     │ │   │
│  │  • PostGIS Extensions                                              │ │   │
│  │  • Canonical Schema                                                │ │   │
│  │  • Persistent Volume                                               │ │   │
│  │  • Backup & Recovery                                               │ │   │
│  └─────────────────────────────────────────────────────────────────────┘ │   │
│                                                                          │   │
│  ┌─────────────────────────────────────────────────────────────────────┐ │   │
│  │                    Monitoring Stack                                 │ │   │
│  │                                                                     │ │   │
│  │  • Prometheus (Metrics)                                            │ │   │
│  │  • Grafana (Dashboards)                                            │ │   │
│  │  • Loki (Logging)                                                  │ │   │
│  └─────────────────────────────────────────────────────────────────────┘ │   │
└──────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Future Enhancements

### Planned Features

1. **Additional Data Sources**: NeTEx, SIRI, etc., processors
2. **Analytics**: Historical data analysis and reporting
3. **Monitoring**: Comprehensive observability stack
4. **UI Improvements**: Enhanced installation and management interfaces

### Scalability Considerations

- **Horizontal Scaling**: Multiple processor instances
- **Caching Strategies**: Redis for distributed caching
- **Database Optimization**: Read replicas and partitioning
- **CDN Integration**: Static asset delivery optimization

---

*This architecture documentation is maintained as part of Task 2 and will be updated as the system evolves.*