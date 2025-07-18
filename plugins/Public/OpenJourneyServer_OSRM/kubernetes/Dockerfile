# Use the official OSRM backend image
FROM osrm/osrm-backend:latest

# The container will be started with command-line arguments in the Kubernetes manifest
# to specify the OSRM data file and other options.

# Create a non-root user and group
RUN groupadd -r osrmuser && useradd -r -g osrmuser osrmuser

# Create and set permissions for data directory
RUN mkdir -p /data && chown -R osrmuser:osrmuser /data

# Switch to non-root user
USER osrmuser

# Expose the default OSRM port
EXPOSE 5000
