#!/usr/bin/python
# -*- coding: utf-8 -*-
# pylint: disable=line-too-long, broad-exception-caught

# Copyright: (c) 2025, Cockroach Labs
# Apache License, Version 2.0 (see LICENSE or http://www.apache.org/licenses/LICENSE-2.0)

"""
Ansible module for managing CockroachDB cluster parameters.

This module allows managing cluster and session parameters in a CockroachDB cluster,
including setting individual parameters, applying parameter profiles for specific
workloads, and resetting parameters to their default values.

The documentation for this module is maintained in the plugins/docs/cockroachdb_parameter.yml file.
"""

import datetime
import traceback
import re
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_native
try:
    from ansible_collections.rpunt.cockroachdb.plugins.module_utils.cockroachdb import (
        CockroachDBHelper,
        COCKROACHDB_IMP_ERR,
        HAS_PSYCOPG2,
    )
except ImportError:
    # This is handled in the module
    pass

ANSIBLE_METADATA = {
    "metadata_version": "1.1",
    "status": ["preview"],
    "supported_by": "cockroach_labs",
}

# Helper function to normalize time duration strings or objects
def normalize_duration(duration_val):
    """
    Convert duration strings or timedelta objects to a standard format (seconds as float)
    Input examples: '5m', '300ms', '1h', '60s', '1h30m', '2h15m30s', timedelta object
    Returns standardized duration in seconds as float
    """
    # Handle timedelta objects
    if isinstance(duration_val, datetime.timedelta):
        return duration_val.total_seconds()

    # Handle string durations
    if not isinstance(duration_val, str):
        return None

    # Handle complex duration formats like "1h30m" or "2h15m30s"
    # This regex matches patterns like 1h, 30m, 2h15m30s, etc.
    complex_pattern = r'(?:(\d+(?:\.\d+)?)([a-z]+))'
    matches = re.findall(complex_pattern, duration_val.lower())

    if matches:
        total_seconds = 0.0
        for value, unit in matches:
            value = float(value)
            # Convert to seconds based on unit
            if unit == 'ns':
                total_seconds += value / 1_000_000_000
            elif unit == 'us' or unit == 'µs':
                total_seconds += value / 1_000_000
            elif unit == 'ms':
                total_seconds += value / 1_000
            elif unit == 's':
                total_seconds += value
            elif unit == 'm':
                total_seconds += value * 60
            elif unit == 'h':
                total_seconds += value * 3600
            elif unit == 'd':
                total_seconds += value * 86400
            else:
                # Unrecognized unit, return None
                return None
        return total_seconds

    # If not a complex format, check for simple format
    simple_pattern = r'^(\d+(?:\.\d+)?)([a-z]+)$'
    match = re.match(simple_pattern, duration_val.lower())

    if not match:
        return None

    value, unit = match.groups()
    value = float(value)

    # Convert to seconds based on unit
    if unit == 'ns':
        return value / 1_000_000_000
    elif unit == 'us' or unit == 'µs':
        return value / 1_000_000
    elif unit == 'ms':
        return value / 1_000
    elif unit == 's':
        return value
    elif unit == 'm':
        return value * 60
    elif unit == 'h':
        return value * 3600
    elif unit == 'd':
        return value * 86400
    else:
        return None

# Helper function to compare duration values
def durations_equal(duration1, duration2):
    """
    Compare if two duration values represent the same amount of time
    Handles both string durations and timedelta objects
    """
    seconds1 = normalize_duration(duration1)
    seconds2 = normalize_duration(duration2)

    # If both can be normalized, compare the normalized values
    if seconds1 is not None and seconds2 is not None:
        # Use a reasonable epsilon for floating point comparison
        # For small durations (< 1min), use 0.01s
        # For larger durations, allow 0.1% difference
        if max(seconds1, seconds2) < 60:
            epsilon = 0.01  # 10ms
        else:
            epsilon = max(seconds1, seconds2) * 0.001  # 0.1% of the duration

        return abs(seconds1 - seconds2) < epsilon

    # Otherwise, fall back to string comparison
    return str(duration1) == str(duration2)

