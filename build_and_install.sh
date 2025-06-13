#!/bin/bash
# Script to build and test the CockroachDB Ansible collection

set -e

# Check for galaxy.yml file
if [ ! -f galaxy.yml ]; then
  echo "galaxy.yml not found. This script must be run from the collection root directory."
  exit 1
fi

# Get the collection filename from the galaxy.yml file
NAMESPACE=$(grep "namespace:" galaxy.yml | awk '{print $2}')
NAME=$(grep "name:" galaxy.yml | awk '{print $2}')
VERSION=$(grep "version:" galaxy.yml | awk '{print $2}')
COLLECTION_NAME="${NAMESPACE}.${NAME}"
COLLECTION_FILE="${NAMESPACE}-${NAME}-${VERSION}.tar.gz"

echo "Building and installing the $COLLECTION_NAME collection"

# Remove build artifacts
echo "Cleaning up build artifacts..."
rm -rf ansible_collections/
rm -f *.tar.gz

# Build the collection
echo "Building collection..."
ansible-galaxy collection build --force

# Find the latest built archive
COLLECTION_ARCHIVE=$(ls -t *.tar.gz | head -1)

if [ -z "$COLLECTION_ARCHIVE" ]; then
    echo "Error: No collection archive found after build"
    exit 1
fi

echo "Collection built: $COLLECTION_ARCHIVE"

# Install the collection to the default location
echo "Installing collection to default location..."
ansible-galaxy collection install "$COLLECTION_ARCHIVE" --force

# Provide instructions for using the collection
echo "Collection can be used by referencing modules as:"
echo "  - ${COLLECTION_NAME}.module_name"

echo "Collection $COLLECTION_NAME installed successfully"

# Verify the collection is installed
echo "Verifying installation..."
ansible-galaxy collection list | grep -i $NAME
