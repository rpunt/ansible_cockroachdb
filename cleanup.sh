#!/bin/bash

# Script to clean up build artifacts and prepare for Git commit

echo "Cleaning up build artifacts..."

# Remove build artifacts
rm -rf ansible_collections/
rm -f *.tar.gz

# Remove Python cache files
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete
find . -type f -name "*.pyd" -delete

# Remove test output
rm -rf tests/output/*

echo "Cleanup complete!"
echo "The repository is now ready for Git commit."
