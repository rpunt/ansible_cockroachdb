#!/usr/bin/python
# -*- coding: utf-8 -*-
# pylint: disable=line-too-long, broad-exception-caught

# Copyright: (c) 2025, Cockroach Labs
# Apache License, Version 2.0 (see LICENSE or http://www.apache.org/licenses/LICENSE-2.0)

"""
Ansible module for managing tables in a CockroachDB database.

This module allows creating, modifying, and removing tables in a CockroachDB database.
It supports defining columns with their data types, constraints, primary keys,
partitioning, and other table options.

The documentation for this module is maintained in the plugins/docs/cockroachdb_table.yml file.
"""

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.cockroachdb import CockroachDBHelper


ANSIBLE_METADATA = {
    "metadata_version": "1.1",
    "status": ["preview"],
    "supported_by": "cockroach_labs",
}


def main():
    module_args = dict(
        name=dict(type='str', required=True),
        database=dict(type='str', required=True),
        state=dict(type='str', default='present', choices=['present', 'absent']),
        columns=dict(
            type='list',
            elements='dict',
            options=dict(
                name=dict(type='str', required=True),
                type=dict(type='str', required=True),
                primary_key=dict(type='bool', default=False),
                nullable=dict(type='bool', default=True),
                default=dict(type='str'),
            ),
        ),
        primary_key=dict(type='list', elements='str'),
        partition_by=dict(
            type='dict',
            options=dict(
                type=dict(type='str', required=True, choices=['HASH', 'RANGE', 'LIST']),
                columns=dict(type='list', elements='str', required=True),
                partitions=dict(
                    type='list',
                    elements='dict',
                    options=dict(
                        name=dict(type='str', required=True),
                        values=dict(type='list', elements='raw', required=True),
                    ),
                ),
            ),
        ),
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
        argument_spec=module_args,
        supports_check_mode=True,
        required_if=[
            ('state', 'present', ['columns'], True),
        ],
    )

    name = module.params['name']
    database = module.params['database']
    state = module.params['state']
    columns = module.params['columns']
    primary_key = module.params['primary_key']
    partition_by = module.params['partition_by']

    # Override database parameter for the initial connection
    orig_database = module.params['database']
    module.params['database'] = 'defaultdb'

    db = CockroachDBHelper(module)

    changed = False
    result = {
        'changed': False,
        'name': name,
        'database': orig_database,
        'state': state
    }

    try:
        # Connect to the CockroachDB server
        db.connect()

        # Check if the database exists
        if not db.database_exists(orig_database):
            module.fail_json(msg="Database %s does not exist" % orig_database)

        # Switch to the target database
        db.execute_query("USE %s" % orig_database)

        # Check if the table exists
        table_exists = bool(db.execute_query(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s AND table_schema = %s",
            [name, 'public']
        ))

        if module.check_mode:
            if state == 'present' and not table_exists:
                result['changed'] = True
            elif state == 'absent' and table_exists:
                result['changed'] = True
            module.exit_json(**result)

        if state == 'present':
            if not table_exists:
                if not columns:
                    module.fail_json(msg="Parameter 'columns' is required when creating a table")

                # Build CREATE TABLE statement
                column_defs = []
                pk_columns = []

                for column in columns:
                    col_def = f"{column['name']} {column['type']}"

                    if column.get('primary_key'):
                        pk_columns.append(column['name'])

                    if not column.get('nullable', True):
                        col_def += " NOT NULL"

                    if column.get('default') is not None:
                        col_def += f" DEFAULT {column['default']}"

                    column_defs.append(col_def)

                # Add primary key constraint if defined via columns or primary_key parameter
                if primary_key:
                    pk_columns = primary_key

                if pk_columns:
                    column_defs.append(f"PRIMARY KEY ({', '.join(pk_columns)})")

                # Start building the CREATE TABLE query
                create_query = f"CREATE TABLE {name} ({', '.join(column_defs)})"

                # Add partitioning if specified
                if partition_by:
                    part_type = partition_by['type']
                    part_columns = partition_by['columns']
                    part_partitions = partition_by.get('partitions', [])

                    # Add PARTITION BY clause
                    if part_type == 'HASH':
                        create_query += f" PARTITION BY HASH ({', '.join(part_columns)})"
                    elif part_type == 'LIST':
                        create_query += f" PARTITION BY LIST ({', '.join(part_columns)})"
                    elif part_type == 'RANGE':
                        create_query += f" PARTITION BY RANGE ({', '.join(part_columns)})"

                    # Add partition definitions
                    if part_partitions:
                        partition_defs = []

                        for partition in part_partitions:
                            part_name = partition['name']
                            part_values = partition['values']

                            if part_type == 'HASH':
                                # For HASH partitioning, values represents the number of buckets
                                if len(part_values) != 1:
                                    module.fail_json(msg=f"HASH partitioning requires exactly one value (bucket count) per partition")
                                partition_defs.append(f"PARTITION {part_name} VALUES IN ({part_values[0]})")

                            elif part_type == 'LIST':
                                # For LIST partitioning, convert values to SQL strings
                                list_values = []
                                for val_list in part_values:
                                    if val_list == ["DEFAULT"]:
                                        list_values.append("DEFAULT")
                                    else:
                                        # Convert each list value to a proper SQL tuple
                                        list_values_str = []
                                        for val in val_list:
                                            if isinstance(val, str):
                                                list_values_str.append(f"'{val}'")
                                            else:
                                                list_values_str.append(str(val))
                                        list_values.append(f"({', '.join(list_values_str)})")

                                partition_defs.append(f"PARTITION {part_name} VALUES IN ({', '.join(list_values)})")

                            elif part_type == 'RANGE':
                                # For RANGE partitioning, values should be pairs: [from_val, to_val]
                                if len(part_values) != 2:
                                    module.fail_json(msg=f"RANGE partitioning requires exactly two values per partition: [from_value, to_value]")

                                # Format the range values
                                from_vals = []
                                to_vals = []

                                for val in part_values[0]:  # from_values
                                    if isinstance(val, str):
                                        from_vals.append(f"'{val}'")
                                    else:
                                        from_vals.append(str(val))

                                for val in part_values[1]:  # to_values
                                    if isinstance(val, str):
                                        to_vals.append(f"'{val}'")
                                    else:
                                        to_vals.append(str(val))

                                from_str = f"({', '.join(from_vals)})"
                                to_str = f"({', '.join(to_vals)})"

                                partition_defs.append(f"PARTITION {part_name} VALUES FROM {from_str} TO {to_str}")

                        # Add all partition definitions to the CREATE TABLE statement
                        if partition_defs:
                            create_query += f" (\n  " + ",\n  ".join(partition_defs) + "\n)"

                # Execute the CREATE TABLE query
                db.execute_query(create_query)
                result['query'] = create_query
                changed = True

        elif state == 'absent':
            if table_exists:
                db.execute_query(f"DROP TABLE {name}")
                changed = True

        result['changed'] = changed

    except Exception as e:
        module.fail_json(msg=str(e))
    finally:
        db.close()

    module.exit_json(**result)


if __name__ == '__main__':
    main()
