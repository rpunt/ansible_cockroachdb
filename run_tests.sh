#!/bin/bash
# Comprehensive test script for CockroachDB Ansible collection
# This script can run tests in local or Podman modes with or without containers

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Default settings
MODE="local"         # local, podman
TEST_TYPE="all"      # all, sanity, unit, integration
USE_CONTAINERS=false # use containers for CockroachDB
VERBOSE=false        # verbose output

# Help message
show_help() {
    echo -e "${BOLD}CockroachDB Ansible Collection Test Runner${NC}"
    echo -e "This script runs tests for the CockroachDB Ansible collection in different modes\n"
    echo -e "${BOLD}Usage:${NC} $0 [options]"
    echo -e "\n${BOLD}Options:${NC}"
    echo -e "  ${GREEN}-m, --mode${NC} MODE       Test mode: local, podman (default: local)"
    echo -e "  ${GREEN}-t, --type${NC} TYPE       Test type: all, sanity, unit, integration (default: all)"
    echo -e "  ${GREEN}-c, --container${NC}       Use Podman containers for CockroachDB (default: false)"
    echo -e "  ${GREEN}-v, --verbose${NC}         Enable verbose output"
    echo -e "  ${GREEN}-h, --help${NC}            Show this help message"
    echo -e "\n${BOLD}Examples:${NC}"
    echo -e "  $0 --mode local --type all                          # Run all tests locally"
    echo -e "  $0 --mode podman --type sanity                      # Run sanity tests in podman"
    echo -e "  $0 --mode local --container                         # Run tests locally with containerized CockroachDB"
    echo -e "  $0 -m podman -t integration -c                      # Run integration tests in podman with containerized CockroachDB"
    echo -e "  $0 -t integration -f consolidated_tests.yml -d basic # Run basic integration tests with consolidated framework"
    echo -e "  $0 -t integration -d comprehensive                  # Run comprehensive tests with consolidated framework"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -m|--mode)
            MODE="$2"
            shift 2
            ;;
        -t|--type)
            TEST_TYPE="$2"
            shift 2
            ;;
        -c|--container)
            USE_CONTAINERS=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
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

# Validate options
if [[ ! "$MODE" =~ ^(local|podman)$ ]]; then
    echo -e "${RED}Error: Invalid mode '$MODE'. Must be 'local' or 'podman'${NC}"
    exit 1
fi

if [[ ! "$TEST_TYPE" =~ ^(all|sanity|unit|integration)$ ]]; then
    echo -e "${RED}Error: Invalid test type '$TEST_TYPE'. Must be 'all', 'sanity', 'unit', or 'integration'${NC}"
    exit 1
fi

# Check required commands
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}Error: '$1' is required but not found. Please install it first.${NC}"
        exit 1
    fi
}

# Check if we're in the collection root
if [ ! -f "galaxy.yml" ]; then
    echo -e "${RED}Error: galaxy.yml not found. Please run this script from the collection root.${NC}"
    exit 1
fi

# Get collection information
COLLECTION_NAMESPACE=$(grep "namespace:" galaxy.yml | awk '{print $2}')
COLLECTION_NAME=$(grep "name:" galaxy.yml | awk '{print $2}')
COLLECTION_VERSION=$(grep "version:" galaxy.yml | awk '{print $2}')
COLLECTION_FILE="${COLLECTION_NAMESPACE}-${COLLECTION_NAME}-${COLLECTION_VERSION}.tar.gz"

# Print test configuration
echo -e "\n${BOLD}CockroachDB Ansible Collection Test Configuration${NC}"
echo -e "  ${YELLOW}Collection:${NC} ${COLLECTION_NAMESPACE}.${COLLECTION_NAME} v${COLLECTION_VERSION}"
echo -e "  ${YELLOW}Mode:${NC} ${MODE}"
echo -e "  ${YELLOW}Test Type:${NC} ${TEST_TYPE}"
echo -e "  ${YELLOW}Use Containers:${NC} ${USE_CONTAINERS}"
echo -e "  ${YELLOW}Verbose:${NC} ${VERBOSE}"
echo -e "${BOLD}======================================================${NC}\n"

# Remove build artifacts
echo "Cleaning up build artifacts..."
rm -rf ansible_collections/
rm -f *.tar.gz

# Build collection
echo -e "${BLUE}Building collection...${NC}"
ansible-galaxy collection build --force

# Install collection
echo -e "${BLUE}Installing collection...${NC}"
ansible-galaxy collection install "${COLLECTION_FILE}" --force

