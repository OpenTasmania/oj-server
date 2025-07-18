# GTFS Plugin

This plugin provides comprehensive GTFS (General Transit Feed Specification) data processing capabilities, including
both legacy daemon-based processing and modern processor-based ETL operations.

## Features

- **GTFS Data Processing**: Complete GTFS feed parsing and database integration
- **Dual Processing Architecture**: Legacy daemon and modern processor implementations
- **Database Schema Management**: Automatic creation of GTFS and canonical database tables
- **Kubernetes Integration**: Containerized GTFS processing with CronJob scheduling
- **Data Validation**: GTFS feed validation and quality checks
- **Processor Interface**: Modern ETL processor implementing standard interface

## What This Plugin Does

The GTFS plugin handles the processing of GTFS (General Transit Feed Specification) data from transit agencies. It
provides two processing approaches: a legacy daemon for backward compatibility and a modern processor for integration
with the ETL orchestrator.

Key capabilities:

- Downloads and processes GTFS ZIP files from URLs
- Parses GTFS text files (routes, stops, trips, etc.)
- Transforms data into both legacy and canonical database schemas
- Provides scheduled processing through Kubernetes CronJobs
- Validates GTFS data compliance and quality
- Supports both batch and real-time processing workflows

## Implementation

### Core Components

- **GTFS Daemon** (`gtfs_daemon/`): Legacy processing daemon with PostgreSQL integration
- **GTFS Processor** (`processors/`): Modern ETL processor implementing ProcessorInterface
- **Database Schema**: SQL scripts for table creation and management
- **Kubernetes Manifests**: Deployment and scheduling configuration

### Architecture

```
GTFS Feed URL → Download → Parse → Transform → Database
                    ↓
              Legacy Schema / Canonical Schema
```

### Processing Approaches

#### Legacy GTFS Daemon

- Standalone daemon process
- Direct PostgreSQL integration
- Legacy `gtfs.*` schema tables
- Kubernetes CronJob deployment
- JSON-based configuration

#### Modern GTFS Processor

- Implements ProcessorInterface
- Canonical database schema
- ETL orchestrator integration
- YAML-based configuration
- Plugin architecture support

## How to Use

### Legacy Daemon Processing

The GTFS daemon runs as a scheduled Kubernetes CronJob:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: gtfs-daemon-cronjob
spec:
  schedule: "0 */6 * * *"  # Every 6 hours
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: gtfs-daemon
              image: gtfs-daemon:latest
              command: [ "python", "gtfs_daemon.py" ]
```

#### Configuration

Create a JSON configuration file:

```json
{
  "database": {
    "host": "postgres-service",
    "port": 5432,
    "database": "transit",
    "user": "gtfs_user",
    "password": "password"
  },
  "feeds": [
    {
      "name": "Transit Agency",
      "url": "https://example.com/gtfs.zip",
      "enabled": true
    }
  ],
  "processing": {
    "max_retries": 3,
    "retry_delay": 60,
    "cleanup_old_data": true
  }
}
```

#### Manual Execution

```bash
# Run daemon once
python gtfs_daemon/gtfs_daemon.py --config config.json

# Check daemon status
kubectl logs -l app=gtfs-daemon
```

### Modern Processor Integration

The GTFS processor integrates with the ETL orchestrator:

```yaml
static_feeds:
  - name: "GTFS_Feed"
    type: "gtfs"
    source: "https://example.com/gtfs.zip"
    enabled: true
    schedule: "daily"
    description: "Transit agency GTFS feed"
```

#### Usage with ETL Orchestrator

```bash
# Process GTFS feeds through orchestrator
python run_static_etl.py --feed GTFS_Feed

