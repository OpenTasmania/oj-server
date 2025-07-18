# pgAgent Job Scheduler Plugin

This plugin provides pgAgent for PostgreSQL job scheduling and automated database maintenance tasks.

## Features

- **Job Scheduling**: Schedule and execute database jobs and maintenance tasks
- **Automated Maintenance**: Database backup, vacuum, reindex, and cleanup operations
- **SQL Job Execution**: Execute SQL scripts and stored procedures on schedule
- **Multi-step Jobs**: Support for complex jobs with multiple steps and dependencies
- **Error Handling**: Retry logic and error notification for failed jobs
- **Logging**: Comprehensive job execution logging and history
- **Kubernetes Integration**: Containerized deployment with persistent scheduling

## What This Plugin Does

The pgAgent plugin provides a robust job scheduling system for PostgreSQL databases. It enables automated execution of
database maintenance tasks, data processing jobs, and custom SQL operations on configurable schedules.

Key capabilities:

- Schedule recurring database maintenance tasks
- Execute SQL scripts and stored procedures automatically
- Perform database backups and cleanup operations
- Run data processing and ETL jobs
- Monitor job execution and handle failures
- Provide job history and performance tracking
- Support complex multi-step job workflows

## Implementation

### Core Components

- **pgAgent Extension**: PostgreSQL extension for job scheduling
- **Job Scheduler**: Background process that monitors and executes jobs
- **Job Database**: pgagent schema storing job definitions and history
- **Execution Engine**: SQL execution and error handling system
- **Logging System**: Job execution tracking and history management

### Architecture

```
Kubernetes CronJob → pgAgent Process → PostgreSQL Database
                           ↓
                    Job Execution / Logging
```

## How to Use

### Configuration

Configure pgAgent settings in your YAML configuration:

```yaml
pgagent:
  enabled: true
  db_host: "postgres-service"
  db_port: 5432
  db_name: "openjourney"
  poll_time: 10  # seconds between job checks
  retry_on_crash: "yes"
  log_level: 1   # 0=DEBUG, 1=LOG, 2=WARNING, 3=ERROR
```

### Kubernetes Deployment

The plugin automatically deploys pgAgent when the system is set up:

```bash
# Deploy pgAgent service
kubectl apply -f kubernetes/

# Check deployment status
kubectl get cronjobs pgagent-cronjob
kubectl get pods -l app=pgagent
```

### Database Setup

The plugin automatically creates the required database components:

```sql
-- pgAgent extension (created automatically)
CREATE
EXTENSION IF NOT EXISTS pgagent;

-- Verify pgagent schema exists
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name = 'pgagent';
```

## Job Management

### Creating Jobs with pgAdmin

1. **Connect to Database** using pgAdmin
2. **Navigate to pgAgent Jobs** in the browser tree
3. **Right-click and select "Create > Job..."**
4. **Configure Job Properties**:
    - General: Job name and description
    - Steps: SQL commands to execute
    - Schedules: When the job should run
    - Options: Error handling and notifications

### Creating Jobs with SQL

#### Basic Job Creation

```sql
-- Create a simple backup job
INSERT INTO pgagent.pga_job (jobjclid, jobname, jobdesc, jobhostagent, jobenabled)
VALUES (1, 'Daily Backup', 'Daily database backup job', '', true);

-- Get the job ID
SELECT jobid
FROM pgagent.pga_job
WHERE jobname = 'Daily Backup';

-- Create job step
INSERT INTO pgagent.pga_jobstep (jstjobid, jstname, jstkind, jstcode, jstdesc)
VALUES ((SELECT jobid FROM pgagent.pga_job WHERE jobname = 'Daily Backup'),
        'Backup Database',
        's', -- SQL step
        'pg_dump -h localhost -U postgres -d mydb > /backups/daily_backup.sql',
        'Create daily database backup');

-- Create schedule
INSERT INTO pgagent.pga_schedule (jscjobid, jscname, jscdesc, jscenabled, jscstart, jscminutes, jschours, jscweekdays,
                                  jscmonthdays, jscmonths)
VALUES ((SELECT jobid FROM pgagent.pga_job WHERE jobname = 'Daily Backup'),
        'Daily at 2 AM',
        'Run backup daily at 2:00 AM',
        true,
        '2024-01-01 02:00:00',
        ARRAY[false, false, true, false, false, false, false, false, false, false, false, false, false, false, false,
        false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false,
        false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false,
        false, false, false, false, false, false, false, false, false, false, false, false, false ], -- minute 2
        ARRAY[false, false, true, false, false, false, false, false, false, false, false, false, false, false, false,
        false, false, false, false, false, false, false, false, false ], -- hour 2
        ARRAY[true, true, true, true, true, true, true ], -- all weekdays
        ARRAY[true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true,
        true, true, true, true, true, true, true, true, true, true, true, true, true, true, true ], -- all month days
        ARRAY[true, true, true, true, true, true, true, true, true, true, true, true ] -- all months
       );
```

