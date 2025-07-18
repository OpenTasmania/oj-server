# GTFS to OpenJourney Daemon Implementation

This document describes the implementation of the GTFS to OpenJourney daemon as a repeating job in the Kubernetes cluster. The daemon regularly imports GTFS feeds from configured URLs and inserts them into the OpenJourney PostgreSQL database.

## Overview

The GTFS daemon is implemented as a Kubernetes CronJob that:

- **Downloads GTFS feeds** from configured URLs
- **Converts GTFS data** to OpenJourney format
- **Stores data** in the PostgreSQL database with OpenJourney schema
- **Runs regularly** on a configurable schedule (default: every 6 hours)
- **Handles failures** with retry logic and exponential backoff
- **Maintains data integrity** with upsert operations

## Architecture

### Components

1. **GTFS Daemon Container** (`gtfs-daemon:latest`)
   - Python-based application
   - Uses `gtfs-kit` for GTFS parsing
   - PostgreSQL integration with `psycopg2`
   - Configurable via environment variables and config files

2. **Kubernetes CronJob** (`gtfs-daemon-cronjob`)
   - Scheduled execution (default: `0 */6 * * *` - every 6 hours)
   - Resource limits and requests
   - Failure handling and history retention

3. **Configuration Management**
   - ConfigMap for GTFS feed URLs and settings
   - Secret integration for database credentials
   - Environment variable overrides

### Data Flow

```
GTFS URLs → Download → Parse → Convert → PostgreSQL (OpenJourney Schema)
```

1. **Download**: Fetch GTFS ZIP files from configured URLs
2. **Parse**: Extract and parse GTFS files using gtfs-kit
3. **Convert**: Transform GTFS data to OpenJourney format
4. **Store**: Insert/update data in PostgreSQL with spatial support

## Configuration

### GTFS Feed Configuration

The daemon is configured via a JSON configuration file and environment variables:

```json
{
  "feeds": [
    {
      "name": "ACT Transport",
      "url": "https://www.transport.act.gov.au/googletransit/google_transit.zip",
      "description": "Australian Capital Territory public transport GTFS feed"
    },
    {
      "name": "Tasmania Transport", 
      "url": "https://www.transport.tas.gov.au/gtfs/import/general_transit_feed.zip",
      "description": "Tasmania public transport GTFS feed"
    }
  ],
  "log_level": "INFO",
  "max_retries": 3,
  "retry_delay": 60
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_HOST` | `postgres-service` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `openjourney` | Database name |
| `POSTGRES_USER` | `postgres` | Database user |
| `POSTGRES_PASSWORD` | - | Database password (from secret) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `MAX_RETRIES` | `3` | Maximum retry attempts |
| `RETRY_DELAY` | `60` | Base retry delay in seconds |
| `GTFS_URLS` | - | Comma-separated GTFS URLs (alternative to config file) |

### Schedule Configuration

The CronJob schedule can be modified in `cronjob.yaml`:

```yaml
spec:
  # Examples:
  schedule: "0 */6 * * *"    # Every 6 hours
  schedule: "0 2 * * *"      # Daily at 2 AM
  schedule: "0 2 * * 1"      # Weekly on Monday at 2 AM
  schedule: "0 2 1 * *"      # Monthly on 1st at 2 AM
```

## Database Integration

### OpenJourney Schema Mapping

The daemon maps GTFS data to the OpenJourney database schema:

| GTFS File | OpenJourney Table | Key Mappings |
|-----------|-------------------|--------------|
| `agency.txt` | `openjourney.data_sources` | agency_id → source_id |
| `routes.txt` | `openjourney.routes` | route_id → route_id |
| `stops.txt` | `openjourney.stops` | stop_id → stop_id, coordinates → PostGIS geometry |
| `calendar.txt` | `openjourney.temporal_data` | service_id → service_id |
| `trips.txt` + `stop_times.txt` | `openjourney.segments` | Generated from trip sequences |

### Data Operations

- **Upsert Logic**: Uses `ON CONFLICT DO UPDATE` for data consistency
- **Spatial Data**: Converts lat/lon coordinates to PostGIS POINT geometry
- **Timestamps**: Automatic `created_at` and `updated_at` tracking
- **Foreign Keys**: Maintains referential integrity between tables

## Deployment

### Building the Container

```bash
# Build the GTFS daemon container
cd kubernetes/components/gtfs_daemon
docker build -t gtfs-daemon:latest .
```

### Deploying to Kubernetes

```bash
# Deploy the entire stack including GTFS daemon
kubectl apply -k kubernetes/overlays/production/

# Or deploy just the GTFS daemon component
kubectl apply -k kubernetes/components/gtfs_daemon/
```

### Verifying Deployment

```bash
# Check CronJob status
kubectl get cronjobs

# Check recent job runs
kubectl get jobs

# View logs from latest job
kubectl logs -l app=gtfs-daemon --tail=100

# Check database for imported data
kubectl exec -it deployment/postgres-deployment -- psql -U postgres -d openjourney -c "SELECT COUNT(*) FROM openjourney.routes;"
```

## Monitoring and Troubleshooting

### Monitoring

1. **CronJob Status**
   ```bash
   kubectl describe cronjob gtfs-daemon-cronjob
   ```

2. **Job History**
   ```bash
   kubectl get jobs --selector=app=gtfs-daemon
   ```

3. **Pod Logs**
   ```bash
   kubectl logs -l app=gtfs-daemon --tail=100 -f
   ```

