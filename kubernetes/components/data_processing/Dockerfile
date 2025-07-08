# Use a Python base image
FROM python:3.11-slim

# Install any necessary Python packages
# For example:
# RUN pip install pandas numpy

# Copy data processing scripts
COPY . /app
WORKDIR /app

# Create a non-root user and group
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set ownership and permissions
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# The entrypoint can be python, and scripts can be run as arguments.
ENTRYPOINT [ "python" ]