# Helper function to normalize byte size strings
def normalize_byte_size(size_val):
    """
    Normalize byte size strings by removing spaces and converting to lowercase
    for comparison purposes. Also handles various decimal point formatting.

    Examples:
    - "1.0 GiB" -> "1gib"
    - "1.00GiB" -> "1gib"
    - "64 MiB" -> "64mib"
    - "1.5 GiB" -> "1.5gib" (preserves actual decimal values)
    """
    if isinstance(size_val, str) and size_val.strip():  # Check if it's a non-empty string
        # Remove spaces and convert to lowercase for comparison
        normalized = re.sub(r'\s+', '', size_val.lower())

        # Handle integer values with decimal points (e.g., "1.0gib" -> "1gib")
        # Match whole numbers with decimal point and zero(s) after
        normalized = re.sub(r'(\d+)\.0+([kmgt]i?b)', r'\1\2', normalized)

        # Handle decimal fractions with trailing zeros (e.g., "1.50gib" -> "1.5gib")
        # This preserves the real decimal part while removing trailing zeros
        normalized = re.sub(r'(\d+\.\d+?)0+([kmgt]i?b)', r'\1\2', normalized)

        return normalized
    return None

# Helper function to compare byte size values
def byte_sizes_equal(size1, size2):
    """
    Compare if two byte size strings are equivalent
    by normalizing them first (removing spaces, case-insensitive)
    and comparing the normalized values.
    """
    norm1 = normalize_byte_size(size1)
    norm2 = normalize_byte_size(size2)

    if norm1 is not None and norm2 is not None:
        return norm1 == norm2

    # Fallback to string comparison if normalization fails
    return str(size1) == str(size2)

# Get CockroachDB cluster setting types for type-based comparisons
def get_setting_types(db_helper):
    """Get a dictionary of parameter names to their types from CockroachDB"""
    setting_types = {}

    # Define known byte size parameters (critical for idempotency)
    byte_size_params = [
        'kv.snapshot_rebalance.max_rate',
        'kv.snapshot_recovery.max_rate',
        'kv.bulk_io_write.max_rate'
    ]

    # Force known byte size parameters to always have type 'z'
    for param in byte_size_params:
        setting_types[param] = 'z'  # z = byte size

    # Get setting types directly from crdb_internal.cluster_settings
    # CockroachDB provides types as single letter codes:
    # 'b' (boolean), 'd' (duration), 'f' (float), 'i' (integer), 'z' (byte size), etc.
    try:
        query = "SELECT variable, type FROM crdb_internal.cluster_settings"
        results = db_helper.execute_query(query)

        if results:
            for variable, setting_type in results:
                # Store the type (lowercase for consistency)
                setting_types[variable] = setting_type.lower()

                # Force byte-size types to be 'z'
                if 'byte' in str(setting_type).lower():
                    setting_types[variable] = 'z'
    except Exception:
        pass  # If query fails, we'll still have our known byte size parameters

    return setting_types

# Predefined parameter profiles for various workloads
PARAMETER_PROFILES = {
    'oltp': {
        # Parameters optimized for online transaction processing
        'sql.defaults.distsql': 'on',
        'kv.rangefeed.enabled': True,
        'kv.closed_timestamp.target_duration': '1s',
        'server.time_until_store_dead': '5m'
    },
    'olap': {
        # Parameters optimized for analytical queries
        'sql.defaults.distsql': 'on',
        'kv.closed_timestamp.target_duration': '3s',
        'server.time_until_store_dead': '10m'
    },
    'hybrid': {
        # Parameters balanced for mixed workloads
        'sql.defaults.distsql': 'on',
        'kv.rangefeed.enabled': True,
        'kv.closed_timestamp.target_duration': '3s',
        'server.time_until_store_dead': '7m'
    },
    'low_latency': {
        # Parameters optimized for low latency applications
        'sql.defaults.distsql': 'on',
        'kv.closed_timestamp.target_duration': '300ms',
        'server.time_until_store_dead': '1m'
    },
    'high_throughput': {
        # Parameters for maximizing throughput
        'sql.defaults.distsql': 'on',
        'kv.snapshot_rebalance.max_rate': '64MiB',
        'kv.snapshot_recovery.max_rate': '64MiB'
    },
    'web_application': {
        # Parameters for typical web application workloads
        'sql.defaults.distsql': 'auto',
        'server.web_session_timeout': '2h',
        'kv.rangefeed.enabled': True
    },
    'batch_processing': {
        # Parameters for batch jobs
        'sql.defaults.distsql': 'on',
        'kv.snapshot_rebalance.max_rate': '64MiB',
        'kv.bulk_io_write.max_rate': '512MiB'
    }
}


