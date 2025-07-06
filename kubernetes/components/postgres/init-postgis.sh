#!/bin/sh
set -e

# This script is run when the container is first started.
# It installs the PostGIS extension in the database.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION postgis;
    CREATE EXTENSION postgis_topology;
EOSQL
