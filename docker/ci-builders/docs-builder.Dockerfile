# Dockerfile for the documentation generation environment
# Name this file: docs-builder.Dockerfile
FROM debian:bookworm

ENV PIPX_HOME=/opt/pipx
ENV PIPX_BIN_DIR=/usr/local/bin
ENV PATH="${PATH}:${PIPX_BIN_DIR}"

RUN DEBIAN_FRONTEND=noninteractive && \
    apt-get update -y && \
    apt-get upgrade -y && \
    apt-get dist-upgrade -y && \
    apt-get install -y --no-install-recommends \
        curl \
        git \
        python3-full \
        pipx \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN pipx install todocheck && \
    pipx install git-cliff

# Verify installations
RUN todocheck --version && \
    git-cliff --version