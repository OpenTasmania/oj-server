# **Instructional Manual: Architecting a Pluggable Static Transit Data Pipeline**

## **1. Introduction and Vision**

This document details the architectural design for a unified and extensible data pipeline. The vision is to enable our
application to ingest, process, and store static public transport schedule data from a wide range of industry standards,
including GTFS, NeTEx, and TransXchange.

Currently, the system includes a processor specifically for the GTFS format. This plan outlines the evolution of that
single-format pipeline into a modular, multi-format framework. This will create a single, consistent source of truth for
all static transit data, regardless of its original format, making the entire system more robust, capable, and easier to
maintain.

## **2. Core Architectural Principles**

To manage the inherent complexity of different data standards, the architecture will be founded on two guiding
principles: **Pluggable ETL Processors** and a **Canonical Database Schema**.

* **Principle 1: Pluggable ETL Processors**
  The system will move away from a format-specific design and adopt a modular architecture. We will create a collection
  of independent "ETL (Extract, Transform, Load)" processor plugins. Each plugin will be a self-contained module
  encapsulating the logic to handle one specific data standard. For example, a `GtfsProcessor` will handle GTFS feeds,
  while a `NetexProcessor` will handle NeTEx feeds. A central orchestrator will dynamically execute the correct
  processor based on a unified configuration.

* **Principle 2: The Canonical Database Schema**
  This is the cornerstone of the static data architecture. Instead of each data format defining its own set of tables,
  all data will be transformed and loaded into a single, standardized, and format-agnostic set of database tables.
  This "Canonical Database Schema" becomes the single source of truth for the application.

  By enforcing this standard, other services like `pg_tileserv` or any future data analysis tools will have a consistent
  and predictable schema to query against, without needing to understand the nuances of the original source formats.

## **3. Defining the Canonical Database Schema**

The first and most critical design task is to define the tables and columns of the Canonical Database Schema. This
schema must be generic enough to represent the core concepts of public transport schedules, such as stops, routes, and
trips, from various standards.

Conceptual examples of canonical tables include:

* **`transport_stops`**:
    * `stop_id`: A unique internal identifier.
    * `source_id`: The stop's original ID from the source file.
    * `stop_name`: The common name of the stop.
    * `geom`: The stop's location stored as a PostGIS Point geometry.
    * `stop_code`, `parent_station_id`, etc.

* **`transport_routes`**:
    * `route_id`: A unique internal identifier.
    * `source_id`: The route's original ID.
    * `route_short_name`, `route_long_name`, `route_type` (e.g., bus, rail).

* **`transport_trips`**:
    * `trip_id`: A unique internal identifier.
    * `route_id`: A foreign key to the `transport_routes` table.
    * `shape_id`: An identifier for the physical path of the trip.
    * `direction_id`, `trip_headsign`.

* **`transport_schedule`** (or `transport_stop_times`):
    * `trip_id`: Foreign key to `transport_trips`.
    * `stop_id`: Foreign key to `transport_stops`.
    * `stop_sequence`: The order of the stop within the trip.
    * `arrival_time`, `departure_time`.

* **`transport_shapes`**:
    * `shape_id`: A unique identifier for a shape.
    * `geom`: The physical path stored as a PostGIS LineString geometry.

This schema will replace the format-specific `gtfs_*` tables.

## **4. Implementation Blueprint**

This section outlines the components required to build the new ETL (Extract, Transform, Load) pipeline.

* **4.1. Configuration (`config.yaml`)**
  The configuration must be updated to support multiple static data feeds. The singular `gtfs_feed_url` should be
  replaced by a `static_feeds` list. Each entry in the list must specify its `type` so the orchestrator can select the
  correct processor.

    * **Conceptual `config.yaml` Structure:**
        ```yaml
        static_feeds:
          - id: "act_buses_gtfs"
            type: "gtfs"
            enabled: true
            url: "https://www.transport.act.gov.au/googletransit/google_transit.zip"

          - id: "uk_regional_netex"
            type: "netex"
            enabled: true
            # NeTEx/TransXchange are often large XML files, so could be a local path or URL
            path: "/opt/transit_data/uk_regional_netex.xml"
        ```

* **4.2. ETL Pipeline Architecture**
  The existing `processors/gtfs` module will serve as a template for a more generic and powerful ETL framework.

    * **The Orchestrator**: A master script (e.g., `processors/run_static_etl.py`) that serves as the entry point for
      all static data processing. It reads the `static_feeds` configuration and, for each enabled feed, executes the
      corresponding processor plugin.
    * **The Processor Interface**: An abstract base class that defines a common contract for all static ETL plugins.
      This interface will mandate the implementation of core methods like `extract`, `transform`, and `load`, ensuring
      consistent behavior across all processors.
    * **Processor Plugins**: Each plugin will be a dedicated module (e.g., `/processors/gtfs_processor`,
      `/processors/netex_processor`) that implements the Processor Interface. The primary responsibility of each plugin
      is to:
        1. **Extract**: Download or read the source data file(s).
        2. **Transform**: Parse the source data and meticulously convert it into a set of standard data structures (
           e.g., Pandas DataFrames) that exactly match the tables and columns of the **Canonical Database Schema**. This
           is the most complex step and is unique to each format.
        3. **Load**: Pass the standardized data structures to a common data loading utility, which will then insert the
           data into the canonical tables in the PostgreSQL database. The existing `processors/gtfs/load.py` can be
           evolved into this common utility.

## **5. Recommended Development Roadmap**

A phased approach is recommended to ensure a smooth transition from the current system to the new architecture.

1. **Phase 1: Schema Definition**: Design and finalize the Canonical Database Schema in PostgreSQL. This is the
   foundational step upon which all others depend.
2. **Phase 2: Refactor the GTFS Processor**: This is the most critical phase. Adapt the existing GTFS pipeline to
   function as the first official plugin. This involves modifying its transformation logic to map GTFS data to the new
   canonical tables instead of the legacy `gtfs_*` tables.
3. **Phase 3: Build the Orchestrator**: Develop the main orchestrator script that can configure and run the newly
   refactored GTFS processor plugin. At the end of this phase, the system should be able to load GTFS data into the new
   canonical schema.
4. **Phase 4: Update Data Consumers**: Modify downstream services, such as the `pg_tileserv` configuration, to query the
   new canonical tables.
5. **Phase 5: Expansion**: With the new framework fully operational and validated, begin developing additional processor
   plugins for NeTEx, TransXchange, or other formats as needed. Each new plugin will be a self-contained project that
   adheres to the established interface and targets the same canonical schema.