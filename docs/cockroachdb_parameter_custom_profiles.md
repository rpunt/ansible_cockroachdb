# Custom Parameter Profiles for CockroachDB

The `cockroachdb_parameter` module now supports user-defined custom parameter profiles in addition to the built-in profiles.

## Overview

Parameter profiles allow you to apply a set of related parameters with a single profile name, making it easier to:

- Standardize configurations across environments
- Apply vendor or organization-specific tuning recommendations
- Override built-in profiles with custom values
- Share configuration profiles between teams

## Built-in Profiles

The module includes these built-in profiles:

- `oltp` - Optimized for online transaction processing
- `olap` - Optimized for analytical queries
- `hybrid` - Balanced for mixed workloads
- `low_latency` - Optimized for low latency applications
- `high_throughput` - Maximizing throughput
- `web_application` - Typical web application workloads
- `batch_processing` - Batch job processing

## Custom Profiles

### Basic Usage

Define custom profiles using the `custom_profiles` parameter:

```yaml
- name: Apply custom performance profile
  cockroachdb_parameter:
    profile: my_custom_profile
    custom_profiles:
      my_custom_profile:
        sql.defaults.distsql: "on"
        kv.rangefeed.enabled: true
        server.time_until_store_dead: "3m"
        kv.closed_timestamp.target_duration: "500ms"
    host: localhost
    port: 26257
    user: root
    ssl_mode: disable
```

### Multiple Custom Profiles

You can define multiple custom profiles in a single task:

```yaml
- name: Define multiple custom profiles
  cockroachdb_parameter:
    profile: production_tuned
    custom_profiles:
      production_tuned:
        sql.defaults.distsql: "on"
        kv.snapshot_rebalance.max_rate: "128MiB"
        kv.bulk_io_write.max_rate: "1GiB"
      development_mode:
        sql.defaults.distsql: "auto"
        server.time_until_store_dead: "1m"
      testing_profile:
        sql.defaults.distsql: "off"
        kv.rangefeed.enabled: false
    host: localhost
    port: 26257
    user: root
    ssl_mode: disable
```

### Overriding Built-in Profiles

Custom profiles can override built-in profile names:

```yaml
- name: Override built-in OLTP profile
  cockroachdb_parameter:
    profile: oltp  # Same name as built-in profile
    custom_profiles:
      oltp:
        # Your custom OLTP configuration
        sql.defaults.distsql: "auto"  # Different from built-in
        kv.rangefeed.enabled: true
        # Add your own parameters
        server.web_session_timeout: "4h"
    host: localhost
    port: 26257
    user: root
    ssl_mode: disable
```

### Combining Profiles with Additional Parameters

Individual parameters take precedence over profile parameters:

```yaml
- name: Apply profile and override specific parameters
  cockroachdb_parameter:
    profile: my_base_profile
    custom_profiles:
      my_base_profile:
        sql.defaults.distsql: "on"
        kv.rangefeed.enabled: true
        server.time_until_store_dead: "5m"
    parameters:
      # This will override the profile value
      server.time_until_store_dead: "2m"
      # This will be added to the profile parameters
      sql.defaults.optimizer: "on"
    host: localhost
    port: 26257
    user: root
    ssl_mode: disable
```

## Return Values

When using custom profiles, the module returns additional information:

```yaml
# Example return values
{
  "changed": true,
  "profile": "my_custom_profile",
  "custom_profile_used": true,
  "available_custom_profiles": ["my_custom_profile", "other_profile"],
  "parameters": {
    "sql.defaults.distsql": "on",
    "server.time_until_store_dead": "3m"
  }
}
```

## Best Practices

### 1. Use Descriptive Profile Names

```yaml
custom_profiles:
  production_high_performance:
    # High-performance production settings
  development_debugging:
    # Development-friendly settings
  compliance_secure:
    # Security-focused settings
```

### 2. Document Your Profiles

```yaml
custom_profiles:
  # Production profile for OLTP workloads with high availability requirements
  production_oltp_ha:
    sql.defaults.distsql: "on"
    kv.rangefeed.enabled: true
    server.time_until_store_dead: "5m"
    kv.closed_timestamp.target_duration: "1s"

  # Development profile for fast iteration and debugging
  development_fast:
    sql.defaults.distsql: "auto"
    server.time_until_store_dead: "1m"
```

### 3. Version Control Your Profiles

Store your custom profiles in version-controlled files:

```yaml
# profiles.yml
cockroach_custom_profiles:
  production_oltp:
    sql.defaults.distsql: "on"
    kv.rangefeed.enabled: true
  production_olap:
    sql.defaults.distsql: "on"
    kv.closed_timestamp.target_duration: "3s"
```

Then use them in your playbooks:

```yaml
- name: Load custom profiles
  include_vars: profiles.yml

- name: Apply production OLTP profile
  cockroachdb_parameter:
    profile: production_oltp
    custom_profiles: "{{ cockroach_custom_profiles }}"
    host: "{{ inventory_hostname }}"
    port: 26257
    user: root
    ssl_mode: disable
```

### 4. Validate Profile Parameters

Always test your custom profiles in a development environment first:

```yaml
- name: Validate custom profile parameters
  cockroachdb_parameter:
    profile: my_new_profile
    custom_profiles:
      my_new_profile:
        sql.defaults.distsql: "on"
        # Test parameters here first
    host: dev-cluster.example.com
    port: 26257
    user: root
    ssl_mode: disable
  check_mode: true  # Test without applying changes
```

## Error Handling

The module provides helpful error messages for invalid profiles:

```yaml
- name: Try to use non-existent profile
  cockroachdb_parameter:
    profile: typo_in_profile_name
    custom_profiles:
      correct_profile_name:
        sql.defaults.distsql: "on"
    host: localhost
    port: 26257
    user: root
    ssl_mode: disable
  # Will fail with: "Profile 'typo_in_profile_name' not found.
  # Available profiles: ['oltp', 'olap', ..., 'correct_profile_name']"
```

## Migration from Built-in Profiles

To migrate from a built-in profile to a custom one:

1. Check what parameters the built-in profile sets:

   ```bash
   # Look at the module source or use debug mode
   ansible-playbook your-playbook.yml -vvv
   ```

2. Create a custom profile with your modifications:

   ```yaml
   custom_profiles:
     my_oltp:
       # Start with built-in OLTP parameters
       sql.defaults.distsql: "on"
       kv.rangefeed.enabled: true
       kv.closed_timestamp.target_duration: "1s"
       server.time_until_store_dead: "5m"
       # Add your customizations
       sql.defaults.optimizer: "on"
       server.web_session_timeout: "4h"
   ```

3. Update your playbooks to use the custom profile:

   ```yaml
   - name: Apply custom OLTP profile
     cockroachdb_parameter:
       profile: my_oltp  # Changed from 'oltp'
       custom_profiles:
         my_oltp:
           # Your parameters here
   ```

This approach gives you full control over your CockroachDB parameter configurations while maintaining the convenience of profile-based management.
