#!/bin/bash
# Test runner script for CockroachDB Ansible collection
#
# This script runs tests for the CockroachDB Ansible collection locally
# with CockroachDB running in a podman contain    if podman ps -a --format '{{.Names}}' | grep -q "cockroachdb-install-test"; then
        echo -e "${YELLOW}Found existing cockroachdb-install-test container, removing...${NC}"
        podman stop cockroachdb-install-test 2>/dev/null || true
        podman rm cockroachdb-install-test 2>/dev/null || true
    fir consistency and
# isolation. This simplifies the testing environment while maintaining
# reliable database behavior.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Default settings
TEST_TYPE="all"      # all, sanity, unit, integration
VERBOSE=false        # verbose output

# Default CockroachDB container image name
CRDB_CONTAINER_IMAGE="cockroachdb/cockroach:latest"

# Help message
show_help() {
    echo -e "${BOLD}CockroachDB Ansible Collection Test Runner${NC}"
    echo -e "This script runs tests for the CockroachDB Ansible collection\n"
    echo -e "${BOLD}Usage:${NC} $0 [options]"
    echo -e "\n${BOLD}Options:${NC}"
    echo -e "  ${GREEN}-t, --type${NC} TYPE       Test type: all, sanity, unit, integration (default: all)"
    echo -e "  ${GREEN}-v, --verbose${NC}         Enable verbose output"
    echo -e "  ${GREEN}-h, --help${NC}            Show this help message"
    echo -e "\n${BOLD}Examples:${NC}"
    echo -e "  $0                                 # Run all tests (default)"
    echo -e "  $0 --type sanity                   # Run sanity tests only"
    echo -e "  $0 -t integration                  # Run integration tests only"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -t|--type)
            TEST_TYPE="$2"
            shift 2
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
echo -e "  ${YELLOW}Test Type:${NC} ${TEST_TYPE}"
echo -e "${BOLD}======================================================${NC}\n"

# Check dependencies
check_dependency() {
    local cmd=$1
    local package=$2

    if ! command -v "$cmd" &> /dev/null; then
        echo -e "${RED}Error: $package is required but not found.${NC}"
        echo -e "${YELLOW}Please install $package before running tests.${NC}"
        return 1
    fi
    return 0
}

# Check required dependencies
DEPENDENCY_CHECK_FAILED=false

# Check podman for CockroachDB container
if ! check_dependency "podman" "podman"; then
    DEPENDENCY_CHECK_FAILED=true
fi

# Check for podman-compose (needed for CockroachDB container)
if ! command -v podman-compose &> /dev/null; then
    echo -e "${YELLOW}Warning: podman-compose not found. Will attempt to use direct podman commands instead.${NC}"
    echo -e "${YELLOW}For best results, consider installing podman-compose.${NC}"
fi

# Check for Python dependencies
if ! check_dependency "python3" "Python 3"; then
    DEPENDENCY_CHECK_FAILED=true
fi

if ! check_dependency "ansible" "Ansible"; then
    DEPENDENCY_CHECK_FAILED=true
fi

if [ "$DEPENDENCY_CHECK_FAILED" = true ]; then
    echo -e "${RED}One or more required dependencies are missing. Please install them and try again.${NC}"
    exit 1
fi

# Check for required Python dependencies
echo -e "${BLUE}Checking Python dependencies...${NC}"

# For pytest-based tests, ensure pytest is available
if [ "$TEST_TYPE" = "unit" ] || [ "$TEST_TYPE" = "all" ]; then
    if ! python3 -c "import pytest" &> /dev/null; then
        echo -e "${YELLOW}Warning: pytest is not installed. Installing it now...${NC}"
        if ! pip3 install pytest mock &> /dev/null; then
            echo -e "${RED}Failed to install pytest. Please install it manually: pip install pytest mock${NC}"
            exit 1
        else
            echo -e "${GREEN}Successfully installed pytest and mock.${NC}"
        fi
    fi
fi

