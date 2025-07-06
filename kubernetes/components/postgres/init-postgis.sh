#!/bin/sh
set -e

# This script is run when the container is first started.
# It installs the PostGIS extension in the database.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS postgis;
    CREATE EXTENSION IF NOT EXISTS postgis_topology;
    CREATE EXTENSION IF NOT EXISTS hstore;

    -- Grant schema privileges
    GRANT CREATE, USAGE ON SCHEMA public TO "$POSTGRES_USER";

    -- Grant privileges on existing objects created by extensions
    GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public TO "$POSTGRES_USER";
    GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO "$POSTGRES_USER";
    GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO "$POSTGRES_USER";

    -- Grant default privileges for future objects created by the user
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON TABLES TO "$POSTGRES_USER";
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO "$POSTGRES_USER";
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO "$POSTGRES_USER";
EOSQL
