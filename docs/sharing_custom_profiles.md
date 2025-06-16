# Sharing Custom Profiles Across All Hosts in Inventory

This document shows different approaches for making custom parameter profiles available to all hosts in your Ansible inventory.

## Approach 1: Group Variables (Recommended)

Create group variables that contain your custom profiles:

### group_vars/all.yml

```yaml
---
# Global custom profiles available to all hosts
cockroach_custom_profiles:
  production_oltp:
    sql.defaults.distsql: "on"
    kv.rangefeed.enabled: true
    server.time_until_store_dead: "5m"
    kv.closed_timestamp.target_duration: "1s"

  production_olap:
    sql.defaults.distsql: "on"
    kv.closed_timestamp.target_duration: "3s"
    server.time_until_store_dead: "10m"

  development_mode:
    sql.defaults.distsql: "auto"
    server.time_until_store_dead: "1m"
    kv.closed_timestamp.target_duration: "100ms"

  testing_profile:
    sql.defaults.distsql: "off"
    kv.rangefeed.enabled: false
    server.time_until_store_dead: "30s"
```

### group_vars/cockroach_prod.yml

```yaml
---
# Production-specific profiles
cockroach_custom_profiles:
  high_performance:
    sql.defaults.distsql: "on"
    kv.snapshot_rebalance.max_rate: "256MiB"
    kv.bulk_io_write.max_rate: "2GiB"
    server.time_until_store_dead: "5m"

  compliance_mode:
    sql.log.slow_query.latency_threshold: "1s"
    server.web_session_timeout: "30m"
    sql.defaults.distsql: "on"
```

### Your playbook

```yaml
---
- name: Configure CockroachDB with shared custom profiles
  hosts: cockroach_nodes
  tasks:
    - name: Apply production OLTP profile to all production hosts
      cockroachdb_parameter:
        profile: production_oltp
        custom_profiles: "{{ cockroach_custom_profiles }}"
        host: "{{ inventory_hostname }}"
        port: 26257
        user: root
        ssl_mode: disable

    - name: Apply different profiles based on host groups
      cockroachdb_parameter:
        profile: "{{ cockroach_profile | default('production_oltp') }}"
        custom_profiles: "{{ cockroach_custom_profiles }}"
        host: "{{ inventory_hostname }}"
        port: 26257
        user: root
        ssl_mode: disable
```

## Approach 2: Host Variables

Define profiles per host or host group:

### host_vars/cockroach-01.yml

```yaml
---
cockroach_profile: production_oltp
cockroach_custom_profiles:
  production_oltp:
    sql.defaults.distsql: "on"
    kv.rangefeed.enabled: true
    # Host-specific optimizations
    server.time_until_store_dead: "3m"
```

### host_vars/cockroach-dev-01.yml

```yaml
---
cockroach_profile: development_mode
cockroach_custom_profiles:
  development_mode:
    sql.defaults.distsql: "auto"
    server.time_until_store_dead: "1m"
```

## Approach 3: Include Variables Files

Store profiles in dedicated files and include them:

### vars/cockroach_profiles.yml

```yaml
---
cockroach_custom_profiles:
  web_application:
    sql.defaults.distsql: "auto"
    server.web_session_timeout: "2h"
    kv.rangefeed.enabled: true
    sql.defaults.optimizer: "on"

  batch_processing:
    sql.defaults.distsql: "on"
    kv.bulk_io_write.max_rate: "1GiB"
    sql.defaults.vectorize: "on"

  microservices:
    sql.defaults.distsql: "on"
    kv.rangefeed.enabled: true
    server.time_until_store_dead: "2m"
    sql.defaults.serial_normalization: "sql_sequence"
```

### Your playbook

```yaml
---
- name: Configure CockroachDB with included profiles
  hosts: cockroach_nodes
  vars_files:
    - vars/cockroach_profiles.yml
  tasks:
    - name: Apply custom profiles from vars file
      cockroachdb_parameter:
        profile: "{{ cockroach_profile }}"
        custom_profiles: "{{ cockroach_custom_profiles }}"
        host: "{{ inventory_hostname }}"
        port: 26257
        user: root
        ssl_mode: disable
```

## Approach 4: Inventory Variables

Define profiles directly in your inventory file:

### inventory.ini

```ini
[cockroach_prod]
cockroach-prod-01 cockroach_profile=production_oltp
cockroach-prod-02 cockroach_profile=production_oltp
cockroach-prod-03 cockroach_profile=production_olap

[cockroach_dev]
cockroach-dev-01 cockroach_profile=development_mode

[cockroach_prod:vars]
cockroach_custom_profiles={"production_oltp":{"sql.defaults.distsql":"on","kv.rangefeed.enabled":true},"production_olap":{"sql.defaults.distsql":"on","kv.closed_timestamp.target_duration":"3s"}}

[cockroach_dev:vars]
cockroach_custom_profiles={"development_mode":{"sql.defaults.distsql":"auto","server.time_until_store_dead":"1m"}}
```

