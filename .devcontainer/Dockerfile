# The dev container's base image, without its Yarn package source: Yarn's signing key
# no longer verifies, and an unsigned source stops apt - and with it the Docker feature.
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm
RUN rm -f /etc/apt/sources.list.d/yarn.list
