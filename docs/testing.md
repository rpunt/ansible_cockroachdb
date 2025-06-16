# Testing the CockroachDB Ansible Collection

This document describes how to test the CockroachDB Ansible collection using various methods and tools.

## Prerequisites

- Python 3.6 or higher with pip
- Ansible 2.9 or higher
- Podman (recommended for default testing mode)
- For containerized CockroachDB testing:
  - podman-compose or the included podman-compose-wrapper.sh (for integration tests)

## Overview of Testing Scripts

The collection includes several scripts to facilitate testing:

1. `run_tests.sh` - Primary comprehensive script supporting multiple testing environments (podman by default, local as an advanced option)
2. `test_with_podman.sh` - Legacy script for running tests specifically in Podman containers
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
# Run all tests with default settings (Podman mode)
./run_tests.sh

# Run all tests locally (advanced option)
./run_tests.sh --mode local --type all

# Run sanity tests in a Podman container
./run_tests.sh --type sanity

# Run integration tests in Podman with containerized CockroachDB
./run_tests.sh --type integration --container

# Get help on all options
./run_tests.sh --help
```

> 💡 **Note:** Podman is the default and recommended testing environment as it provides consistent and isolated conditions for testing. Local testing is available as an advanced option for development purposes.

### Command-line Options for run_tests.sh

- `--mode, -m MODE`: Test mode (podman, local) - default is podman
- `--type, -t TYPE`: Test type (all, sanity, unit, integration) - default is all
- `--container, -c`: Use containers for CockroachDB - default is false
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

Podman is now the default testing environment for the `run_tests.sh` script. However, if you want to use the legacy Podman-specific script:

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

> ⚠️ **Note:** The `test_with_podman.sh` script is maintained for backward compatibility, but the recommended approach is to use `run_tests.sh` which defaults to Podman mode.

## Integration Testing

Integration tests require a running CockroachDB instance. When using the `--container` option or Podman mode, the script will:

1. Start a CockroachDB container using the configuration in `tests/integration/docker-compose.yml` with Podman
2. Run the integration tests
3. Stop the CockroachDB container when tests are complete

Without the `--container` option in local mode, you'll need a locally running CockroachDB instance accessible at localhost:26257.

### Integration Test Structure

The integration tests in the collection have the following features:

- **Variable-based configuration** for connection parameters
- **Modular test structure** with module-specific test blocks
- **Environment variable configuration** for connection parameters

#### Running Integration Tests

Run integration tests using the `run_tests.sh` script:

```bash
# Run integration tests with default settings (Podman mode)
./run_tests.sh --type integration

# Run integration tests in local mode
./run_tests.sh --mode local --type integration

# Run integration tests with containerized CockroachDB
./run_tests.sh --type integration --container
```

#### Modules Tested in Integration Tests

The integration tests cover all the modules in the collection:

| Module | Description |
|--------|-------------|
| cockroachdb_info | Gather information about CockroachDB |
| cockroachdb_db | Manage CockroachDB databases |
| cockroachdb_query | Execute SQL queries in CockroachDB |
| cockroachdb_user | Manage CockroachDB users |
| cockroachdb_privilege | Manage CockroachDB privileges |
| cockroachdb_table | Manage CockroachDB tables |
| cockroachdb_index | Manage CockroachDB indexes |
| cockroachdb_statistics | Manage CockroachDB statistics |
| cockroachdb_parameter | Manage CockroachDB parameters |
| cockroachdb_maintenance | Perform CockroachDB maintenance operations |
| cockroachdb_backup | Manage CockroachDB backups |

#### Environment Variables

The integration tests support the following environment variables:

| Variable Name | Description | Default |
|---------------|-------------|---------|
| COCKROACH_HOST | Database host | localhost |
| COCKROACH_PORT | Database port | 26257 |
| COCKROACH_USER | Database user | root |
| COCKROACH_PASSWORD | Database password | - |
| COCKROACH_SSL_MODE | SSL mode | disable |
| COCKROACH_SSL_CERT | SSL certificate path | - |
| COCKROACH_SSL_KEY | SSL key path | - |
| COCKROACH_SSL_ROOTCERT | SSL root certificate path | - |

#### Integration Test Files

The following test files are included:

- `integration_tests.yml` - Default test file used for integration tests

The `--file` and `--test-mode` options have been removed from the latest version of `run_tests.sh` for simplification. The script now uses the standard `integration_tests.yml` file for all integration testing.

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

## Testing Modes

The `run_tests.sh` script supports two primary testing modes:

### Podman Mode (Default)

Podman mode creates isolated containers for running tests, providing a consistent and reproducible testing environment. This is the recommended mode for:

- CI/CD pipelines
- Consistent test results across different environments
- Testing without altering your local system configuration
- Ensuring all dependencies are properly installed

### Local Mode (Advanced)

Local mode runs tests directly on your host system. This mode is available as an advanced option for:

- Development workflows where you need quick feedback
- Debugging specific issues
- Environments where containers can't be used
- Custom or specialized testing setups

**IMPORTANT: For local mode, you must have CockroachDB installed and running locally before starting tests.** You can start CockroachDB with:

```bash
cockroach start-single-node --insecure --background
```

**Requirements for local mode:**

- The CockroachDB server must be accessible on localhost:26257 with user 'root' without a password
- For integration tests, your local CockroachDB instance must allow creating/dropping databases and users
- Currently, sanity and unit tests may fail in local mode due to issues with build artifacts
- The script will attempt to configure the proper ANSIBLE_COLLECTIONS_PATH but you may need to manually set it if modules can't be found

We recommend using the default Podman mode unless you have specific requirements that necessitate local testing.

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
   ./run_tests.sh --type unit --verbose
   ```

7. If running in local mode, ensure CockroachDB is installed and running:

   ```bash
   # Check if CockroachDB is installed
   which cockroach

   # Start CockroachDB if not running
   cockroach start-single-node --insecure --background

   # Verify CockroachDB is running
   cockroach sql --insecure -e "SHOW DATABASES;"
   ```

8. If you get a "couldn't resolve module/action 'cockroach_labs.cockroachdb.cockroachdb_*'" error in local mode:

   ```bash
   # Set the ANSIBLE_COLLECTIONS_PATH manually
   export ANSIBLE_COLLECTIONS_PATH="$(pwd):$HOME/.ansible/collections:/usr/share/ansible/collections"

   # Or try manually installing the collection
   ansible-galaxy collection build --force
   ansible-galaxy collection install cockroach_labs-cockroachdb-*.tar.gz --force
   ```
