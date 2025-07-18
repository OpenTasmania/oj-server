# Use a Node.js base image
FROM node:18-slim

# Install carto
RUN npm install -g carto

# Create a non-root user and group
RUN groupadd -r nodeuser && useradd -r -g nodeuser nodeuser

# Set ownership for global npm directory
RUN chown -R nodeuser:nodeuser /usr/local/lib/node_modules

# Switch to non-root user
USER nodeuser

# The entrypoint will be 'carto' and arguments will be provided
# in the Kubernetes manifest to compile stylesheets.
ENTRYPOINT [ "carto" ]
