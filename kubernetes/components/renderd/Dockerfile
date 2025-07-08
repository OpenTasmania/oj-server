# Use a Debian base image
FROM debian:bullseye-slim

# Install dependencies for renderd, mapnik, and apache
RUN apt-get update && apt-get install -y --no-install-recommends \
    apache2 \
    libapache2-mod-tile \
    mapnik-utils \
    osm2pgsql \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Copy the renderd configuration. This will be mounted from a ConfigMap in Kubernetes.
COPY kubernetes/components/renderd/renderd.conf /etc/renderd.conf

# Copy the map style. This could also be mounted from a ConfigMap or an init container.
COPY kubernetes/components/renderd/mapnik-style.xml /etc/mapnik-style.xml

# Expose the Apache port
EXPOSE 80

# Start Apache and renderd
CMD ["/usr/sbin/apache2ctl", "-D", "FOREGROUND"]