# For integration tests, ensure psycopg2 is available
if [ "$TEST_TYPE" = "integration" ] || [ "$TEST_TYPE" = "all" ]; then
    echo -e "${YELLOW}Checking and installing psycopg2...${NC}"

    # Find the system Python used by Ansible
    ANSIBLE_PYTHON=$(ansible --version | grep "python version" | awk '{print $4}')
    ANSIBLE_PYTHON_PATH=$(which python${ANSIBLE_PYTHON%.*} 2>/dev/null || which python3)

    echo -e "${BLUE}Ansible is using Python: ${ANSIBLE_PYTHON} at ${ANSIBLE_PYTHON_PATH}${NC}"

    # Try to install psycopg2 for multiple Python interpreters to ensure compatibility
    for PIP_CMD in "pip3" "pip" "python3 -m pip" "python -m pip" "${ANSIBLE_PYTHON_PATH} -m pip"; do
        echo -e "${BLUE}Trying to install psycopg2-binary with: ${PIP_CMD}${NC}"
        if ${PIP_CMD} install --user psycopg2-binary; then
            echo -e "${GREEN}Successfully installed psycopg2-binary using ${PIP_CMD}.${NC}"
            break
        fi
    done

    # Verify installation
    if ! python3 -c "import psycopg2" &> /dev/null; then
        echo -e "${YELLOW}Warning: psycopg2 still not accessible with python3. Continuing anyway...${NC}"
    else
        echo -e "${GREEN}psycopg2 is available with python3.${NC}"
    fi
fi

# Option to install all dependencies from requirements.txt
echo -e "${BLUE}You can also install all dependencies at once with: pip3 install -r requirements.txt${NC}"

# Clean, build and install collection
echo -e "${BLUE}Cleaning up build artifacts...${NC}"
rm -rf ansible_collections/ *.tar.gz

echo -e "${BLUE}Building and installing collection...${NC}"
ansible-galaxy collection build --force
ansible-galaxy collection install "${COLLECTION_FILE}" --force

