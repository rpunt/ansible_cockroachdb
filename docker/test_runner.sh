#!/bin/bash

set -e

# Set variables
COLLECTION_NAMESPACE="rpunt"
COLLECTION_NAME="cockroachdb"

echo "=== CockroachDB Ansible Collection Test Runner ==="
echo "Running tests for ${COLLECTION_NAMESPACE}.${COLLECTION_NAME}"

# Create ansible collections directory structure
ANSIBLE_COLLECTIONS_PATH="/root/.ansible/collections/ansible_collections"
mkdir -p "${ANSIBLE_COLLECTIONS_PATH}/${COLLECTION_NAMESPACE}/${COLLECTION_NAME}"

# Link collection files to ansible collections path
ln -sf /collection/* "${ANSIBLE_COLLECTIONS_PATH}/${COLLECTION_NAMESPACE}/${COLLECTION_NAME}/"

# Function to run tests
run_tests() {
  TEST_TYPE=$1
  echo "Running $TEST_TYPE tests..."
  
  case $TEST_TYPE in
    "sanity")
      cd /collection
      ansible-test sanity --docker=base --python=3.11
      ;;
    "unit")
      cd /collection
      pytest -v tests/unit/
      ;;
    "integration")
      cd /collection
      ansible-playbook -i tests/integration/inventory tests/integration/integration_tests.yml -v
      ;;
    *)
      echo "Unknown test type: $TEST_TYPE"
      exit 1
      ;;
  esac
}

# Run the specified tests or all tests
if [ -z "$1" ]; then
  # Run all tests
  run_tests "sanity"
  run_tests "unit"
  run_tests "integration"
else
  # Run specific test
  run_tests "$1"
fi

echo "All tests completed!"