4. **Database Verification**
   ```sql
   -- Check data freshness
   SELECT source_name, updated_at FROM openjourney.data_sources ORDER BY updated_at DESC;
   
   -- Check record counts
   SELECT 
     (SELECT COUNT(*) FROM openjourney.routes) as routes,
     (SELECT COUNT(*) FROM openjourney.stops) as stops,
     (SELECT COUNT(*) FROM openjourney.segments) as segments;
   ```

### Common Issues

#### 1. Download Failures
- **Symptoms**: "Error downloading GTFS feed" in logs
- **Solutions**: 
  - Check URL accessibility
  - Verify network policies allow HTTPS egress
  - Check for temporary service outages

#### 2. Database Connection Issues
- **Symptoms**: "Error writing to PostgreSQL" in logs
- **Solutions**:
  - Verify PostgreSQL service is running
  - Check database credentials in secret
  - Ensure network policy allows database access

#### 3. Parsing Errors
- **Symptoms**: "Error converting GTFS data" in logs
- **Solutions**:
  - Check GTFS feed validity
  - Review gtfs-kit compatibility
  - Examine specific error messages

#### 4. Resource Limits
- **Symptoms**: Pod OOMKilled or CPU throttling
- **Solutions**:
  - Increase memory/CPU limits in CronJob
  - Optimize processing for large feeds
  - Consider processing feeds sequentially

### Log Analysis

The daemon provides structured logging:

```
2024-01-15 10:00:01 - GTFSDaemon - INFO - Starting GTFS daemon run...
2024-01-15 10:00:02 - GTFSDaemon - INFO - Processing feed: ACT Transport
2024-01-15 10:00:05 - GTFSToOpenJourneyConverter - INFO - Converting GTFS data from /tmp/tmpxxx/gtfs_feed.zip
2024-01-15 10:00:10 - PostgreSQLOpenJourneyWriter - INFO - Writing data to OpenJourney PostgreSQL database...
2024-01-15 10:00:12 - PostgreSQLOpenJourneyWriter - INFO - Wrote 150 routes
2024-01-15 10:00:13 - PostgreSQLOpenJourneyWriter - INFO - Wrote 2500 stops
2024-01-15 10:00:15 - PostgreSQLOpenJourneyWriter - INFO - Wrote 8500 segments
2024-01-15 10:00:16 - GTFSDaemon - INFO - Successfully processed feed: ACT Transport
```

## Customization

### Adding New GTFS Feeds

1. **Via ConfigMap** (recommended):
   ```bash
   kubectl edit configmap gtfs-daemon-config
   ```
   Add new feed to the `config.json` data.

2. **Via Environment Variables**:
   ```bash
   kubectl set env cronjob/gtfs-daemon-cronjob GTFS_URLS="url1,url2,url3"
   ```

### Modifying Schedule

```bash
kubectl patch cronjob gtfs-daemon-cronjob -p '{"spec":{"schedule":"0 4 * * *"}}'
```

### Scaling Resources

```bash
kubectl patch cronjob gtfs-daemon-cronjob -p '{
  "spec": {
    "jobTemplate": {
      "spec": {
        "template": {
          "spec": {
            "containers": [{
              "name": "gtfs-daemon",
              "resources": {
                "limits": {"memory": "4Gi", "cpu": "2000m"},
                "requests": {"memory": "1Gi", "cpu": "500m"}
              }
            }]
          }
        }
      }
    }
  }
}'
```

## Security Considerations

### Network Policies

The daemon includes network policies that:
- Allow DNS resolution
- Allow HTTPS/HTTP for GTFS downloads
- Allow PostgreSQL database connections
- Deny all other traffic

### Secrets Management

- Database credentials stored in Kubernetes secrets
- No sensitive data in ConfigMaps or environment variables
- Container runs as non-root user

### Data Validation

- Input validation for GTFS data
- SQL injection prevention with parameterized queries
- Error handling to prevent data corruption

## Performance Optimization

### Resource Allocation

- **Memory**: 512Mi request, 2Gi limit (adjust based on feed sizes)
- **CPU**: 250m request, 1000m limit
- **Storage**: Temporary storage for GTFS downloads

### Processing Optimization

- Batch database operations
- Connection pooling for database access
- Parallel processing of multiple feeds
- Incremental updates where possible

## Future Enhancements

### Planned Features

1. **Real-time Updates**: Integration with GTFS-RT feeds
2. **Data Validation**: Enhanced GTFS feed validation
3. **Metrics**: Prometheus metrics for monitoring
4. **Notifications**: Slack/email notifications for failures
5. **Web UI**: Management interface for feed configuration

### Extension Points

- Custom data transformations
- Additional output formats
- Integration with other transit standards
- Machine learning for data quality assessment

## Support and Maintenance

### Regular Maintenance

1. **Monitor feed URLs** for changes or outages
2. **Review logs** for processing errors
3. **Update container images** for security patches
4. **Backup database** before major updates

### Troubleshooting Checklist

- [ ] CronJob is scheduled and active
- [ ] ConfigMap contains valid GTFS URLs
- [ ] Database credentials are correct
- [ ] Network policies allow required traffic
- [ ] Resource limits are adequate
- [ ] GTFS feeds are accessible and valid

## Conclusion

The GTFS to OpenJourney daemon provides a robust, scalable solution for regularly importing transit data into the OpenJourney database. With proper configuration and monitoring, it ensures that the system maintains up-to-date transit information from multiple sources.

For questions or support, please refer to the project documentation or contact the development team.