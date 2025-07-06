# Use a Python base image
FROM python:3.11-slim

# Install any necessary Python packages
# For example:
# RUN pip install pandas numpy

# Copy data processing scripts
COPY . /app
WORKDIR /app

# The entrypoint can be python, and scripts can be run as arguments.
ENTRYPOINT [ "python" ]
