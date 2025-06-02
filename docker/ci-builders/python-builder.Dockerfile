# Dockerfile for the main Python build environment
# Name this file: python-builder.Dockerfile
FROM debian:trixie

ENV PIPX_HOME=/opt/pipx
ENV PIPX_BIN_DIR=/usr/local/bin
ENV PATH="${PATH}:${PIPX_BIN_DIR}"

RUN DEBIAN_FRONTEND=noninteractive && \
    apt-get update -y && \
    apt-get upgrade -y && \
    apt-get dist-upgrade -y && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        python3-full \
        pipx \
        postgresql-common \
        libpq-dev \
        libpython3-dev \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN pipx install uv

# Verify uv installation
RUN uv --version