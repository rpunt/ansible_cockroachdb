#!/bin/bash
# Test runner script for CockroachDB Ansible collection
# Supports local testing and Podman-based container testing
#
# Podman is the recommended and default testing environment as it provides
# consistent and isolated testing conditions. Local testing is available as
# an advanced option for development purposes.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Default settings
MODE="podman"        # podman, local
TEST_TYPE="all"      # all, sanity, unit, integration
USE_CONTAINERS=false # use containers for CockroachDB
VERBOSE=false        # verbose output

# Help message
show_help() {
    echo -e "${BOLD}CockroachDB Ansible Collection Test Runner${NC}"
    echo -e "This script runs tests for the CockroachDB Ansible collection\n"
    echo -e "${BOLD}Usage:${NC} $0 [options]"
    echo -e "\n${BOLD}Options:${NC}"
    echo -e "  ${GREEN}-m, --mode${NC} MODE       Test mode: podman, local (default: podman)"
    echo -e "  ${GREEN}-t, --type${NC} TYPE       Test type: all, sanity, unit, integration (default: all)"
    echo -e "  ${GREEN}-c, --container${NC}       Use Podman containers for CockroachDB (default: false)"
    echo -e "  ${GREEN}-v, --verbose${NC}         Enable verbose output"
    echo -e "  ${GREEN}-h, --help${NC}            Show this help message"
    echo -e "\n${BOLD}Examples:${NC}"
    echo -e "  $0                                 # Run all tests in podman (default)"
    echo -e "  $0 --mode local --type all         # Run all tests locally"
    echo -e "  $0 --type sanity                   # Run sanity tests in podman"
    echo -e "  $0 -t integration -c               # Run integration tests with containerized CockroachDB"
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
echo -e "${BOLD}======================================================${NC}\n"

# Check dependencies
if [ "$MODE" = "podman" ]; then
    if ! command -v podman &> /dev/null; then
        echo -e "${RED}Error: podman is required but not found. Please install it first.${NC}"
        exit 1
    fi
fi

if [ "$USE_CONTAINERS" = true ]; then
    if ! command -v podman-compose &> /dev/null; then
        echo -e "${RED}Error: podman-compose is required for container tests. Please install it first.${NC}"
        exit 1
    fi
fi

# Clean, build and install collection
echo "Cleaning up build artifacts..."
rm -rf ansible_collections/ *.tar.gz

echo -e "${BLUE}Building and installing collection...${NC}"
ansible-galaxy collection build --force
ansible-galaxy collection install "${COLLECTION_FILE}" --force

# Start/stop CockroachDB container function
start_cockroachdb_container() {
    echo -e "${GREEN}Starting CockroachDB in Podman container...${NC}"
    podman-compose -f tests/integration/docker-compose.yml up -d
    echo -e "${YELLOW}Waiting for CockroachDB to be ready...${NC}"

    # Give CockroachDB time to initialize
    local max_attempts=12
    local attempt=1
    while [ $attempt -le $max_attempts ]; do
        echo -e "${BLUE}Checking if CockroachDB is ready (attempt $attempt/$max_attempts)...${NC}"
        if podman exec cockroachdb-test curl -s http://localhost:8080/health > /dev/null 2>&1; then
            echo -e "${GREEN}CockroachDB is ready!${NC}"
            break
        fi

        if [ $attempt -eq $max_attempts ]; then
            echo -e "${RED}CockroachDB failed to start properly within the expected time.${NC}"
            podman logs cockroachdb-test
            return 1
        fi

        echo -e "${YELLOW}Waiting for CockroachDB to become available...${NC}"
        sleep 5
        (( attempt++ ))
    done
}

stop_cockroachdb_container() {
    echo -e "${GREEN}Stopping CockroachDB container...${NC}"
    podman-compose -f tests/integration/docker-compose.yml down
}

# Run the appropriate tests
run_tests() {
    local test_type=$1

    # Common container test command function
    run_in_container() {
        local cmd=$1
        echo -e "${BLUE}Running command in container: $cmd${NC}"

        # Create a setup script to ensure proper environment
        cat > container_setup.sh << EOF
#!/bin/bash
set -e -x
cd /collection
echo "Setting up container environment..."
# Ensure minimal environment output during setup
export DEBIAN_FRONTEND=noninteractive

# Install system dependencies
apt-get update -qq
apt-get install -y --no-install-recommends git curl python3-dev libpq-dev gcc build-essential postgresql-client procps -qq

# Set up Python environment
python3 -m pip install --upgrade pip setuptools wheel

# Install Ansible
python3 -m pip install ansible ansible-core

# Clean any previous installations and install psycopg2 properly
python3 -m pip uninstall -y psycopg2 psycopg2-binary || true
python3 -m pip install psycopg2-binary

# Verify psycopg2 is installed correctly
python3 -c "import psycopg2; print('psycopg2 version:', psycopg2.__version__)"

# Install additional dependencies
python3 -m pip install jinja2 pyyaml

# Add IP for localhost to /etc/hosts for better container compatibility
if ! grep -q "127.0.0.1 localhost" /etc/hosts; then
    echo "127.0.0.1 localhost" >> /etc/hosts
fi

# Create symlink for the collection to make sure modules are found
mkdir -p /root/.ansible/collections/ansible_collections/cockroach_labs
ln -sf /collection /root/.ansible/collections/ansible_collections/cockroach_labs/cockroachdb

# Print debug info
echo "Python path:"
python3 -c "import sys; print(sys.path)"
echo "Ansible collections path:"
python3 -c "import os; print(os.environ.get('ANSIBLE_COLLECTIONS_PATH', 'Not set'))"

# Set environment variables for better Python/Ansible compatibility
export PYTHONPATH="/collection:/root/.ansible/collections:\${PYTHONPATH}"
export ANSIBLE_COLLECTIONS_PATH="/root/.ansible/collections"

echo "Running command: $cmd"
$cmd
EOF
        chmod +x container_setup.sh

        # Run container with improved settings
        podman run --rm -v "$(pwd):/collection:Z" --net=host \
            -e PYTHONUNBUFFERED=1 \
            -e ANSIBLE_STDOUT_CALLBACK=debug \
            -e ANSIBLE_PYTHON_INTERPRETER=/usr/local/bin/python3 \
            -e ANSIBLE_COLLECTIONS_PATH=/root/.ansible/collections \
            -e PYTHONPATH=/collection:/root/.ansible/collections \
            -e ANSIBLE_MODULE_UTILS=/collection/plugins/module_utils \
            -e ANSIBLE_CONFIG=/collection/ansible.cfg \
            python:3.11-slim bash -c "/collection/container_setup.sh"

        # Clean up
        rm -f container_setup.sh
    }

    # Run specific test types
    case "$test_type" in
        "sanity")
            echo -e "${GREEN}Running sanity tests...${NC}"
            local sanity_cmd="python -c 'import unittest; unittest.main(module=\"tests.unit.modules\", argv=[\"first-arg-is-ignored\", \"TestCockroachDBModules.test_module_imports\", \"TestCockroachDBModules.test_documentation_exists\"])'"
            if [ "$MODE" = "podman" ]; then
                run_in_container "$sanity_cmd"
            else
                eval $sanity_cmd
            fi
            ;;
        "unit")
            echo -e "${GREEN}Running unit tests...${NC}"
            local unit_cmd="python -m unittest tests/unit/modules.py"
            if [ "$MODE" = "podman" ]; then
                run_in_container "$unit_cmd"
            else
                eval $unit_cmd
            fi
            ;;        "integration")
            echo -e "${GREEN}Running integration tests...${NC}"
            if [ "$USE_CONTAINERS" = true ]; then
                start_cockroachdb_container
                trap stop_cockroachdb_container EXIT
            elif [ "$MODE" = "local" ]; then
                # Check if CockroachDB is installed and running locally when in local mode
                if ! command -v cockroach &> /dev/null; then
                    echo -e "${RED}Error: CockroachDB not found. In local mode, you must have CockroachDB installed.${NC}"
                    echo -e "${YELLOW}Tip: Install CockroachDB or use podman mode with --container option.${NC}"
                    exit 1
                fi

                # Check if CockroachDB is running by trying to connect
                if ! cockroach sql --insecure --host=localhost --port=26257 -e "SELECT 1" &> /dev/null; then
                    echo -e "${RED}Error: CockroachDB is not running or not accessible.${NC}"
                    echo -e "${YELLOW}Tip: Start CockroachDB with: cockroach start-single-node --insecure --background${NC}"
                    exit 1
                fi

                echo -e "${GREEN}Successfully connected to local CockroachDB instance${NC}"
            fi

            # Check if the integration tests file exists
            if [ ! -f "tests/integration/integration_tests.yml" ]; then
                echo -e "${RED}Error: Integration test file not found: tests/integration/integration_tests.yml${NC}"
                exit 1
            fi

            # Check if inventory exists and is properly set up
            if [ ! -f "tests/integration/inventory" ]; then
                echo -e "${RED}Error: Inventory file not found: tests/integration/inventory${NC}"
                exit 1
            fi

            # Create a container-friendly inventory file when running in podman mode
            if [ "$MODE" = "podman" ]; then
                echo -e "${YELLOW}Creating container-friendly inventory file${NC}"
                cat > tests/integration/inventory.container << EOF
