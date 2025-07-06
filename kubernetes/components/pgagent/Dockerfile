# Use a Debian base image
FROM debian:bullseye-slim

# Install pgagent
RUN apt-get update && apt-get install -y --no-install-recommends pgagent && rm -rf /var/lib/apt/lists/*

# The entrypoint will be 'pgagent'.
# Arguments will be provided in the Kubernetes manifest to connect to the database.
ENTRYPOINT [ "pgagent" ]
