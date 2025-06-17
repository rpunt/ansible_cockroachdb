#!/usr/bin/python
# -*- coding: utf-8 -*-
# pylint: disable=line-too-long, broad-exception-caught

# Copyright: (c) 2025, Cockroach Labs
# Apache License, Version 2.0 (see LICENSE or http://www.apache.org/licenses/LICENSE-2.0)

"""
Ansible module to manage CockroachDB statistics for query optimization.

This module allows you to create, delete, and configure statistics collection
for your CockroachDB tables and columns. Good statistics help the query optimizer
make better execution plan choices, resulting in faster queries.

For full documentation, see the plugins/docs/cockroachdb_statistics.yml file
"""

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_native
from ansible_collections.cockroach_labs.cockroachdb.plugins.module_utils.cockroachdb import (
    CockroachDBHelper,
    HAS_PSYCOPG2,
    COCKROACHDB_IMP_ERR,
)


ANSIBLE_METADATA = {
    "metadata_version": "1.1",
    "status": ["preview"],
    "supported_by": "cockroach_labs",
}

def main():
    argument_spec = dict(
        database=dict(type='str', required=True),
        schema=dict(type='str', default='public'),
        table=dict(type='str'),
        columns=dict(type='list', elements='str'),
        operation=dict(
            type='str',
            default='create',
            choices=['create', 'delete', 'configure']
        ),
        options=dict(
            type='dict',
            options=dict(
                as_of_time=dict(type='str'),
                throttling=dict(type='float'),
                histogram_buckets=dict(type='int'),
            )
        ),
        auto_stats=dict(
            type='dict',
            options=dict(
                enabled=dict(type='bool'),
                fraction=dict(type='float'),
                min_rows_threshold=dict(type='int'),
                min_stale_rows=dict(type='int'),
            )
        ),
        # Connection parameters
        host=dict(type='str', default='localhost'),
        port=dict(type='int', default=26257),
        user=dict(type='str', default='root'),
        password=dict(type='str', no_log=True),
        ssl_mode=dict(type='str', default='verify-full',
                     choices=['disable', 'allow', 'prefer', 'require', 'verify-ca', 'verify-full']),
        ssl_cert=dict(type='str'),
        ssl_key=dict(type='str'),
        ssl_rootcert=dict(type='str'),
        connect_timeout=dict(type='int', default=30),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_together=[['ssl_cert', 'ssl_key']],
    )

    if not HAS_PSYCOPG2:
        module.fail_json(msg=missing_required_lib('psycopg2'), exception=COCKROACHDB_IMP_ERR)

    database = module.params['database']
    schema = module.params['schema']
    table = module.params['table']
    columns = module.params['columns']
    operation = module.params['operation']
    options = module.params.get('options', {}) or {}
    auto_stats = module.params.get('auto_stats', {}) or {}

    # Initialize helper
    helper = CockroachDBHelper(module)

    try:
        helper.connect()

        # Connect to specific database
        helper.connect_to_database(database)

        # Initialize result
        result = {
            'changed': False,
            'queries': [],
        }

        # Check if schema exists
        if not helper.schema_exists(schema, database):
            module.fail_json(msg=f"Schema '{schema}' does not exist in database '{database}'")

        # Check if table exists if specified
        if table and not helper.table_exists(table, schema, database):
            module.fail_json(msg=f"Table '{schema}.{table}' does not exist in database '{database}'")

        if operation == 'configure':
            # Configure automatic statistics collection
            if auto_stats:
                settings_changed = False
                settings_queries = []
                current_settings = {}

                # Get current automatic stats settings
                stats_settings_query = """
                    SHOW CLUSTER SETTINGS LIKE 'sql.stats.automatic_collection%'
                """
                settings_result = helper.execute_query(stats_settings_query)

                # Make sure we have at least two columns in the result
                for row in settings_result:
                    if len(row) >= 2:  # Ensure we have at least 2 columns in the result
                        setting_name = row[0]
                        current_value = row[1]
                        current_settings[setting_name] = current_value

                # Configure settings
                if 'enabled' in auto_stats:
                    enabled = "true" if auto_stats['enabled'] else "false"
                    current_enabled = current_settings.get('sql.stats.automatic_collection.enabled', None)

                    # Only update if the current value differs
                    if current_enabled is None or str(current_enabled).lower() != enabled.lower():
                        enabled_query = f"""
                            SET CLUSTER SETTING sql.stats.automatic_collection.enabled = {enabled}
                        """
                        settings_queries.append(enabled_query.strip())

                if 'fraction' in auto_stats:
                    fraction = float(auto_stats['fraction'])
                    if not 0.0 <= fraction <= 1.0:
                        module.fail_json(msg="fraction must be between 0.0 and 1.0")

                    current_fraction = current_settings.get('sql.stats.automatic_collection.fraction_stale_rows', None)

                    # Only update if the current value differs
                    if current_fraction is None or abs(float(current_fraction) - fraction) > 0.0001:
                        fraction_query = f"""
                            SET CLUSTER SETTING sql.stats.automatic_collection.fraction_stale_rows = {fraction}
                        """
                        settings_queries.append(fraction_query.strip())

                if 'min_rows_threshold' in auto_stats:
                    min_rows = int(auto_stats['min_rows_threshold'])
                    current_min_rows = current_settings.get('sql.stats.automatic_collection.min_rows_threshold', None)

                    # Only update if the current value differs
                    if current_min_rows is None or int(float(current_min_rows)) != min_rows:
                        min_rows_query = f"""
                            SET CLUSTER SETTING sql.stats.automatic_collection.min_rows_threshold = {min_rows}
                        """
                        settings_queries.append(min_rows_query.strip())

                if 'min_stale_rows' in auto_stats:
                    min_stale = int(auto_stats['min_stale_rows'])
                    current_min_stale = current_settings.get('sql.stats.automatic_collection.min_stale_rows', None)

                    # Only update if the current value differs
                    if current_min_stale is None or int(float(current_min_stale)) != min_stale:
                        min_stale_query = f"""
                            SET CLUSTER SETTING sql.stats.automatic_collection.min_stale_rows = {min_stale}
                        """
                        settings_queries.append(min_stale_query.strip())

                result['queries'].extend(settings_queries)

                # Execute settings queries if not in check mode
                if settings_queries and not module.check_mode:
                    for query in settings_queries:
                        helper.execute_query(query)
                        settings_changed = True

                result['changed'] = settings_changed

                # Get updated settings
                if settings_changed:
                    updated_settings = {}
                    settings_result = helper.execute_query(stats_settings_query)

                    for row in settings_result:
                        setting_name = row[0]
                        updated_value = row[1]
                        updated_settings[setting_name] = updated_value

                    result['settings'] = updated_settings
                else:
                    result['settings'] = current_settings

        elif operation == 'create':
            # Create statistics
            stats_queries = []
            affected_tables = []
            affected_columns = {}
            need_stats_creation = False

            # Get tables to process
            tables_to_process = []
            if table:
                tables_to_process = [(schema, table)]
            else:
                # If no table specified, get all tables in schema
                tables_query = f"""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    AND table_type = 'BASE TABLE'
                """
                tables_result = helper.execute_query(tables_query, [schema])
                tables_to_process = [(schema, row[0]) for row in tables_result]

            # Process each table
            for schema_name, table_name in tables_to_process:
                fully_qualified_table = f"{schema_name}.{table_name}"
                affected_tables.append(fully_qualified_table)

                # Construct options string
                options_parts = []

                if 'as_of_time' in options:
                    options_parts.append(f"AS OF SYSTEM TIME '{options['as_of_time']}'")

                if 'throttling' in options:
                    throttle_val = float(options['throttling'])
                    if not 0.0 <= throttle_val <= 1.0:
                        module.fail_json(msg="throttling must be between 0.0 and 1.0")
                    options_parts.append(f"WITH THROTTLING {throttle_val}")

                if 'histogram_buckets' in options:
                    buckets = int(options['histogram_buckets'])
                    # Only add if specified
                    if buckets > 0:
                        options_parts.append(f"WITH HISTOGRAMS BUCKETS {buckets}")

                options_str = " ".join(options_parts)

                # Check if statistics already exist for this table/columns
                existing_stats_query = f"""
                    SHOW STATISTICS FOR TABLE {schema_name}.{table_name}
                """
                existing_stats_result = helper.execute_query(existing_stats_query)

                # Process existing statistics
                has_matching_stats = False
                column_stats_map = {}

                # Build a map of columns to their statistics
                for stat_row in existing_stats_result:
                    stat_name = stat_row[0] if len(stat_row) > 0 else None
                    stat_columns = stat_row[2] if len(stat_row) > 2 else None

                    if stat_columns:
                        # Convert column string to list
                        try:
                            stat_column_list = [col.strip() for col in stat_columns.split(',')]
                            column_stats_map[tuple(sorted(stat_column_list))] = stat_name
                        except Exception:
                            # If we can't parse column info, assume no match
                            pass

                # Handle statistics for specific columns or all columns
                if columns:
                    # Looking for stats on specific columns
                    affected_columns[fully_qualified_table] = columns
                    cols_str = ", ".join(columns)

                    # Check if stats already exist for the exact column set or a superset
                    sorted_columns_key = tuple(sorted(columns))

                    # Direct match
                    if sorted_columns_key in column_stats_map:
                        has_matching_stats = True

                    # Also check if the stats name already exists
                    stats_name = f"stats_{table_name}_{columns[0]}"
                    if len(columns) > 1:
                        stats_name += f"_plus{len(columns)-1}"

                    for stat_row in existing_stats_result:
                        if stat_row[0] == stats_name:
                            has_matching_stats = True
                            break

                    # Create stats name from table and columns (limited to avoid name length issues)
                    stats_name = f"stats_{table_name}_{columns[0]}"
                    if len(columns) > 1:
                        stats_name += f"_plus{len(columns)-1}"

                    # First check if a statistic with this exact name already exists
                    name_exists = False
                    for stat_row in existing_stats_result:
                        if len(stat_row) > 0 and stat_row[0] == stats_name:
                            name_exists = True
                            break

                    if name_exists:
                        has_matching_stats = True

                    create_stats_query = f"""
                        CREATE STATISTICS {stats_name}
                        ON {cols_str} FROM {schema_name}.{table_name}
                        {options_str}
                    """

                    if not has_matching_stats:
                        stats_queries.append(create_stats_query.strip())
                        need_stats_creation = True
                else:
                    # Check for table-wide statistics
                    # For table-wide stats, we specifically check for the existence of a matching stats name
                    has_stat_with_name = False
                    stats_name = f"stats_{table_name}_all"

                    for stat_row in existing_stats_result:
                        if stat_row[0] == stats_name:
                            has_stat_with_name = True
                            break

                    has_matching_stats = has_stat_with_name

                    # Create statistics for all columns (CockroachDB's default behavior)
                    create_stats_query = f"""
                        CREATE STATISTICS {stats_name}
                        FROM {schema_name}.{table_name}
                        {options_str}
                    """

                    if not has_matching_stats:
                        stats_queries.append(create_stats_query.strip())
                        need_stats_creation = True

            result['queries'].extend(stats_queries)
            result['tables'] = affected_tables
            if affected_columns:
                result['columns'] = affected_columns

            # Set changed flag if we have queries to run
            if stats_queries and need_stats_creation:
                result['changed'] = True

            # Execute statistics creation queries if not in check mode and needed
            if stats_queries and not module.check_mode and need_stats_creation:
                for query in stats_queries:
                    helper.execute_query(query)

        elif operation == 'delete':
            # Delete statistics
            delete_queries = []
            affected_tables = []
            has_stats_to_delete = False

            # Get tables to process
            tables_to_process = []
            if table:
                tables_to_process = [(schema, table)]
                affected_tables.append(f"{schema}.{table}")
            else:
                # If no table specified, get all tables in schema
                tables_query = f"""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    AND table_type = 'BASE TABLE'
                """
                tables_result = helper.execute_query(tables_query, [schema])
                tables_to_process = [(schema, row[0]) for row in tables_result]
                affected_tables = [f"{schema}.{row[0]}" for row in tables_result]

            # For each table, delete all statistics
            for schema_name, table_name in tables_to_process:
                # Check if there are any custom statistics for this table
                # We want to distinguish between the default automatic statistics and user-created ones
                stats_query = f"""
                    SHOW STATISTICS FOR TABLE {schema_name}.{table_name}
                """

                stats_result = helper.execute_query(stats_query)

                # Filter stats to those that are not auto-generated (to make deletion idempotent)
                non_auto_stats = set()  # Use a set to avoid duplicates
                has_user_stats = False

                for row in stats_result:
                    if len(row) > 0:
                        stat_name = row[0]
                        if stat_name and not stat_name.startswith('__auto__'):
                            non_auto_stats.add(stat_name)
                            has_user_stats = True

                # Only generate queries if there are non-auto stats to delete
                if has_user_stats and non_auto_stats:
                    for stat_name in non_auto_stats:
                        # Using the direct DELETE FROM system.table_statistics method
                        delete_query = f"""
                            DELETE FROM system.table_statistics WHERE name = '{stat_name}'
                        """
                        delete_queries.append(delete_query.strip())
                        has_stats_to_delete = True

            result['queries'].extend(delete_queries)
            result['tables'] = affected_tables

            # Set changed flag based on whether there are stats to delete
            result['changed'] = has_stats_to_delete

            # Execute delete queries if not in check mode and there are stats to delete
            if delete_queries and not module.check_mode and has_stats_to_delete:
                for query in delete_queries:
                    helper.execute_query(query)

        module.exit_json(**result)

    except Exception as e:
        module.fail_json(msg=f"Error managing statistics: {to_native(e)}")

    finally:
        if helper.conn:
            helper.conn.close()


if __name__ == '__main__':
    main()
