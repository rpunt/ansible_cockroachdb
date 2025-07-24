# CockroachDB Ansible Collection - AI Agent Instructions

This document provides essential information for AI agents working with the CockroachDB Ansible collection.

## Project Overview

This is an Ansible collection for managing CockroachDB databases. It provides modules for installation, configuration, maintenance, and monitoring of CockroachDB clusters.

## Project Architecture

- **plugins/modules/**: Contains individual Ansible modules for specific CockroachDB tasks
  - Follows standard Ansible module format (Python classes with documentation and argument specs)
  - Example: `cockroachdb_parameter.py` manages cluster parameters
- **plugins/module_utils/**: Shared utilities for modules
  - `cockroachdb.py`: Core helper class for database connections and operations
- **examples/**: Example playbooks demonstrating module usage
- **tests/**: Integration, unit, and sanity tests
  - Uses Podman/Docker for containerized testing environments

## Development Workflows

### Building and Installing

```bash
# Build and install the collection locally
./build_and_install.sh

# Or manually:
ansible-galaxy collection build --force
ansible-galaxy collection install rpunt-cockroachdb-*.tar.gz -f
```

### Testing

```bash
# Run all tests (uses Podman by default)
./run_tests.sh

# Run specific test types
./run_tests.sh --type integration
./run_tests.sh --type unit
./run_tests.sh --type sanity

# Run tests with coverage reports
./run_tests.sh --type all --coverage
```

## Coding Conventions

1. **Module Structure**: Each module follows the standard Ansible module pattern:
   - Documentation in YAML format at the top
   - `DOCUMENTATION`, `EXAMPLES`, and `RETURN` variables
   - `AnsibleModule` instance for argument parsing
   - Main function with error handling
   - Call to `run_module()` in the `if __name__ == '__main__':` block

2. **Error Handling**: Use `module.fail_json()` with informative error messages and include exception details when applicable:
   ```python
   except Exception as e:
       module.fail_json(msg="Error executing query", exception=to_native(e))
   ```

3. **Connection Management**: Use the `CockroachDBHelper` class from `module_utils/cockroachdb.py` for database connections:
   ```python
   from ansible_collections.rpunt.cockroachdb.plugins.module_utils.cockroachdb import CockroachDBHelper
   ```

4. **SQL Injection Prevention**: Always use parameterized queries and validate identifiers:
   ```python
   if not is_valid_identifier(table_name):
       module.fail_json(msg=f"Invalid table name: {table_name}")
   ```

## Integration Points

1. **Module Parameters**: Common connection parameters are used across all modules:
   - `host`, `port`, `user`, `password`, `database`, `ssl_mode`, etc.

2. **External Dependencies**:
   - psycopg2 for PostgreSQL-compatible database connections
   - Standard Python libraries (no exotic dependencies)

## Testing Guidelines

1. The test environment uses Podman (default) or Docker to spin up CockroachDB instances
2. Each module should have integration tests that verify actual behavior with a database
3. Unit tests should mock the database connection when possible