def main():
    argument_spec = dict(
        parameters=dict(type='dict'),
        profile=dict(type='str'),  # Remove choices validation to allow custom profiles
        custom_profiles=dict(type='dict', default={}),
        scope=dict(type='str', default='cluster', choices=['cluster', 'session']),
        reset_all=dict(type='bool', default=False),
        host=dict(type='str', default='localhost'),
        port=dict(type='int', default=26257),
        user=dict(type='str', default='root'),
        password=dict(type='str', no_log=True),
        ssl_mode=dict(type='str', default='verify-full', choices=['disable', 'allow', 'prefer', 'require', 'verify-ca', 'verify-full']),
        ssl_cert=dict(type='path'),
        ssl_key=dict(type='path'),
        ssl_rootcert=dict(type='path'),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[['parameters', 'profile', 'reset_all']],
        mutually_exclusive=[['profile', 'reset_all'], ['parameters', 'reset_all']]
    )

    if not HAS_PSYCOPG2:
        module.fail_json(msg="The psycopg2 module is required", exception=COCKROACHDB_IMP_ERR)

    parameters = module.params['parameters']
    profile = module.params['profile']
    custom_profiles = module.params['custom_profiles']
    scope = module.params['scope']
    reset_all = module.params['reset_all']

    # Merge built-in profiles with custom profiles
    all_profiles = PARAMETER_PROFILES.copy()
    all_profiles.update(custom_profiles)

    # Validate profile exists if specified
    if profile and profile not in all_profiles:
        available_profiles = list(all_profiles.keys())
        module.fail_json(
            msg=f"Profile '{profile}' not found. Available profiles: {available_profiles}. "
                f"You can define custom profiles using the 'custom_profiles' parameter."
        )

    result = {
        'changed': False,
        'parameters': {},
        'debug': {
            'comparison_values': {}
        }
    }

    if profile:
        result['profile'] = profile
        if custom_profiles:
            result['available_custom_profiles'] = list(custom_profiles.keys())

    # Initialize the helper
    db = CockroachDBHelper(module)

    try:
        # Connect to the database
        db.connect()

        # Get CockroachDB setting types for type-based comparison
        setting_types = {}
        if scope == 'cluster':  # Only fetch types for cluster settings
            setting_types = get_setting_types(db)
            result['debug']['setting_types_available'] = len(setting_types) > 0

            # Print debug info about critical byte size parameters
            byte_size_params = ['kv.snapshot_rebalance.max_rate', 'kv.snapshot_recovery.max_rate', 'kv.bulk_io_write.max_rate']
            for param in byte_size_params:
                if param in setting_types:
                    result['debug'][f'{param}_type'] = setting_types[param]

        # Handle profile application
        if profile:
            profile_params = all_profiles[profile]

            # If parameters were also provided, merge them with profile parameters
            # Individual parameters take precedence over profile parameters
            if parameters:
                merged_params = profile_params.copy()
                merged_params.update(parameters)
                parameters = merged_params
            else:
                parameters = profile_params

            # Set up the profile in the result
            result['profile'] = profile
            if profile in custom_profiles:
                result['custom_profile_used'] = True

        # Handle setting parameters
        if parameters:
            reset_list = []
            changed_params = {}

            for name, value in parameters.items():
                if value is None:
                    # Reset parameter to default
                    reset_list.append(name)
                    if scope == 'cluster':
                        query = f"RESET CLUSTER SETTING {name}"
                    else:
                        query = f"RESET {name}"

                    if not module.check_mode:
                        db.execute_query(query)

                    result['changed'] = True
                    # Add to changed parameters with None value to indicate reset
                    changed_params[name] = None
                else:
                    # Set parameter value
                    # Convert boolean values properly for SQL
                    if isinstance(value, bool):
                        sql_value = "true" if value else "false"
                    else:
                        sql_value = f"'{value}'" if isinstance(value, str) else str(value)

                    # Get the current value of the parameter before making any changes
                    if scope == 'cluster':
                        current_value_query = f"SHOW CLUSTER SETTING {name}"
                    else:
                        current_value_query = f"SHOW {name}"

                    current_value = None
                    try:
                        # Set fail_on_error to False to handle unknown settings gracefully
                        current_value_result = db.execute_query(current_value_query, fail_on_error=False)
                        if current_value_result:
                            current_value = current_value_result[0][0]
                    except Exception as ex:
                        # Parameter might not exist, or we can't read it
                        if "unknown setting" in str(ex).lower():
                            module.fail_json(msg=f"Unknown setting: '{name}'. The specified parameter does not exist in this version of CockroachDB. Please check the parameter name or refer to the CockroachDB documentation for valid parameters.")
                        # For other exceptions, we'll continue and treat as a new parameter

                    # Compare values in a consistent way to ensure idempotency
                    is_changed = False

                    # Convert any non-serializable values to strings for debug info
                    requested_value = str(value) if value is not None else None
                    current_value_str = str(current_value) if current_value is not None else None

                    comparison_info = {
                        'name': name,
                        'requested_type': type(value).__name__,
                        'requested_value': requested_value,
                        'current_type': type(current_value).__name__ if current_value is not None else 'None',
                        'current_value': current_value_str,
                    }

                    # Handle case where we couldn't read the current value
                    if current_value is None:
                        is_changed = True
                        comparison_info['reason'] = 'current_value is None'

                    # Use type-based comparison if available
                    elif scope == 'cluster' and name in setting_types:
                        setting_type = setting_types[name]
                        comparison_info['setting_type'] = setting_type

                        # Byte size comparison (z)
                        if setting_type == 'z':
                            # Use the dedicated byte size comparison function
                            is_changed = not byte_sizes_equal(value, current_value)

                            # Add normalized values to debug info
                            norm_value = normalize_byte_size(str(value))
                            norm_current = normalize_byte_size(str(current_value))

                            comparison_info['normalized_requested'] = norm_value
                            comparison_info['normalized_current'] = norm_current
                            comparison_info['reason'] = 'byte_size_comparison (type-based)'

                        # Duration comparison (d)
                        elif setting_type == 'd':
                            is_changed = not durations_equal(value, current_value)
                            seconds_value = normalize_duration(value)
                            seconds_current = normalize_duration(current_value)
                            comparison_info['normalized_seconds_requested'] = seconds_value
                            comparison_info['normalized_seconds_current'] = seconds_current
                            comparison_info['reason'] = 'duration_comparison (type-based)'

                        # Boolean comparison (b)
                        elif setting_type == 'b':
                            if isinstance(value, bool) and isinstance(current_value, str):
                                current_bool = current_value.lower() in ('true', 't', 'yes', 'y', '1', 'on')
                                is_changed = value != current_bool
                                comparison_info['normalized_current'] = str(current_bool)
                            elif isinstance(value, str) and isinstance(current_value, bool):
                                value_bool = value.lower() in ('true', 't', 'yes', 'y', '1', 'on')
                                is_changed = value_bool != current_value
                                comparison_info['normalized_requested'] = str(value_bool)
                            else:
                                str_current = str(current_value).lower()
                                str_value = str(value).lower()
                                is_changed = str_current != str_value
                            comparison_info['reason'] = 'boolean_comparison (type-based)'

                        # Integer comparison (i)
                        elif setting_type == 'i':
                            try:
                                # Convert both to integers for comparison
                                int_value = int(float(str(value))) if not isinstance(value, bool) else (1 if value else 0)
                                int_current = int(float(str(current_value))) if not isinstance(current_value, bool) else (1 if current_value else 0)

                                is_changed = int_value != int_current
                                comparison_info['normalized_requested'] = str(int_value)
                                comparison_info['normalized_current'] = str(int_current)
                                comparison_info['reason'] = 'integer_comparison (type-based)'
                            except (ValueError, TypeError):
                                # Fallback to string comparison if conversion fails
                                str_current = str(current_value)
                                str_value = str(value)
                                is_changed = str_current != str_value
                                comparison_info['reason'] = 'integer_comparison_fallback (type-based)'

                        # Float comparison (f)
                        elif setting_type == 'f':
                            try:
                                # Convert both to floats for comparison
                                float_value = float(str(value)) if not isinstance(value, bool) else (1.0 if value else 0.0)
                                float_current = float(str(current_value)) if not isinstance(current_value, bool) else (1.0 if current_value else 0.0)

                                # Use a small epsilon for floating point comparison
                                epsilon = max(abs(float_value), abs(float_current)) * 0.0000001 or 0.0000001
                                is_changed = abs(float_value - float_current) > epsilon

                                comparison_info['normalized_requested'] = str(float_value)
                                comparison_info['normalized_current'] = str(float_current)
                                comparison_info['reason'] = 'float_comparison (type-based)'
                            except (ValueError, TypeError):
                                # Fallback to string comparison if conversion fails
                                str_current = str(current_value)
                                str_value = str(value)
                                is_changed = str_current != str_value
                                comparison_info['reason'] = 'float_comparison_fallback (type-based)'

                        # Default comparison for other types
                        else:
                            str_current = str(current_value)
                            str_value = str(value)
                            is_changed = str_current != str_value
                            comparison_info['reason'] = 'string_comparison (type-based)'

                    # Add debugging information
                    comparison_info['is_changed'] = is_changed
                    comparison_info['python_type_current'] = str(type(current_value).__name__) if current_value is not None else 'None'
                    comparison_info['python_type_requested'] = str(type(value).__name__) if value is not None else 'None'
                    result['debug']['comparison_values'][name] = comparison_info

                    # If a change is needed, execute it
                    if is_changed:
                        if scope == 'cluster':
                            query = f"SET CLUSTER SETTING {name} = {sql_value}"
                        else:
                            query = f"SET {name} = {sql_value}"

                        if not module.check_mode:
                            try:
                                # Will raise an exception if setting doesn't exist
                                db.execute_query(query, fail_on_error=True)
                                result['changed'] = True
                                # Add to changed parameters
                                changed_params[name] = value
                            except Exception as ex:
                                if "unknown setting" in str(ex).lower():
                                    module.fail_json(msg=f"Unknown setting: '{name}'. The specified parameter does not exist in this version of CockroachDB. Please check the parameter name or refer to the CockroachDB documentation for valid parameters.")
                                # Re-raise other exceptions
                                raise
                        else:
                            # In check mode, we assume it would work
                            result['changed'] = True
                            # Add to changed parameters
                            changed_params[name] = value
            # Update result with actual changed parameters
            result['parameters'] = changed_params

            if reset_list:
                result['reset'] = reset_list

        # Handle reset all parameters
        if reset_all:
            if scope == 'cluster':
                query = "RESET CLUSTER SETTING ALL"
            else:
                query = "RESET ALL"

            if not module.check_mode:
                db.execute_query(query)

            result['changed'] = True
            result['reset_all'] = True

    except Exception as e:
        module.fail_json(msg=f"Error setting parameters: {to_native(e)}", exception=traceback.format_exc())
    finally:
        if db.conn:
            db.close()                    # Add debug information to help with troubleshooting
    result['debug'].update({
        'requested_parameters': parameters,
        'profile_used': profile,
        'scope': scope,
        'reset_all': reset_all
    })

    module.exit_json(**result)


if __name__ == '__main__':
    main()
