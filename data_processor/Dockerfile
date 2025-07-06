# Use a slim Python base image
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /app

# Copy and install Python dependencies
COPY pyproject.toml .

RUN apt-get update \
    && apt-get --yes upgrade \
    && apt-get --yes install gcc  libpq-dev \
    && apt-get clean \
    && apt-get --purge autoremove


RUN pip install --no-cache-dir uv && \
    uv pip install --no-cache-dir --system .

# Copy the necessary application code
COPY common/ ./common/
COPY installer/processors/ ./installer/processors/

# The container will be executed by a run script
COPY data_processor/run.py .
CMD ["python", "run.py"]
