# Use a Debian base image
FROM debian:bullseye-slim

# Install pgagent
RUN apt-get update && apt-get install -y --no-install-recommends pgagent && rm -rf /var/lib/apt/lists/*

# Create a non-root user and group
RUN groupadd -r pguser && useradd -r -g pguser pguser

# Create a directory for pgagent data
RUN mkdir -p /var/lib/pgagent && chown -R pguser:pguser /var/lib/pgagent

# Switch to non-root user
USER pguser

# The entrypoint will be 'pgagent'.
# Arguments will be provided in the Kubernetes manifest to connect to the database.
ENTRYPOINT [ "pgagent" ]
