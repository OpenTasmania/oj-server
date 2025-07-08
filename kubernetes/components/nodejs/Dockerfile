# Use the official Node.js image
FROM node:18-slim

# Create a non-root user and group
RUN groupadd -r nodeuser && useradd -r -g nodeuser nodeuser

# Create a directory for the application
WORKDIR /app

# Set ownership and permissions
RUN chown -R nodeuser:nodeuser /app

# Switch to non-root user
USER nodeuser

# This image can be used as a base for any Node.js-based tools
# or as a standalone container for running scripts.
CMD [ "node" ]
