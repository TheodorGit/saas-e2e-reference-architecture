# Yarn's apt source has an expired signing key, which breaks apt and the Docker feature.
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm
RUN rm -f /etc/apt/sources.list.d/yarn.list