# Start/stop CockroachDB container function
start_cockroachdb_container() {
    echo -e "${GREEN}Starting CockroachDB in Podman container...${NC}"

    # First check if the container already exists and is running
    if podman ps -a --format '{{.Names}}' | grep -q "cockroachdb-install-test"; then
        echo -e "${YELLOW}Found existing CockroachDB container, stopping and removing it...${NC}"
        podman stop cockroachdb-install-test 2>/dev/null || true
        podman rm cockroachdb-install-test 2>/dev/null || true
    fi

    # Check if we have a valid docker-compose.yml file
    if [ ! -f "tests/integration/docker-compose.yml" ]; then
        echo -e "${RED}Error: docker-compose.yml file not found at tests/integration/docker-compose.yml${NC}"
        return 1
    fi

    # Check if we're testing the cockroachdb_install module
    if grep -q "cockroachdb_install" <<< "$*"; then
        echo -e "${YELLOW}Tests include cockroachdb_install module, building custom container...${NC}"

        # Build a custom container from our Dockerfile if it exists
        if [ -f "tests/integration/Dockerfile" ]; then
            echo -e "${BLUE}Building custom container for cockroachdb_install tests...${NC}"

            # Build the container with non-interactive mode
            DOCKER_BUILDKIT=1 podman build \
                --build-arg DEBIAN_FRONTEND=noninteractive \
                -t cockroachdb-test-image:latest \
                -f tests/integration/Dockerfile tests/integration

            if [ $? -eq 0 ]; then
                # Update docker-compose to use our custom image
                echo -e "${YELLOW}Updating docker-compose.yml to use custom image${NC}"
                sed -i.bak 's|image:.*cockroach.*|image: cockroachdb-test-image:latest|g' tests/integration/docker-compose.yml
                rm -f tests/integration/docker-compose.yml.bak
            else
                echo -e "${RED}Failed to build custom image, using standard CockroachDB image${NC}"
            fi
        fi
    else
        # Use standard CockroachDB image
        echo -e "${BLUE}Using standard CockroachDB container image...${NC}"

        # Make sure docker-compose.yml is using the standard image
        if [ -f "tests/integration/docker-compose.yml" ] && ! grep -q "image: cockroachdb/cockroach:latest" tests/integration/docker-compose.yml; then
            echo -e "${YELLOW}Updating docker-compose.yml to use standard CockroachDB image${NC}"
            sed -i.bak 's|image:.*|image: cockroachdb/cockroach:latest|g' tests/integration/docker-compose.yml
            rm -f tests/integration/docker-compose.yml.bak
        fi
    fi

    # Try with podman-compose first (with better error handling)
    echo -e "${BLUE}Attempting to start CockroachDB with podman-compose...${NC}"
    if podman-compose -f tests/integration/docker-compose.yml up -d; then
        echo -e "${GREEN}Successfully started CockroachDB with podman-compose${NC}"
    else
        # Fall back to direct podman commands if podman-compose fails
        echo -e "${YELLOW}podman-compose failed, falling back to direct podman commands...${NC}"

        # Get image name from docker-compose file
        local image_name=$(grep "image:" tests/integration/docker-compose.yml | awk '{print $2}')
        if [ -z "$image_name" ]; then
            image_name="cockroachdb/cockroach:latest"
            echo -e "${YELLOW}No image specified in docker-compose.yml, using default: $image_name${NC}"
        fi

        echo -e "${BLUE}Starting CockroachDB with podman run...${NC}"
        podman run --name cockroachdb-install-test -d \
            -p 26257:26257 -p 8080:8080 \
            "$image_name" \
            start-single-node --insecure

        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to start CockroachDB container directly with podman${NC}"
            return 1
        fi
    fi

    echo -e "${YELLOW}Waiting for SSH server to be ready...${NC}"

    # Give SSH server time to initialize
    local max_attempts=5
    local attempt=1
    while [ $attempt -le $max_attempts ]; do
        echo -e "${BLUE}Checking if SSH server is ready (attempt $attempt/$max_attempts)...${NC}"
        if podman exec cockroachdb-install-test ps -ef | grep -v grep | grep sshd > /dev/null 2>&1; then
            echo -e "${GREEN}CockroachDB is ready!${NC}"
            break
        fi

        if [ $attempt -eq $max_attempts ]; then
            echo -e "${RED}CockroachDB failed to start properly within the expected time.${NC}"
            podman logs cockroachdb-install-test
            return 1
        fi

        echo -e "${YELLOW}Waiting for CockroachDB to become available...${NC}"
        sleep 5
        (( attempt++ ))
    done
}

stop_cockroachdb_container() {
    echo -e "${GREEN}Stopping CockroachDB container...${NC}"

    # First try podman-compose
    if podman-compose -f tests/integration/docker-compose.yml down 2>/dev/null; then
        echo -e "${GREEN}Successfully stopped containers with podman-compose${NC}"
    else
        # Fall back to direct podman commands
        echo -e "${YELLOW}Using direct podman commands to stop container...${NC}"
        podman stop cockroachdb-install-test 2>/dev/null || true
        podman rm cockroachdb-install-test 2>/dev/null || true
    fi
}

