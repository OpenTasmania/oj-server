# Use the official upstream OCI image from Docker Hub as the base
FROM postgres:15-alpine

# The postgres image uses these environment variables to create the database and user.
# In Kubernetes, these will be set via Secrets for security.
ENV POSTGRES_DB=gis
ENV POSTGRES_USER=gis
ENV POSTGRES_PASSWORD=gis

# Copy custom initialization scripts.
# This script will be executed on first run to set up PostGIS.
COPY init-postgis.sh /docker-entrypoint-initdb.d/

# Expose the default PostgreSQL port
EXPOSE 5432