### Common Job Types

#### Database Maintenance Jobs

```sql
-- Vacuum and analyze job
INSERT INTO pgagent.pga_jobstep (jstjobid, jstname, jstkind, jstcode, jstdesc)
VALUES (job_id,
        'Vacuum and Analyze',
        's',
        'VACUUM ANALYZE;',
        'Vacuum and analyze all tables');

-- Reindex job
INSERT INTO pgagent.pga_jobstep (jstjobid, jstname, jstkind, jstcode, jstdesc)
VALUES (job_id,
        'Reindex Tables',
        's',
        'REINDEX DATABASE mydb;',
        'Rebuild all indexes');
```

#### Data Processing Jobs

```sql
-- ETL processing job
INSERT INTO pgagent.pga_jobstep (jstjobid, jstname, jstkind, jstcode, jstdesc)
VALUES (job_id,
        'Process Daily Data',
        's',
        'CALL process_daily_data();',
        'Execute daily data processing procedure');

-- Data cleanup job
INSERT INTO pgagent.pga_jobstep (jstjobid, jstname, jstkind, jstcode, jstdesc)
VALUES (job_id,
        'Cleanup Old Data',
        's',
        'DELETE FROM logs WHERE created_at < NOW() - INTERVAL ''30 days'';',
        'Remove logs older than 30 days');
```

#### Backup Jobs

```sql
-- Database backup job
INSERT INTO pgagent.pga_jobstep (jstjobid, jstname, jstkind, jstcode, jstdesc)
VALUES (job_id,
        'Create Backup',
        'b', -- batch step
        'pg_dump -h postgres-service -U postgres -d mydb | gzip > /backups/backup_$(date +%Y%m%d).sql.gz',
        'Create compressed database backup');
```

## Job Scheduling

### Schedule Patterns

pgAgent supports flexible scheduling patterns:

#### Time-based Schedules

```sql
-- Daily at specific time
jscminutes
: [0] (minute 0)
jschours: [2] (hour 2 = 2:00 AM)
jscweekdays: [true,true,true,true,true,true,true] (all days)

-- Weekly on specific day
jscweekdays: [false,true,false,false,false,false,false] (Monday only)

-- Monthly on specific day
jscmonthdays: [false,true,false,...] (2nd day of month)
```

#### Interval-based Schedules

```sql
-- Every 15 minutes
jscminutes
: [true,false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,false]

-- Every 6 hours
jschours: [true,false,false,false,false,false,true,false,false,false,false,false,true,false,false,false,false,false,true,false,false,false,false,false]
```

## Monitoring and Management

### Job Status Monitoring

```sql
-- View all jobs and their status
SELECT j.jobname, j.jobdesc, j.jobenabled, j.joblastrun
FROM pgagent.pga_job j
ORDER BY j.jobname;

-- View job execution history
SELECT jl.jlgid, j.jobname, jl.jlgstart, jl.jlgduration, jl.jlgstatus
FROM pgagent.pga_joblog jl
         JOIN pgagent.pga_job j ON j.jobid = jl.jlgjobid
ORDER BY jl.jlgstart DESC LIMIT 20;

-- View failed jobs
SELECT j.jobname, jl.jlgstart, jl.jlgstatus, sl.jsloutput
FROM pgagent.pga_joblog jl
         JOIN pgagent.pga_job j ON j.jobid = jl.jlgjobid
         LEFT JOIN pgagent.pga_jobsteplog sl ON sl.jsljlgid = jl.jlgid
WHERE jl.jlgstatus != 's'
ORDER BY jl.jlgstart DESC;
```

### Job Management Operations

```sql
-- Enable/disable jobs
UPDATE pgagent.pga_job
SET jobenabled = false
WHERE jobname = 'Job Name';
UPDATE pgagent.pga_job
SET jobenabled = true
WHERE jobname = 'Job Name';

-- Delete job (cascades to steps and schedules)
DELETE
FROM pgagent.pga_job
WHERE jobname = 'Job Name';

-- Clear job history
DELETE
FROM pgagent.pga_joblog
WHERE jlgstart < NOW() - INTERVAL '30 days';
```

## Troubleshooting

### Common Issues

1. **Jobs Not Running**
    - Check pgAgent process status: `kubectl get pods -l app=pgagent`
    - Verify job is enabled: `SELECT jobenabled FROM pgagent.pga_job WHERE jobname = 'Job Name'`
    - Check schedule configuration
    - Review pgAgent logs: `kubectl logs -l app=pgagent`

