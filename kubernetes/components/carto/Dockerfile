# Use a Node.js base image
FROM node:18-slim

# Install carto
RUN npm install -g carto

# The entrypoint will be 'carto' and arguments will be provided
# in the Kubernetes manifest to compile stylesheets.
ENTRYPOINT [ "carto" ]
