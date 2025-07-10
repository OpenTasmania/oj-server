# Use the official Apache httpd image
FROM httpd:latest

RUN apt-get update \
    && apt-get --yes upgrade \
    && apt-get --yes install libapache2-mod-tile \
    && apt-get clean \
    && apt-get --purge autoremove

# Create a non-root user and group
RUN groupadd -r apacheuser && useradd -r -g apacheuser apacheuser

# Set ownership and permissions for Apache directories
RUN chown -R apacheuser:apacheuser /usr/local/apache2/logs \
    && chmod -R 755 /usr/local/apache2/logs \
    && chown -R apacheuser:apacheuser /usr/local/apache2/htdocs \
    && chmod -R 755 /usr/local/apache2/htdocs

# Switch to non-root user
USER apacheuser

EXPOSE 8080