# Functions for tests
run_local_tests() {
    local test_type=$1

    case "$test_type" in
        "sanity")
            echo -e "${GREEN}Running local sanity tests...${NC}"
            python -c "import unittest; unittest.main(module='tests.unit.modules', argv=['first-arg-is-ignored', 'TestCockroachDBModules.test_module_imports', 'TestCockroachDBModules.test_documentation_exists'])"
            ;;
        "unit")
            echo -e "${GREEN}Running local unit tests...${NC}"
            python -m unittest tests/unit/modules.py
            ;;
        "integration")
            echo -e "${GREEN}Running local integration tests...${NC}"
            if [ "$USE_CONTAINERS" = true ]; then
                start_cockroachdb_container
                trap stop_cockroachdb_container EXIT
            fi
            ansible-playbook tests/integration/integration_tests.yml -v
            ;;
        "all")
            run_local_tests "sanity"
            run_local_tests "unit"
            run_local_tests "integration"
            ;;
    esac
}

run_podman_tests() {
    local test_type=$1

    # Check if podman is installed
    check_command podman

    case "$test_type" in
        "sanity")
            echo -e "${GREEN}Running sanity tests in Podman container...${NC}"
            podman run --rm -v "$(pwd):/collection:Z" \
                python:3.9-slim \
                bash -c "cd /collection && \
                    apt-get update && \
                    apt-get install -y git && \
                    pip install -U 'pip' 'wheel' 'ansible' 'ansible-core' 'psycopg2-binary' && \
                    python -c \"import unittest; unittest.main(module='tests.unit.modules', argv=['first-arg-is-ignored', 'TestCockroachDBModules.test_module_imports', 'TestCockroachDBModules.test_documentation_exists'])\""
            ;;
        "unit")
            echo -e "${GREEN}Running unit tests in Podman container...${NC}"
            podman run --rm -v "$(pwd):/collection:Z" \
                python:3.9-slim \
                bash -c "cd /collection && \
                    apt-get update && \
                    apt-get install -y git && \
                    pip install -U 'pip' 'wheel' 'ansible' 'ansible-core' 'psycopg2-binary' && \
                    python -m unittest tests/unit/modules.py"
            ;;
        "integration")
            echo -e "${GREEN}Running integration tests in Podman container...${NC}"
            # Start CockroachDB in Podman container if needed
            if [ "$USE_CONTAINERS" = true ]; then
                echo -e "${GREEN}Starting CockroachDB in Podman container...${NC}"
                if command -v podman-compose &> /dev/null; then
                    podman-compose -f tests/integration/docker-compose.yml up -d
                    trap "podman-compose -f tests/integration/docker-compose.yml down" EXIT
                else
                    echo -e "${YELLOW}Warning: podman-compose not found. Using wrapper...${NC}"
                    bash podman-compose-wrapper.sh -f tests/integration/docker-compose.yml up -d
                    trap "bash podman-compose-wrapper.sh -f tests/integration/docker-compose.yml down" EXIT
                fi
            fi

            # Run integration tests
            podman run --rm -v "$(pwd):/collection:Z" \
                --net=host \
                python:3.9-slim \
                bash -c "cd /collection && \
                    apt-get update && \
                    apt-get install -y git && \
                    pip install -U 'pip' 'wheel' 'ansible' 'ansible-core' 'psycopg2-binary' && \
                    ansible-playbook tests/integration/${TEST_FILE} -v"
            ;;
        "all")
            run_podman_tests "sanity"
            run_podman_tests "unit"
            run_podman_tests "integration"
            ;;
    esac
}



start_cockroachdb_container() {
    echo -e "${GREEN}Starting local CockroachDB container with Podman...${NC}"
    if command -v podman-compose &> /dev/null; then
        podman-compose -f tests/integration/docker-compose.yml up -d
    else
        echo -e "${RED}Error: podman-compose not found and podman-compose-wrapper.sh not available${NC}"
        exit 1
    fi

    # Wait for CockroachDB to be ready
    echo -e "${YELLOW}Waiting for CockroachDB to be ready...${NC}"
    sleep 10  # Simple wait - in production, use a proper health check
}

stop_cockroachdb_container() {
    echo -e "${GREEN}Stopping local CockroachDB container...${NC}"
    if command -v podman-compose &> /dev/null; then
        podman-compose -f tests/integration/docker-compose.yml down
    fi
}

# Run tests based on mode
case "$MODE" in
    "local")
        run_local_tests "$TEST_TYPE"
        ;;
    "podman")
        run_podman_tests "$TEST_TYPE"
        ;;
esac

echo -e "\n${GREEN}${BOLD}All tests completed successfully!${NC}"