# List GTFS processor capabilities
python run_static_etl.py --list-processors
```

## Database Schema

### Legacy Schema (`gtfs.*`)

The plugin creates tables in the `gtfs` schema:

- `gtfs.agency` - Transit agency information
- `gtfs.routes` - Route definitions
- `gtfs.stops` - Stop locations and details
- `gtfs.trips` - Trip schedules
- `gtfs.stop_times` - Stop timing information
- `gtfs.calendar` - Service calendar
- `gtfs.calendar_dates` - Service exceptions
- `gtfs.shapes` - Route geometry (optional)
- `gtfs.fare_attributes` - Fare information (optional)
- `gtfs.fare_rules` - Fare rules (optional)

### Canonical Schema (`canonical.*`)

Modern processor creates canonical tables:

- `canonical.transport_agencies` - Agency information
- `canonical.transport_routes` - Route data
- `canonical.transport_stops` - Stop locations with PostGIS geometry
- `canonical.transport_trips` - Trip information
- `canonical.transport_stop_times` - Timing data
- `canonical.transport_shapes` - Route shapes with geometry

## Data Processing Pipeline

### Extract Phase

- Downloads GTFS ZIP files from configured URLs
- Validates ZIP file structure and contents
- Extracts and validates individual GTFS text files
- Performs basic data integrity checks

### Transform Phase

- Parses GTFS text files using gtfs-kit library
- Validates GTFS specification compliance
- Converts data types and formats
- Generates PostGIS geometry from coordinates
- Applies data quality filters and validation

### Load Phase

- Creates database tables if they don't exist
- Performs bulk data insertion with conflict resolution
- Updates existing records with new data
- Maintains referential integrity between tables
- Provides transaction rollback on errors

## GTFS Validation

The plugin performs comprehensive GTFS validation:

### Format Validation

- Required files presence check
- Column header validation
- Data type verification
- Required field validation

### Content Validation

- Geographic coordinate validation
- Date and time format checking
- Reference integrity between files
- Service calendar consistency

### Quality Checks

- Duplicate record detection
- Orphaned record identification
- Geographic bounds validation
- Schedule consistency verification

## Performance Considerations

- **Memory Usage**: Efficient processing of large GTFS files
- **Database Performance**: Bulk operations and indexing
- **Network Efficiency**: Conditional downloads based on file modification
- **Processing Time**: Parallel processing of GTFS components

## Troubleshooting

### Common Issues

1. **Download Failures**
    - Check GTFS feed URL accessibility
    - Verify network connectivity
    - Review authentication requirements

2. **Parsing Errors**
    - Validate GTFS file format compliance
    - Check for encoding issues (UTF-8 required)
    - Review file structure and required fields

3. **Database Errors**
    - Verify PostgreSQL connectivity
    - Check database permissions
    - Ensure PostGIS extension is installed

4. **Validation Failures**
    - Review GTFS specification compliance
    - Check for data quality issues
    - Validate geographic coordinates

### Debugging

#### Legacy Daemon

```bash
# Check daemon logs
kubectl logs -l app=gtfs-daemon

# Manual daemon execution with debug
python gtfs_daemon.py --config config.json --debug
```

#### Modern Processor

```bash
# Test processor with dry run
python run_static_etl.py --feed GTFS_Feed --dry-run --verbose

# Check processor registration
python run_static_etl.py --list-processors
```

## Dependencies

- **Python Packages**:
    - `gtfs-kit` - GTFS parsing and validation
    - `psycopg2` - PostgreSQL connectivity
    - `pandas` - Data manipulation
    - `requests` - HTTP downloads
    - `geopandas` - Geospatial data processing

- **Database**:
    - PostgreSQL 12+
    - PostGIS extension for geometry support

- **System**:
    - Kubernetes for containerized deployment
    - Persistent storage for data processing

## File Structure

```
plugins/Public/OpenJourneyServer_GTFS/
├── plugin.py                          # Main plugin implementation
├── gtfs_daemon/                       # Legacy daemon implementation
│   ├── gtfs_daemon.py                # Main daemon script
│   ├── cronjob.yaml                  # Kubernetes CronJob
│   └── Dockerfile                    # Container image
├── processors/                        # Modern processor implementation
│   └── gtfs_processor.py             # GTFS processor class
├── sql/                              # Database schema scripts
│   ├── create_gtfs_schema.sql        # Legacy schema creation
│   └── create_canonical_schema.sql   # Canonical schema creation
├── tests/                            # Unit tests
│   └── test_gtfs_processor.py        # Processor tests
├── init-OpenJourney-GTFS-postgis.sh  # Database initialization script
├── GTFS_Daemon_Implementation.md     # Legacy daemon documentation
├── OpenJourney_Database_Implementation.md # Database schema documentation
└── README.md                         # This documentation
```

## Integration Examples

### Scheduled Processing

```bash
# Deploy CronJob for regular updates
kubectl apply -f gtfs_daemon/cronjob.yaml
```

### Manual Processing

```bash
# Process specific GTFS feed
python run_static_etl.py --feed Transit_Agency_GTFS

# Validate GTFS feed without processing
python run_static_etl.py --feed Transit_Agency_GTFS --dry-run
```

### Database Queries

```sql
-- Get all routes for an agency
SELECT route_id, route_short_name, route_long_name
FROM gtfs.routes
WHERE agency_id = 'AGENCY_ID';

-- Find stops within a geographic area
SELECT stop_id, stop_name, stop_lat, stop_lon
FROM gtfs.stops
WHERE stop_lat BETWEEN -42.9 AND -42.8
  AND stop_lon BETWEEN 147.2 AND 147.4;
```