[cockroachdb_servers]
localhost ansible_connection=local

[testgroup]
testhost ansible_connection=local

[all:vars]
ansible_python_interpreter=/usr/local/bin/python3
cockroachdb_host=localhost
cockroachdb_port=26257
cockroachdb_ssl_mode=disable
cockroachdb_user=root
EOF
                INVENTORY_FILE="tests/integration/inventory.container"
            else
                # Make sure the inventory has the cockroachdb_servers group for local mode
                if ! grep -q '\[cockroachdb_servers\]' "tests/integration/inventory"; then
                    echo -e "${YELLOW}Warning: Adding cockroachdb_servers group to inventory${NC}"
                    cat > tests/integration/inventory << EOF
[cockroachdb_servers]
localhost ansible_connection=local ansible_python_interpreter=$(which python3)

[testgroup]
testhost ansible_connection=local ansible_python_interpreter=$(which python3)

[all:vars]
ansible_python_interpreter=$(which python3)
cockroachdb_host=localhost
cockroachdb_port=26257
cockroachdb_ssl_mode=disable
cockroachdb_user=root
EOF
                fi
                INVENTORY_FILE="tests/integration/inventory"
            fi

            local int_cmd="ansible-playbook -i $INVENTORY_FILE tests/integration/integration_tests.yml -v"
            if [ "$MODE" = "podman" ]; then
                echo -e "${BLUE}Running tests in podman container...${NC}"
                run_in_container "$int_cmd"
            else
                # Set environment variables for local mode
                export PYTHONPATH="$(pwd):${PYTHONPATH}"
                export ANSIBLE_COLLECTIONS_PATH="$(ansible-config dump | grep 'COLLECTIONS_PATHS' | awk -F ' = ' '{print $2}')"

                # If ANSIBLE_COLLECTIONS_PATH is not set, use default paths
                if [ -z "$ANSIBLE_COLLECTIONS_PATH" ]; then
                    # Add common ansible collection paths
                    export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:/usr/share/ansible/collections"
                fi

                # Add the current directory to ANSIBLE_COLLECTIONS_PATH
                export ANSIBLE_COLLECTIONS_PATH="$(pwd):${ANSIBLE_COLLECTIONS_PATH}"

                echo -e "${BLUE}Using ANSIBLE_COLLECTIONS_PATH: ${ANSIBLE_COLLECTIONS_PATH}${NC}"

                eval $int_cmd
            fi
            ;;
        "all")
            run_tests "sanity"
            run_tests "unit"
            run_tests "integration"
            ;;
    esac
}

# Run the tests
run_tests "$TEST_TYPE"

echo -e "\n${GREEN}${BOLD}All tests completed successfully!${NC}"
