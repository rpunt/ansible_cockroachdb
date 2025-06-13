#!/bin/bash
# Helper script for using podman-compose with ansible-test

set -e

# Check if podman-compose is installed
if ! command -v podman-compose &> /dev/null; then
    echo "podman-compose not found. Installing..."
    if ! command -v pip &> /dev/null; then
        echo "pip not found. Please install Python and pip first."
        exit 1
    fi
    pip install podman-compose
fi

# Check if podman is installed
if ! command -v podman &> /dev/null; then
    echo "podman not found. Please install podman first."
    exit 1
fi

# Check if a command was provided
if [ "$#" -eq 0 ]; then
    echo "Usage: $0 [podman-compose commands]"
    echo "Example: $0 up -d"
    exit 1
fi

# Set podman socket configuration for rootless mode if needed
if [ -S "/run/user/$UID/podman/podman.sock" ]; then
    export DOCKER_HOST=unix:///run/user/$UID/podman/podman.sock
fi

echo "Running: podman-compose $*"
# Execute the command
podman-compose "$@"
