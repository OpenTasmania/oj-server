# Use a Debian base image
FROM debian:bullseye-slim

# Install dependencies for renderd and mapnik
RUN apt-get update && apt-get install -y --no-install-recommends \
    renderd \
    mapnik-utils \
    osm2pgsql \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and group for running renderd
RUN groupadd -r renderuser && useradd -r -g renderuser renderuser

# Create directories for renderd socket and tile cache, and set ownership
# These directories will be mounted over by persistent volumes in Kubernetes,
# but creating them here ensures the image is runnable standalone and has correct permissions.
RUN mkdir -p /var/run/renderd /var/lib/mod_tile && \
    chown -R renderuser:renderuser /var/run/renderd /var/lib/mod_tile

# Switch to non-root user
USER renderuser

# Expose the default renderd port (optional, for clarity)
# Note: Communication will be via a shared socket volume, not typically TCP.
EXPOSE 7653

# Start renderd in the foreground
# The -f flag keeps it from daemonizing, which is standard for container entrypoints.
# The configuration will be mounted from a ConfigMap in the Kubernetes deployment.
CMD ["/usr/bin/renderd", "-f", "-c", "/etc/renderd.conf"]
