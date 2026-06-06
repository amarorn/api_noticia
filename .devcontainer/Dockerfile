FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

USER root
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install -y --no-install-recommends \
        libcurl4-openssl-dev \
        curl \
    && apt-get clean -y && rm -rf /var/lib/apt/lists/*

USER vscode
