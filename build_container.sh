#!/bin/bash
# Build script for creating the CockroachDB Ansible Collection test container image
#
# This script builds a local container image for testing the CockroachDB Ansible collection

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Default settings
IMAGE_NAME="ansible-cockroachdb-test-local"
TAG="latest"

# Help message
show_help() {
    echo -e "${BOLD}CockroachDB Ansible Collection Container Builder${NC}"
    echo -e "This script builds a local container image for testing the CockroachDB Ansible collection\n"
    echo -e "${BOLD}Usage:${NC} $0 [options]"
    echo -e "\n${BOLD}Options:${NC}"
    echo -e "  ${GREEN}-f, --force${NC}           Force rebuild even if image exists"
    echo -e "  ${GREEN}-h, --help${NC}            Show this help message"
    echo -e "\n${BOLD}Examples:${NC}"
    echo -e "  $0                   # Build local image if it doesn't exist"
    echo -e "  $0 --force           # Force rebuild of local image"
}

# Default behavior
FORCE_REBUILD=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -f|--force)
            FORCE_REBUILD=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $key${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Check for podman
if ! command -v podman &> /dev/null; then
    echo -e "${RED}Error: podman is required but not found.${NC}"
    echo -e "${YELLOW}Please install podman before running this script.${NC}"
    exit 1
fi

# Check if we're in the collection root
if [ ! -f "galaxy.yml" ]; then
    echo -e "${RED}Error: galaxy.yml not found. Please run this script from the collection root.${NC}"
    exit 1
fi

# Full image reference
FULL_IMAGE="${IMAGE_NAME}:${TAG}"

# Check if image already exists
if podman image exists "$FULL_IMAGE" && [ "$FORCE_REBUILD" = false ]; then
    echo -e "${GREEN}Local test image $FULL_IMAGE already exists.${NC}"
    echo -e "${YELLOW}Use --force to rebuild if needed.${NC}"
    exit 0
fi

echo -e "${BLUE}Building local container image: ${FULL_IMAGE}${NC}"

# Build the container image
echo -e "${GREEN}Building the container image...${NC}"
podman build -t "$FULL_IMAGE" -f docker/Dockerfile .

echo -e "\n${GREEN}${BOLD}Container image built successfully: ${FULL_IMAGE}${NC}"
echo -e "${YELLOW}This image will be used automatically by run_tests.sh${NC}"
echo -e "${BLUE}To rebuild the image, run: $0 --force${NC}"
