# CockroachDB Ansible Collection Integration Tests

This directory contains integration tests for the CockroachDB Ansible Collection.

## Test Files

The testing framework includes several test files:

- **consolidated_tests.yml** - Main, modular test framework with configurable test modes
- **integration_tests.yml** - Basic tests for core functionality (legacy)
- **comprehensive_tests.yml** - Complete tests for all modules (legacy)
- **simplified_tests.yml** - Tests with variables and structured approach (legacy)

## Using the Consolidated Test Framework

The consolidated test framework supports three test modes:

1. **Basic Mode**: Tests only core modules (info, database, query)
2. **Standard Mode**: Tests common modules (info, database, user, privilege, table, index, query)
3. **Comprehensive Mode**: Tests all available modules

To run tests with the consolidated framework, use the `run_tests.sh` script:

```bash
# Run basic tests
./run_tests.sh -t integration -d basic

# Run standard tests (default)
./run_tests.sh -t integration

# Run comprehensive tests
./run_tests.sh -t integration -d comprehensive
```

## Environment Variables

The test framework supports the following environment variables:

```
CRDB_TEST_MODE         # Test mode: basic, standard, comprehensive
COCKROACH_HOST         # Database host (default: localhost)
COCKROACH_PORT         # Database port (default: 26257)
COCKROACH_USER         # Database user (default: root)
COCKROACH_PASSWORD     # Database password
COCKROACH_SSL_MODE     # SSL mode (default: disable)
COCKROACH_SSL_CERT     # SSL certificate path
COCKROACH_SSL_KEY      # SSL key path
COCKROACH_SSL_ROOTCERT # SSL root certificate path
```

## Test Inventory

The test inventory file (`inventory`) defines the hosts that will be used for integration testing.

## Test Configuration

The `integration_config.yml` file lists all modules that are available for testing.