# Run the appropriate tests
run_tests() {
    local test_type=$1

    # Run specific test types
    case "$test_type" in
        "sanity")
            echo -e "${GREEN}Running sanity tests...${NC}"
            python -c 'import unittest; unittest.main(module="tests.unit.modules", argv=["first-arg-is-ignored", "TestCockroachDBModules.test_module_imports", "TestCockroachDBModules.test_documentation_exists"])'
            ;;
        "unit")
            echo -e "${GREEN}Running unit tests...${NC}"

            # First run standard module unit tests
            python -m unittest tests/unit/modules.py

            # Then run pytest-style unit tests
            echo -e "${GREEN}Running module-specific pytest unit tests...${NC}"
            local pytest_tests=$(find tests/unit/plugins/modules -name "test_*.py" 2>/dev/null)
            if [ -n "$pytest_tests" ]; then
                for test_file in $pytest_tests; do
                    echo -e "${BLUE}Running pytest tests for: $test_file${NC}"
                    python -m pytest $test_file -v
                done
            else
                echo -e "${YELLOW}No module-specific pytest tests found. Skipping.${NC}"
            fi
            ;;
        "integration")
            echo -e "${GREEN}Running integration tests...${NC}"

            # Always use containers for CockroachDB
            start_cockroachdb_container "integration cockroachdb_install"
            trap stop_cockroachdb_container EXIT

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

            # Make sure the inventory has the cockroachdb_servers group
            if ! grep -q '\[cockroachdb_servers\]' "tests/integration/inventory"; then
                echo -e "${YELLOW}Warning: Adding cockroachdb_servers group to inventory${NC}"

                # Get the Python interpreter path that has psycopg2 installed
                # First check which interpreter has psycopg2 available
                echo -e "${BLUE}Finding a Python interpreter with psycopg2 installed...${NC}"

                # Try to find a Python interpreter with psycopg2
                for py_cmd in "python3" "python" "/usr/local/bin/python3" "/usr/bin/python3"; do
                    echo -e "${YELLOW}Checking ${py_cmd}...${NC}"
                    if $py_cmd -c "import psycopg2" &> /dev/null; then
                        PYTHON_PATH=$($py_cmd -c "import sys; print(sys.executable)")
                        echo -e "${GREEN}Found Python interpreter with psycopg2: ${PYTHON_PATH}${NC}"
                        break
                    fi
                done

                # If no interpreter found, use current one
                if [ -z "$PYTHON_PATH" ]; then
                    PYTHON_PATH=$(python3 -c "import sys; print(sys.executable)" 2>/dev/null || which python3)
                    echo -e "${YELLOW}No Python with psycopg2 found, using default: ${PYTHON_PATH}${NC}"
                fi

                cat > tests/integration/inventory << EOF
[cockroachdb_servers]
localhost ansible_connection=local ansible_python_interpreter=${PYTHON_PATH}

[testgroup]
testhost ansible_connection=local ansible_python_interpreter=${PYTHON_PATH}

[all:vars]
ansible_python_interpreter=${PYTHON_PATH}
cockroachdb_host=localhost
cockroachdb_port=26257
cockroachdb_ssl_mode=disable
cockroachdb_user=root
EOF
            fi

            # Set environment variables for tests
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

            # Debug which Python is being used
            echo -e "${YELLOW}Checking Python interpreters...${NC}"
            python3 -c "import sys; print(f'Python executable: {sys.executable}')"
            python3 -c "import sys; print(f'Python path: {sys.path}')"

            # Run the integration tests with debug flags
            echo -e "${YELLOW}Running integration tests with verbose output...${NC}"

            # First run the cockroachdb_install module tests if they exist
            if [ -d "tests/integration/targets/cockroachdb_modules/cockroachdb_install" ]; then
                echo -e "${GREEN}Running cockroachdb_install module tests...${NC}"

                # Set environment variables to avoid prompts
                export DEBIAN_FRONTEND=noninteractive

                # Run the tests
                ANSIBLE_CONFIG=ansible.cfg ansible-playbook -i tests/integration/inventory tests/integration/targets/cockroachdb_modules/cockroachdb_install/main.yml -vvv
            fi

            # Then run the standard integration tests
            echo -e "${GREEN}Running standard integration tests...${NC}"
            ansible-playbook -i tests/integration/inventory tests/integration/integration_tests.yml -vvv -e "is_ssh_only_container=true"
            ;;
        "all")
            run_tests "sanity"
            run_tests "unit"
            run_tests "integration"
            ;;
    esac
}

# Run the tests
echo -e "${YELLOW}Starting tests for type: $TEST_TYPE${NC}"
run_tests "$TEST_TYPE"

echo -e "\n${GREEN}${BOLD}All tests completed successfully!${NC}"
