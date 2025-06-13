# cockroachdb_parameter

Manage CockroachDB cluster parameters

## Description

This module allows you to manage multiple CockroachDB cluster parameters at once. It supports setting, updating, or resetting cluster parameters as well as applying parameter profiles optimized for different workloads.

The module ensures proper change tracking and provides detailed output about which parameters were changed, making it suitable for idempotent operations and integration into CI/CD pipelines.

The module intelligently handles different data types and formats, ensuring that parameters are only marked as changed when their actual values differ. This includes special handling for:

- Boolean values vs. string representations ("true"/"on"/etc.)
- Numeric values with different formats
- Time duration values in different formats (e.g., "5m", "300s", "300000ms", "0.0833h" all represent the same duration)
- Complex time durations (e.g., "1h30m", "2h15m30s")

## Parameters

| Parameter | Required | Type | Choices | Default | Description |
|-----------|----------|------|---------|---------|-------------|
| parameters | no | dict | | | Dictionary of parameter names and their values to set. Use null/None as value to reset a parameter to default. |
| profile | no | str | oltp, olap, hybrid, low_latency, high_throughput, web_application, batch_processing | | Apply a predefined parameter profile for specific workload types. Setting a profile will apply a group of recommended parameter values at once. |
| scope | no | str | cluster, session | cluster | Scope for the parameters (cluster or session) |
| reset_all | no | bool | | false | Reset all session or cluster parameters to default. USE WITH CAUTION - this will reset ALL settings, including critical ones. |
| host | no | str | | localhost | Database host address |
| port | no | int | | 26257 | Database port number |
| user | no | str | | root | Database username |
| password | no | str | | | Database user password |
| ssl_mode | no | str | disable, allow, prefer, require, verify-ca, verify-full | verify-full | SSL connection mode |
| ssl_cert | no | path | | | Path to client certificate file |
| ssl_key | no | path | | | Path to client private key file |
| ssl_rootcert | no | path | | | Path to CA certificate file |

## Requirements

- psycopg2

## Examples

```yaml
# Set multiple cluster parameters
- name: Configure multiple cluster parameters
  cockroachdb_parameter:
    parameters:
      sql.defaults.distsql: "on"
      sql.distsql.distribute_index_joins: "on"
      kv.range_merge.queue_enabled: true
      sql.defaults.optimizer: "on"
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt

# Apply an OLTP optimization profile
- name: Apply OLTP optimization profile
  cockroachdb_parameter:
    profile: oltp
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt

# Reset a parameter to default
- name: Reset parameter to default
  cockroachdb_parameter:
    parameters:
      sql.defaults.distsql: null
    host: localhost
    port: 26257
    user: root

# Set session parameters
- name: Set session parameters
  cockroachdb_parameter:
    parameters:
      application_name: "ansible-deployment"
      statement_timeout: "10s"
      idle_in_transaction_session_timeout: "60s"
    scope: session
    host: localhost
    port: 26257
    user: root

# Set time duration parameters
- name: Set time duration parameters with different formats
  cockroachdb_parameter:
    parameters:
      server.time_until_store_dead: "5m"  # Can also be specified as "300s" or "300000ms"
      kv.closed_timestamp.target_duration: "1h30m"  # Complex duration format
    host: localhost
    port: 26257
    user: root
```

## Return Values

| Key | Returned | Type | Description |
|-----|----------|------|-------------|
| changed | always | bool | Whether any parameters were changed |
| parameters | always | dict | Parameters that were changed |
| profile | when profile is specified | str | Parameter profile that was applied |
| reset | when parameters are reset | list | List of parameters that were reset to default values |
| reset_all | when reset_all is true | bool | Whether all parameters were reset |
| debug | always | dict | Debug information to help with troubleshooting |

## Notes

- This module returns the parameters that were actually changed rather than all parameters that were requested.
- When using a profile, the module will apply all parameters in the profile but only report the ones that actually changed.
- The module supports check mode, allowing you to preview changes without applying them.
- The module implements intelligent comparison for different data types to ensure proper idempotency.
- Time duration formats like "5m", "300s", "300000ms" are normalized for comparison.
- Complex time durations like "1h30m" or "2h15m30s" are properly handled.
- Debug information contains detailed comparison data to help troubleshoot why a parameter was changed.