2. **Job Execution Failures**
    - Check job step logs: `SELECT jsloutput FROM pgagent.pga_jobsteplog WHERE jsljlgid = log_id`
    - Verify database permissions for job user
    - Check SQL syntax in job steps
    - Review error messages in job history

3. **Performance Issues**
    - Monitor job execution times
    - Check for overlapping job schedules
    - Review database resource usage during job execution
    - Consider job step optimization

4. **Database Connection Issues**
    - Verify PostgreSQL connectivity from pgAgent pod
    - Check database credentials and permissions
    - Review network connectivity
    - Ensure pgagent extension is installed

### Debugging

#### Check pgAgent Status

```bash
# View pgAgent pods
kubectl get pods -l app=pgagent

# Check pgAgent logs
kubectl logs -l app=pgagent

# Check CronJob status
kubectl get cronjobs pgagent-cronjob
```

#### Database Diagnostics

```sql
-- Check pgagent extension
SELECT *
FROM pg_extension
WHERE extname = 'pgagent';

-- Verify pgagent schema
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name = 'pgagent';

-- Check job configuration
SELECT jobid, jobname, jobenabled, joblastrun
FROM pgagent.pga_job;

-- Review recent job execution
SELECT *
FROM pgagent.pga_joblog
ORDER BY jlgstart DESC LIMIT 10;
```

## Performance Considerations

- **Job Scheduling**: Avoid overlapping resource-intensive jobs
- **Database Load**: Schedule maintenance jobs during low-usage periods
- **Log Management**: Regularly clean up old job logs to prevent table bloat
- **Resource Usage**: Monitor CPU and memory usage during job execution
- **Concurrent Jobs**: Limit number of concurrent jobs based on system capacity

## Dependencies

- **PostgreSQL**: Database server with pgagent extension
- **pgAgent Extension**: PostgreSQL extension for job scheduling
- **Kubernetes**: Container orchestration for pgAgent process
- **Database Permissions**: Appropriate permissions for job execution

## File Structure

```
plugins/Public/OpenJourneyServer_pgAgent/
├── plugin.py                  # Main plugin implementation
├── kubernetes/               # Kubernetes deployment manifests
│   ├── cronjob.yaml         # pgAgent CronJob definition
│   ├── configmap.yaml       # Configuration management
│   └── kustomization.yaml   # Kustomize configuration
└── README.md                # This documentation
```

## Integration Examples

### Automated Backup System

```sql
-- Create backup job with rotation
CREATE
OR REPLACE FUNCTION automated_backup() RETURNS void AS $$
DECLARE
backup_file text;
BEGIN
    backup_file
:= '/backups/db_backup_' || to_char(now(), 'YYYYMMDD_HH24MI') || '.sql';
    PERFORM
pg_dump('mydb', backup_file);
    
    -- Clean up old backups (keep last 7 days)
    PERFORM
system('find /backups -name "db_backup_*.sql" -mtime +7 -delete');
END;
$$
LANGUAGE plpgsql;
```

### Data Processing Pipeline

```sql
-- ETL job with error handling
CREATE
OR REPLACE FUNCTION daily_etl_process() RETURNS void AS $$
BEGIN
    -- Extract data
INSERT INTO staging_table
SELECT *
FROM source_table
WHERE updated_date = CURRENT_DATE;

-- Transform data
UPDATE staging_table
SET processed_field = transform_function(raw_field);

-- Load data
INSERT INTO target_table
SELECT *
FROM staging_table;

-- Cleanup
DELETE
FROM staging_table;

-- Log success
INSERT INTO process_log (process_name, status, timestamp)
VALUES ('daily_etl', 'success', NOW());

EXCEPTION WHEN OTHERS THEN
    -- Log error
    INSERT INTO process_log (process_name, status, error_message, timestamp) 
    VALUES ('daily_etl', 'error', SQLERRM, NOW());
    RAISE;
END;
$$
LANGUAGE plpgsql;
```

### Maintenance Schedule

```sql
-- Weekly maintenance job
CREATE
OR REPLACE FUNCTION weekly_maintenance() RETURNS void AS $$
BEGIN
    -- Vacuum and analyze
    VACUUM
ANALYZE;
    
    -- Update statistics
    ANALYZE;
    
    -- Reindex if needed
    REINDEX
DATABASE mydb;
    
    -- Log maintenance completion
INSERT INTO maintenance_log (operation, timestamp)
VALUES ('weekly_maintenance', NOW());
END;
$$
LANGUAGE plpgsql;
```