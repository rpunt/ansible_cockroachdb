## License

Apache License 2.0

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Author Information

This collection is maintained by Cockroach Labs.

## Installation and Usage

### Installing the Collection from Ansible Galaxy

Before using the CockroachDB collection, you need to install it with the `ansible-galaxy` CLI:

```bash
ansible-galaxy collection install cockroach_labs.cockroachdb
```

You can also include it in a `requirements.yml` file and install it via `ansible-galaxy collection install -r requirements.yml` using the format:

```yaml
collections:
- name: cockroach_labs.cockroachdb
```

### Building and Installing from Source

You can build and install the collection from source:

```bash
# Clone the repository
git clone https://github.com/yourusername/ansible-cockroachdb.git
cd ansible-cockroachdb

# Build the collection
ansible-galaxy collection build --force

# Install the collection globally
ansible-galaxy collection install cockroach_labs-cockroachdb-*.tar.gz -f
```

Alternatively, you can use the provided script:

```bash
./build_and_install.sh
```

### Using the Collection

Once installed, you can reference modules in your playbooks:

```yaml
- name: Manage CockroachDB parameters
  cockroach_labs.cockroachdb.cockroachdb_parameter:
    parameters:
      sql.defaults.distsql: "on"
      kv.rangefeed.enabled: true
    host: localhost
    port: 26257
    user: root
    ssl_mode: disable
```

## Testing

### Running Tests

This collection includes various types of tests that can be run to ensure everything works correctly:

#### Integration Tests

Integration tests verify that the modules work correctly with an actual CockroachDB instance.

```bash
# Run integration tests (default mode - Podman)
./run_tests.sh --type integration

# Run with local mode (advanced option)
./run_tests.sh --mode local --type integration
```

> **Note:** Podman is the default and recommended testing environment as it provides consistent and isolated testing conditions.

#### Unit Tests

Unit tests verify individual module functions without requiring an actual CockroachDB instance.

```bash
# Run unit tests
./run_tests.sh --type unit
```

#### Sanity Tests

Sanity tests check for code quality and documentation standards.

```bash
# Run sanity tests
./run_tests.sh --type sanity
```

#### Test Environment

For integration tests, a CockroachDB instance is required. By default, tests use Podman Compose to start a local CockroachDB instance for testing. You can also run tests with the `--container` option to use containerized CockroachDB even in local mode. See docker-compose.yml for details (compatible with Podman).

#### Test Coverage

To run tests with coverage reports:

```bash
# Run unit tests with coverage
./run_tests.sh --type unit --coverage

# Run all tests with coverage
./run_tests.sh --type all --coverage
```

Coverage reports are generated in the tests/output/coverage/ directory.
