FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

USER root
# Imagem base inclui repo Yarn com chave GPG expirada/ausente (NO_PUBKEY 62D54FD4003F6525).
# Node vem do devcontainer feature; não precisamos do pacote apt yarn.
RUN rm -f /etc/apt/sources.list.d/yarn.list /etc/apt/sources.list.d/yarn*.list 2>/dev/null || true \
    && apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install -y --no-install-recommends \
        libcurl4-openssl-dev \
        curl \
    && apt-get clean -y && rm -rf /var/lib/apt/lists/*

USER vscode
