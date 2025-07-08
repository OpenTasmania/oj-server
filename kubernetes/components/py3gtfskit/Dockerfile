# Use a Python base image
FROM python:3.11-slim

# Install py3-gtfs-kit
RUN pip install gtfs-kit

# Create a non-root user and group
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Create a directory for the application
WORKDIR /app

# Set ownership and permissions
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# This image can be used to run GTFS processing scripts.
CMD [ "python" ]
