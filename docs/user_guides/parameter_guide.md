# Using the cockroachdb_parameter Module

The `cockroachdb_parameter` module allows you to efficiently manage CockroachDB cluster parameters either individually or by applying predefined workload-specific parameter profiles. This guide provides examples and best practices for using the module.

> **Note:** The `cockroachdb_parameter` module is the recommended way to manage all cluster settings. The older `cockroachdb_cluster` module has been removed as it provided less functionality than `cockroachdb_parameter`.

> **Working with Byte Size Parameters:** For detailed information about working with byte size parameters (like `1GiB`, `64MiB`, etc.) and handling different formats, see the [Byte Size Parameters Guide](parameter_byte_sizes.md).

## Prerequisites

- Ansible 2.9 or higher
- Python's psycopg2 package installed
- Access to a CockroachDB cluster with appropriate permissions

## Basic Usage

### Setting Individual Parameters

You can set multiple parameters in a single task:

```yaml
- name: Configure query execution parameters
  cockroachdb_parameter:
    parameters:
      sql.defaults.distsql: "on"
      kv.rangefeed.enabled: true
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt
```

### Applying Parameter Profiles

Apply predefined settings optimized for specific workloads:

```yaml
- name: Apply OLTP optimization profile
  cockroachdb_parameter:
    profile: oltp
    host: localhost
    port: 26257
    user: root
```

Available profiles include:

- `oltp` - Online Transaction Processing
- `olap` - Analytical Processing
- `hybrid` - Mixed workloads
- `low_latency` - Optimized for minimal latency
- `high_throughput` - Optimized for maximum throughput
- `web_application` - Web application workloads
- `batch_processing` - Batch processing jobs

### Resetting Parameters

Reset a parameter to its default value:

```yaml
- name: Reset parameter to default
  cockroachdb_parameter:
    parameters:
      sql.defaults.distsql: null
    host: localhost
    port: 26257
    user: root
```

Reset all parameters (use with caution):

```yaml
- name: Reset all cluster parameters to default
  cockroachdb_parameter:
    reset_all: true
    scope: cluster
    host: localhost
    port: 26257
    user: root
```

## Advanced Usage

### Session Parameters

Set session-level parameters:

```yaml
- name: Set session parameters
  cockroachdb_parameter:
    parameters:
      application_name: "inventory-service"
      statement_timeout: "10s"
    scope: session
    host: localhost
    port: 26257
    user: root
```

### Using Check Mode

Check mode allows you to preview changes without applying them:

```bash
ansible-playbook your_playbook.yml --check
```

### Handling Sensitive Information

For secure connections with passwords:

```yaml
- name: Configure parameters with password
  cockroachdb_parameter:
    parameters:
      sql.defaults.distsql: "on"
    host: localhost
    port: 26257
    user: root
    password: "{{ cockroach_password }}"
    ssl_mode: require
  no_log: true  # Prevents password from being logged
```

## Troubleshooting

The module provides debug information that can help troubleshoot issues:

```yaml
- name: Configure parameters
  cockroachdb_parameter:
    parameters:
      sql.defaults.distsql: "on"
    host: localhost
    port: 26257
    user: root
  register: result

- name: Display debug information
  debug:
    var: result.debug
```

Common issues:

1. **Parameter not found**: Verify that the parameter name is correct for your CockroachDB version
2. **Permission denied**: Ensure the user has required privileges
3. **Connection issues**: Check network connectivity and SSL configuration

## Best Practices

1. **Use parameter profiles** for common workload types rather than setting individual parameters
2. **Test changes in non-production** environments first
3. **Document your parameter changes** for future reference
4. **Use check mode** to preview changes
5. **Consider session parameters** for application-specific settings
6. **Use result tracking** to monitor which parameters actually changed

For more information, see [CockroachDB Cluster Settings](https://www.cockroachlabs.com/docs/stable/cluster-settings.html).