## Approach 5: Role-Based Profiles

Create an Ansible role that manages profiles:

### roles/cockroach_config/defaults/main.yml

```yaml
---
# Default custom profiles for the role
cockroach_custom_profiles:
  role_default:
    sql.defaults.distsql: "on"
    kv.rangefeed.enabled: true

# Allow override of profiles
cockroach_profile: role_default
```

### roles/cockroach_config/vars/main.yml

```yaml
---
# Role-specific profiles that extend or override defaults
cockroach_role_profiles:
  high_availability:
    sql.defaults.distsql: "on"
    kv.rangefeed.enabled: true
    server.time_until_store_dead: "5m"
    kv.closed_timestamp.target_duration: "1s"

  analytics_optimized:
    sql.defaults.distsql: "on"
    sql.defaults.vectorize: "on"
    kv.closed_timestamp.target_duration: "5s"
```

### roles/cockroach_config/tasks/main.yml

```yaml
---
- name: Merge role profiles with custom profiles
  set_fact:
    merged_profiles: "{{ cockroach_custom_profiles | combine(cockroach_role_profiles, recursive=True) }}"

- name: Apply CockroachDB configuration with merged profiles
  cockroachdb_parameter:
    profile: "{{ cockroach_profile }}"
    custom_profiles: "{{ merged_profiles }}"
    host: "{{ inventory_hostname }}"
    port: 26257
    user: root
    ssl_mode: disable
```

### Using the role in your playbook

```yaml
---
- name: Configure CockroachDB using role
  hosts: cockroach_nodes
  roles:
    - role: cockroach_config
      vars:
        cockroach_profile: high_availability
        cockroach_custom_profiles:
          # These will be merged with role defaults
          custom_production:
            sql.defaults.distsql: "on"
            kv.snapshot_rebalance.max_rate: "128MiB"
```

## Approach 6: Dynamic Profile Selection

Select profiles based on host facts or groups:

```yaml
---
- name: Configure CockroachDB with dynamic profile selection
  hosts: cockroach_nodes
  vars:
    cockroach_custom_profiles:
      small_cluster:
        sql.defaults.distsql: "auto"
        server.time_until_store_dead: "2m"
      large_cluster:
        sql.defaults.distsql: "on"
        kv.snapshot_rebalance.max_rate: "256MiB"
        server.time_until_store_dead: "5m"
      ssd_optimized:
        kv.bulk_io_write.max_rate: "2GiB"
        kv.snapshot_recovery.max_rate: "256MiB"
  tasks:
    - name: Determine profile based on cluster size and storage
      set_fact:
        selected_profile: >-
          {%- if groups['cockroach_nodes'] | length < 3 -%}
            small_cluster
          {%- elif ansible_devices.sda.model is search('SSD') -%}
            ssd_optimized
          {%- else -%}
            large_cluster
          {%- endif -%}

    - name: Apply dynamically selected profile
      cockroachdb_parameter:
        profile: "{{ selected_profile }}"
        custom_profiles: "{{ cockroach_custom_profiles }}"
        host: "{{ inventory_hostname }}"
        port: 26257
        user: root
        ssl_mode: disable
```

## Best Practices Summary

1. **Use group_vars/all.yml** for profiles that should be available everywhere
2. **Use group_vars/[group].yml** for group-specific profiles
3. **Use host_vars** for host-specific customizations
4. **Version control** your profile definitions
5. **Document** what each profile is intended for
6. **Test profiles** in development before applying to production
7. **Use meaningful names** that describe the workload or environment
8. **Combine approaches** as needed for complex environments

## Example Complete Setup

### group_vars/all.yml

```yaml
cockroach_base_profiles:
  standard_oltp:
    sql.defaults.distsql: "on"
    kv.rangefeed.enabled: true
  standard_olap:
    sql.defaults.distsql: "on"
    sql.defaults.vectorize: "on"
```

### group_vars/production.yml

```yaml
cockroach_env_profiles:
  prod_secure:
    sql.log.slow_query.latency_threshold: "1s"
    server.web_session_timeout: "1h"
```

### site.yml

```yaml
---
- name: Configure CockroachDB across all environments
  hosts: cockroach_nodes
  vars:
    # Merge base and environment-specific profiles
    cockroach_custom_profiles: "{{ cockroach_base_profiles | combine(cockroach_env_profiles | default({}), recursive=True) }}"
  tasks:
    - name: Apply configuration with merged profiles
      cockroachdb_parameter:
        profile: "{{ cockroach_node_profile | default('standard_oltp') }}"
        custom_profiles: "{{ cockroach_custom_profiles }}"
        host: "{{ inventory_hostname }}"
        port: 26257
        user: root
        ssl_mode: disable
```

This way, all hosts in your inventory can access the same set of custom profiles, but you have the flexibility to customize them per environment, group, or individual host as needed.
