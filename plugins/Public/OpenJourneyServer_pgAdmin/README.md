# pgAdmin Database Administration Plugin

This plugin provides pgAdmin web interface for PostgreSQL database management and administration.

## Features

- **Web-based Interface**: Modern web interface for PostgreSQL database administration
- **Database Management**: Complete database administration capabilities
- **Query Editor**: Advanced SQL query editor with syntax highlighting
- **Schema Browser**: Visual database schema exploration and management
- **User Management**: Database user and role administration
- **Monitoring**: Database performance monitoring and statistics
- **Kubernetes Deployment**: Containerized deployment with ingress configuration

## What This Plugin Does

The pgAdmin plugin provides a comprehensive web-based administration interface for PostgreSQL databases. It offers
database administrators and developers a powerful tool for managing databases, executing queries, monitoring
performance, and administering database users and permissions.

Key capabilities:

- Database server connection management
- SQL query execution and result visualization
- Database schema creation and modification
- Table data viewing and editing
- User and role management
- Database backup and restore operations
- Performance monitoring and query analysis
- Database maintenance and optimization tools

## Implementation

### Core Components

- **pgAdmin Web Server**: Main web application server
- **Database Connections**: PostgreSQL connection management
- **Authentication System**: User login and session management
- **Query Engine**: SQL execution and result processing
- **Configuration Management**: Server and database configuration

### Architecture

```
Web Browser → pgAdmin Web Interface → PostgreSQL Database
                     ↓
              Configuration / Session Management
```

## How to Use

### Configuration

Configure pgAdmin settings in your YAML configuration:

```yaml
pgadmin:
  enabled: true
  default_email: "admin@example.com"
  default_password: "secure_password"
  listen_port: 80
  server_mode: true
```

**Important Security Note**: Change the default credentials in production environments.

### Kubernetes Deployment

The plugin automatically deploys pgAdmin when the system is set up:

```bash
# Deploy pgAdmin service
kubectl apply -f kubernetes/

# Check deployment status
kubectl get pods -l app=pgadmin
kubectl get services pgadmin-service
```

### Accessing pgAdmin

Once deployed, pgAdmin is available through the configured ingress endpoint:

```
http://your-domain/pgadmin/
```

#### Default Login Credentials

- **Email**: `admin@openjourney.local` (configurable)
- **Password**: `admin` (configurable)

**Security Warning**: Always change default credentials in production!

### Adding Database Servers

1. **Login to pgAdmin** using the configured credentials
2. **Right-click "Servers"** in the browser tree
3. **Select "Create > Server..."**
4. **Configure connection**:
    - **Name**: Descriptive server name
    - **Host**: PostgreSQL server hostname/IP
    - **Port**: PostgreSQL port (default: 5432)
    - **Username**: Database username
    - **Password**: Database password

#### Example Server Configuration

```
General Tab:
  Name: Production Database

Connection Tab:
  Host name/address: postgres-service
  Port: 5432
  Maintenance database: postgres
  Username: postgres
  Password: your_password
```

## Database Administration Tasks

### Schema Management

#### Creating Databases

1. Right-click on server name
2. Select "Create > Database..."
3. Enter database name and configuration
4. Click "Save"

#### Managing Tables

1. Navigate to database > Schemas > public > Tables
2. Right-click for context menu options:
    - Create new table
    - View/Edit data
    - Modify table structure
    - Generate scripts

### Query Operations

#### SQL Query Editor

1. Click "Query Tool" button or press Alt+Shift+Q
2. Write SQL queries in the editor
3. Execute with F5 or Execute button
4. View results in the output panel

#### Example Queries

```sql
-- View all tables in current database
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public';

-- Check database size
SELECT pg_size_pretty(pg_database_size(current_database()));

-- View active connections
SELECT pid, usename, application_name, client_addr, state
FROM pg_stat_activity
WHERE state = 'active';
```

### User and Role Management

#### Creating Users

1. Navigate to server > Login/Group Roles
2. Right-click and select "Create > Login/Group Role..."
3. Configure user properties:
    - General: Username and comments
    - Definition: Password and connection limits
    - Privileges: Database permissions
    - Membership: Role assignments

#### Managing Permissions

```sql
-- Grant database access
GRANT
CONNECT
ON DATABASE mydb TO username;

-- Grant schema usage
GRANT USAGE ON SCHEMA
public TO username;

-- Grant table permissions
GRANT
SELECT,
INSERT
,
UPDATE,
DELETE
ON ALL TABLES IN SCHEMA public TO username;
```

## Monitoring and Maintenance

### Database Statistics

#### Performance Dashboard

1. Navigate to server > Databases > [database_name]
2. Click "Dashboard" tab
3. View real-time statistics:
    - Database size
    - Active connections
    - Transaction statistics
    - Cache hit ratios

#### Query Analysis

1. Use "Query Tool" for query execution
2. Enable "Explain" options for query plans
3. Analyze performance with EXPLAIN ANALYZE
4. Review slow query logs

