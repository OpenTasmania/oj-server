# Data Processing Plugin

This plugin provides static data processing capabilities through an ETL (Extract, Transform, Load) orchestrator that handles various transit data formats.

## Features

- **Static ETL Orchestrator**: Command-line tool for processing static transit data feeds
- **Plugin Architecture**: Dynamically loads processor plugins for different data formats
- **Multi-format Support**: Handles GTFS, NeTEx, and other transit data formats through processors
- **Configuration-driven**: Reads feed configurations from YAML files
- **Dry Run Mode**: Validation and testing without actual data processing
- **Kubernetes Integration**: Containerized processing jobs with persistent storage

## What This Plugin Does

The Data Processing plugin orchestrates the extraction, transformation, and loading of static transit data from various sources. It provides a unified interface for processing different data formats through a pluggable processor architecture.

Key capabilities:
- Processes static transit feeds on-demand or scheduled basis
- Transforms data into canonical database schema
- Supports multiple data formats through processor plugins
- Provides command-line interface for manual operations
- Enables automated data refresh workflows

## Implementation

### Core Components

- **Static ETL Orchestrator** (`run_static_etl.py`): Main command-line tool
- **Processor Registry**: Dynamic loading and management of data processors
- **Configuration Manager**: YAML-based feed configuration
- **Plugin Loader**: Automatic discovery of processor plugins

### Architecture

```
Configuration → ETL Orchestrator → Processor Registry → Data Processors
                      ↓
              Extract → Transform → Load → Database
```

### Static ETL Orchestrator

The main script `run_static_etl.py` provides comprehensive ETL orchestration:

- Reads feed configurations from `config.yaml`
- Discovers and loads processor plugins automatically
- Executes ETL pipeline for configured feeds
- Supports dry-run mode for validation
- Provides detailed logging and error handling

## How to Use

### Command-Line Interface

The orchestrator provides several command-line options:

```bash
# Process all enabled feeds
python run_static_etl.py

# Process a specific feed
python run_static_etl.py --feed FEED_NAME

# Dry run (validate without processing)
python run_static_etl.py --dry-run

# List configured feeds
python run_static_etl.py --list-feeds

# List available processors
python run_static_etl.py --list-processors

# Use custom config file
python run_static_etl.py --config /path/to/config.yaml

# Enable verbose logging
python run_static_etl.py --verbose
```

### Configuration

Configure static feeds in your YAML configuration file:

```yaml
static_feeds:
  - name: "GTFS_Feed"
    type: "gtfs"
    source: "https://example.com/gtfs.zip"
    enabled: true
    schedule: "daily"
    description: "Transit agency GTFS feed"
  
  - name: "NeTEx_Feed"
    type: "netex"
    source: "https://example.com/netex.xml"
    enabled: true
    schedule: "weekly"
    description: "Transit agency NeTEx feed"
```

### Kubernetes Deployment

The plugin supports containerized processing through Kubernetes Jobs:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: data-processing-job
spec:
  template:
    spec:
      containers:
        - name: data-processor
          image: data-processing
          command: ["python", "/app/run_static_etl.py"]
          args: ["--config", "/app/config.yaml"]
```

### Scheduled Processing

Deploy as a CronJob for automated data refresh:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: static-etl-cronjob
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: static-etl
            image: data-processing
            command: ["python", "/app/run_static_etl.py"]
```

## Processor Integration

The plugin uses a processor interface for handling different data formats:

### Supported Processors

- **GTFS Processor**: Handles General Transit Feed Specification data
- **NeTEx Processor**: Processes Network Timetable Exchange format
- **Custom Processors**: Extensible architecture for additional formats

### Processor Discovery

Processors are automatically discovered from:
```
plugins/Public/*/processors/*_processor.py
```

Each processor must implement the `ProcessorInterface` with methods:
- `extract()`: Read data from source
- `transform()`: Convert to canonical format
- `load()`: Store in database

## Data Pipeline

### Extract Phase
- Downloads data from configured sources
- Handles various formats (ZIP, XML, JSON)
- Validates data integrity and format

### Transform Phase
- Converts data to canonical database schema
- Applies data quality checks and validation
- Handles data normalization and cleanup

### Load Phase
- Inserts/updates data in PostgreSQL database
- Manages database transactions and rollbacks
- Provides conflict resolution and data merging

## Performance Considerations

- **Parallel Processing**: Multiple feeds can be processed concurrently
- **Memory Management**: Efficient handling of large datasets
- **Database Optimization**: Bulk operations and transaction management
- **Error Recovery**: Retry logic and graceful error handling

## Troubleshooting

### Common Issues

1. **Configuration Errors**
   - Verify YAML syntax and feed configurations
   - Check source URL accessibility
   - Validate processor availability

2. **Processing Failures**
   - Review processor logs for specific errors
   - Check database connectivity and permissions
   - Verify data format compliance

3. **Performance Issues**
   - Monitor memory usage during processing
   - Check database query performance
   - Review network connectivity for remote sources

### Debugging

Enable verbose logging:
```bash
python run_static_etl.py --verbose
```

Use dry-run mode for testing:
```bash
python run_static_etl.py --dry-run
```

Check processor registration:
```bash
python run_static_etl.py --list-processors
```

## Dependencies

- Python 3.8+
- PostgreSQL with PostGIS
- Required Python packages:
  - `pyyaml` - Configuration file parsing
  - `psycopg2` - PostgreSQL connectivity
  - `requests` - HTTP data fetching
  - Format-specific packages (loaded by processors)

## File Structure

```
plugins/Public/OpenJourneyServer_Dataprocessing/
├── plugin.py                  # Main plugin implementation
├── run_static_etl.py         # Static ETL orchestrator script
├── kubernetes/               # Kubernetes deployment manifests
│   ├── job.yaml             # Processing job definition
│   ├── pvc.yaml             # Persistent volume claims
│   └── kustomization.yaml   # Kustomize configuration
└── README.md                # This documentation
```

## Integration Examples

### Manual Processing
```bash
# Process all feeds
python run_static_etl.py

# Process specific feed with verbose output
python run_static_etl.py --feed GTFS_Feed --verbose
```

### Automated Workflows
```bash
# CI/CD pipeline integration
python run_static_etl.py --config production.yaml --dry-run
python run_static_etl.py --config production.yaml
```

### Monitoring Integration
```bash
# Health check script
python run_static_etl.py --list-feeds | grep "enabled"
```