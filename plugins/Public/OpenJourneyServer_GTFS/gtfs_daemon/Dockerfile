FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    pandas \
    requests \
    gtfs-kit \
    psycopg2-binary \
    lxml

# Create app directory
WORKDIR /app

# Copy GTFS daemon files
COPY gtfs_daemon.py /app/
COPY GTFSToOpenJourney.py /app/
COPY config.json /app/
COPY run_daemon.py /app/

# Create a non-root user
RUN groupadd -r gtfsuser && useradd -r -g gtfsuser gtfsuser

# Set ownership and permissions
RUN chown -R gtfsuser:gtfsuser /app

# Switch to non-root user
USER gtfsuser

# Set the entrypoint
ENTRYPOINT ["python", "/app/run_daemon.py"]