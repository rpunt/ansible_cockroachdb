# Testing the CockroachDB Ansible Collection

This document describes how to test the CockroachDB Ansible collection using various methods and tools.

## Prerequisites

- Python 3.6 or higher with pip
- Ansible 2.9 or higher
- For containerized testing:
  - Podman
  - podman-compose or the included podman-compose-wrapper.sh (for integration tests)

## Overview of Testing Scripts

The collection includes several scripts to facilitate testing:

1. `run_tests.sh` - Comprehensive script supporting multiple testing environments (local, podman)
2. `test_with_podman.sh` - Script for running tests specifically in Podman containers
3. `test_local.sh` - Script for quick testing of individual modules locally
4. `test_module.sh` - Script for testing specific modules
5. `podman-compose-wrapper.sh` - Helper script for running podman-compose commands

## Available Test Types

The testing scripts support several types of tests:

- **Sanity tests**: Basic code quality checks (syntax, formatting, etc.)
- **Unit tests**: Tests individual modules without needing a CockroachDB server
- **Integration tests**: Tests that require a functioning CockroachDB server

## Running Tests

### Using the Comprehensive Test Script

The `run_tests.sh` script supports multiple testing environments and configurations:

```bash
# Run all tests locally
./run_tests.sh --mode local --type all

# Run sanity tests in a Podman container
./run_tests.sh --mode podman --type sanity

# Run integration tests in Podman with containerized CockroachDB
./run_tests.sh --mode podman --type integration --container

# Get help on all options
./run_tests.sh --help
```

### Command-line Options for run_tests.sh

- `--mode, -m MODE`: Test mode (local, podman)
- `--type, -t TYPE`: Test type (all, sanity, unit, integration)
- `--file, -f FILE`: Test file (consolidated_tests.yml, integration_tests.yml, comprehensive_tests.yml, simplified_tests.yml)
- `--test-mode, -d MODE`: Test depth mode (basic, standard, comprehensive)
- `--container, -c`: Use containers for CockroachDB
- `--verbose, -v`: Enable verbose output
- `--help, -h`: Show help message

### Testing Individual Modules

For quick testing of individual modules:

```bash
# Test a specific module with all test types
./test_local.sh cockroachdb_info

# Test a specific module with a specific test type
./test_local.sh cockroachdb_info sanity
./test_local.sh cockroachdb_info unit
./test_local.sh cockroachdb_info integration
```

### Using Podman Specifically

If you prefer to use Podman containers for testing:

```bash
# Run all tests
./test_with_podman.sh --all

# Run only sanity tests
./test_with_podman.sh --sanity

# Run only unit tests
./test_with_podman.sh --unit

# Run only integration tests
./test_with_podman.sh --integration
```

## Integration Testing

Integration tests require a running CockroachDB instance. The script will:

1. Start a CockroachDB container using the configuration in `tests/integration/docker-compose.yml` with Podman
2. Run the integration tests
3. Stop the CockroachDB container when tests are complete

### Consolidated Test Framework

The collection includes a new consolidated test framework that combines all previous test files into a single, modular system. This framework features:

- **Variable-based configuration** for connection parameters
- **Modular test structure** with module-specific test blocks
- **Three test modes**:
  - `basic` - Only tests core functionality (info, database, query operations)
  - `standard` - Tests common modules (info, database, user, privilege, table, index, query)
  - `comprehensive` - Tests all modules including advanced features

#### Using the Consolidated Test Framework

Run tests with the consolidated framework using the `run_tests.sh` script with the new `--test-mode` option:

```bash
# Run basic tests
./run_tests.sh --type integration --test-mode basic

# Run standard tests (default)
./run_tests.sh --type integration

# Run comprehensive tests
./run_tests.sh --type integration --test-mode comprehensive
```

#### Test Modules in Each Mode

| Module | Basic Mode | Standard Mode | Comprehensive Mode |
|--------|------------|---------------|-------------------|
| cockroachdb_info | ✅ | ✅ | ✅ |
| cockroachdb_db | ✅ | ✅ | ✅ |
| cockroachdb_query | ✅ | ✅ | ✅ |
| cockroachdb_user | ❌ | ✅ | ✅ |
| cockroachdb_privilege | ❌ | ✅ | ✅ |
| cockroachdb_table | ❌ | ✅ | ✅ |
| cockroachdb_index | ❌ | ✅ | ✅ |
| cockroachdb_statistics | ❌ | ❌ | ✅ |
| cockroachdb_parameter | ❌ | ❌ | ✅ |
| cockroachdb_maintenance | ❌ | ❌ | ✅ |
| cockroachdb_backup | ❌ | ❌ | ✅ |

#### Environment Variables

The consolidated test framework supports the following environment variables:

| Variable Name | Description | Default |
|---------------|-------------|---------|
| CRDB_TEST_MODE | Test mode: basic, standard, comprehensive | standard |
| COCKROACH_HOST | Database host | localhost |
| COCKROACH_PORT | Database port | 26257 |
| COCKROACH_USER | Database user | root |
| COCKROACH_PASSWORD | Database password | - |
| COCKROACH_SSL_MODE | SSL mode | disable |
| COCKROACH_SSL_CERT | SSL certificate path | - |
| COCKROACH_SSL_KEY | SSL key path | - |
| COCKROACH_SSL_ROOTCERT | SSL root certificate path | - |

#### Legacy Test Files

For backward compatibility, the original test files are still available:

- `integration_tests.yml` - Basic tests for core functionality
- `comprehensive_tests.yml` - Complete tests for all modules
- `simplified_tests.yml` - Tests with variables and structured approach

To use these files with the `run_tests.sh` script:

```bash
# Run simple integration tests
./run_tests.sh -t integration -f integration_tests.yml

# Run comprehensive tests
./run_tests.sh -t integration -f comprehensive_tests.yml

# Run simplified tests
./run_tests.sh -t integration -f simplified_tests.yml
```

## Adding New Tests

### Adding Unit Tests

Place new unit tests in:

```python
tests/unit/
```

### Adding Integration Tests

Create test modules in:

```yaml
tests/integration/targets/cockroachdb_modules/tasks/
```

Add the module name to the list in:

```yaml
tests/integration/integration_config.yml
```

## Test Structure

The collection follows the standard Ansible collection test structure:

- `tests/unit/`: Contains unit tests that don't require external services
- `tests/integration/`: Contains integration tests that require CockroachDB
- `tests/output/`: Contains test results and coverage reports

## Troubleshooting

If you encounter issues with the tests, try these steps:

1. Ensure your Python environment has all required dependencies:
   ```bash
   pip install ansible ansible-core psycopg2-binary
   ```

2. For container-based tests, check that Podman is properly installed

3. For integration tests, make sure port 26257 is available

4. Check that your collection structure follows ansible-test requirements

5. Review the container logs for detailed error messages

6. Try running tests with the `--verbose` flag for more detailed output:
   ```bash
   ./run_tests.sh --mode local --type unit --verbose
   ```