### Backup and Restore

#### Creating Backups

1. Right-click on database
2. Select "Backup..."
3. Configure backup options:
    - Format (Custom, Tar, Plain)
    - Compression level
    - Include/exclude options
4. Execute backup

#### Restoring Databases

1. Right-click on server
2. Select "Restore..."
3. Choose backup file
4. Configure restore options
5. Execute restore

## Security Considerations

### Authentication

- **Change Default Credentials**: Always modify default login credentials
- **Strong Passwords**: Use complex passwords for database access
- **Limited Access**: Restrict pgAdmin access to authorized users only

### Network Security

- **HTTPS**: Configure SSL/TLS for encrypted connections
- **Firewall Rules**: Limit network access to pgAdmin interface
- **VPN Access**: Consider VPN for remote administration

### Database Connections

- **Encrypted Connections**: Use SSL for database connections
- **Limited Privileges**: Use least-privilege principle for database users
- **Connection Limits**: Configure appropriate connection limits

## Troubleshooting

### Common Issues

1. **Cannot Connect to Database**
    - Verify PostgreSQL server is running
    - Check connection parameters (host, port, credentials)
    - Ensure network connectivity
    - Review PostgreSQL pg_hba.conf configuration

2. **pgAdmin Interface Not Loading**
    - Check pgAdmin pod status: `kubectl get pods -l app=pgadmin`
    - Review pod logs: `kubectl logs -l app=pgadmin`
    - Verify ingress configuration
    - Check service endpoints

3. **Authentication Failures**
    - Verify login credentials
    - Check pgAdmin configuration
    - Review authentication logs
    - Ensure proper user permissions

4. **Performance Issues**
    - Monitor resource usage: `kubectl top pods -l app=pgadmin`
    - Check database connection limits
    - Review query performance
    - Consider connection pooling

### Debugging

#### Check pgAdmin Status

```bash
# View pgAdmin pods
kubectl get pods -l app=pgadmin

# Check pgAdmin logs
kubectl logs -l app=pgadmin

# Describe pgAdmin service
kubectl describe service pgadmin-service
```

#### Database Connection Testing

```bash
# Test PostgreSQL connectivity from pgAdmin pod
kubectl exec -it <pgadmin-pod> -- psql -h postgres-service -U postgres -d postgres
```

## Configuration Options

### Environment Variables

Common pgAdmin configuration options:

```yaml
pgadmin:
  enabled: true
  default_email: "admin@example.com"
  default_password: "secure_password"
  listen_port: 80
  server_mode: true

  # Advanced configuration
  config:
    PGADMIN_CONFIG_ENHANCED_COOKIE_PROTECTION: true
    PGADMIN_CONFIG_LOGIN_BANNER: "Database Administration"
    PGADMIN_CONFIG_CONSOLE_LOG_LEVEL: 20
    PGADMIN_CONFIG_FILE_LOG_LEVEL: 20
```

### Server Configuration

pgAdmin server configuration options:

- **Authentication**: LDAP, OAuth, internal authentication
- **SSL Configuration**: Certificate management and encryption
- **Session Management**: Timeout and security settings
- **Logging**: Log levels and output configuration

## Dependencies

- **PostgreSQL**: Target database server for administration
- **Kubernetes**: Container orchestration platform
- **Ingress Controller**: For web interface access
- **Persistent Storage**: For pgAdmin configuration and logs

## File Structure

```
plugins/Public/OpenJourneyServer_pgAdmin/
├── plugin.py                  # Main plugin implementation
├── kubernetes/               # Kubernetes deployment manifests
│   ├── deployment.yaml      # pgAdmin deployment configuration
│   ├── service.yaml         # Service definition
│   ├── configmap.yaml       # Configuration management
│   ├── ingress.yaml         # Web interface access
│   ├── pvc.yaml             # Persistent volume claims
│   └── kustomization.yaml   # Kustomize configuration
└── README.md                # This documentation
```

## Integration Examples

### Automated Database Setup

```sql
-- Create application database
CREATE
DATABASE myapp;

-- Create application user
CREATE
USER appuser WITH PASSWORD 'secure_password';

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE
myapp TO appuser;
```

### Monitoring Queries

```sql
-- Check database connections
SELECT count(*) as active_connections
FROM pg_stat_activity
WHERE state = 'active';

-- Monitor table sizes
SELECT schemaname,
       tablename,
       pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) as size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check slow queries
SELECT query, mean_time, calls, total_time
FROM pg_stat_statements
ORDER BY mean_time DESC LIMIT 10;
```

### Backup Automation

```bash
# Automated backup script
#!/bin/bash
BACKUP_DIR="/backups"
DB_NAME="myapp"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

pg_dump -h postgres-service -U postgres -d $DB_NAME > $BACKUP_DIR/backup_${DB_NAME}_${TIMESTAMP}.sql
```