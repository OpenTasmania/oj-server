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

# Create a non-root user and group
RUN groupadd -r renderuser && useradd -r -g renderuser renderuser

# Set ownership and permissions for Apache and renderd directories
RUN chown -R renderuser:renderuser /var/www/html \
    && chown -R renderuser:renderuser /var/log/apache2 \
    && chown -R renderuser:renderuser /var/run/apache2 \
    && chmod -R 755 /var/log/apache2 \
    && chmod -R 755 /var/run/apache2

# Configure Apache to run on a non-privileged port
RUN sed -i 's/Listen 80/Listen 8080/' /etc/apache2/ports.conf \
    && sed -i 's/<VirtualHost \*:80>/<VirtualHost *:8080>/' /etc/apache2/sites-available/000-default.conf

# Switch to non-root user
USER renderuser

# Expose the Apache port
EXPOSE 8080

# Start Apache and renderd
CMD ["/usr/sbin/apache2ctl", "-D", "FOREGROUND"]
