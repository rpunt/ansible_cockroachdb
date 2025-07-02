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
from ansible_collections.rpunt.cockroachdb.plugins.module_utils.cockroachdb import (
    CockroachDBHelper
)


ANSIBLE_METADATA = {
    "metadata_version": "1.1",
    "status": ["preview"],
    "supported_by": "cockroach_labs",
}

DOCUMENTATION = r"""
---
module: cockroachdb_table
short_description: Manage CockroachDB tables
description:
  - Create, drop, or manage CockroachDB tables
options:
  name:
    description:
      - Name of the table to create or remove
    required: true
    type: str
  database:
    description:
      - Database name where the table should be created or removed
    required: true
    type: str
  state:
    description:
      - The table state
    default: present
    choices: ["present", "absent"]
    type: str
  columns:
    description:
      - List of column definitions for the table when creating
    type: list
    elements: dict
    suboptions:
      name:
        description:
          - Column name
        required: true
        type: str
      type:
        description:
          - Data type for the column
        required: true
        type: str
      primary_key:
        description:
          - Whether this column is part of the primary key
        type: bool
        default: false
      nullable:
        description:
          - Whether this column can be null
        type: bool
        default: true
      default:
        description:
          - Default value for the column
        type: str
  primary_key:
    description:
      - List of column names that form the primary key
    type: list
    elements: str
  partition_by:
    description:
      - Partition specification for the table
    type: dict
    suboptions:
      type:
        description:
          - Type of partitioning to use (HASH, RANGE, LIST)
        required: true
        choices: ['HASH', 'RANGE', 'LIST']
        type: str
      columns:
        description:
          - Column(s) to use for partitioning
        required: true
        type: list
        elements: str
      partitions:
        description:
          - List of partition definitions
        type: list
        elements: dict
        suboptions:
          name:
            description:
              - Name of the partition
            required: true
            type: str
          values:
            description:
              - Values for the partition (for LIST or RANGE partitioning)
            required: true
            type: list
            elements: raw
  host:
    description:
      - Database host address
    default: localhost
    type: str
  port:
    description:
      - Database port number
    default: 26257
    type: int
  user:
    description:
      - Database username
    default: root
    type: str
  password:
    description:
      - Database user password
    type: str
  ssl_mode:
    description:
      - SSL connection mode
    default: verify-full
    choices: ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]
    type: str
  ssl_cert:
    description:
      - Path to client certificate file
    type: path
  ssl_key:
    description:
      - Path to client private key file
    type: path
  ssl_rootcert:
    description:
      - Path to CA certificate file
    type: path
requirements:
  - psycopg2
author:
  - "Ryan Punt (@rpunt)"
"""

EXAMPLES = r"""
# Create a table with columns
- name: Create users table
  cockroachdb_table:
    name: users
    database: myapp
    state: present
    columns:
      - name: id
        type: UUID
        primary_key: true
        nullable: false
        default: "gen_random_uuid()"
      - name: username
        type: STRING
        nullable: false
      - name: email
        type: STRING
        nullable: false
      - name: created_at
        type: TIMESTAMP
        default: "now()"
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt

# Create a table with hash partitioning
- name: Create orders table with hash partitioning
  cockroachdb_table:
    name: orders
    database: sales
    columns:
      - name: order_id
        type: UUID
        primary_key: true
        default: "gen_random_uuid()"
      - name: customer_id
        type: UUID
        nullable: false
      - name: region
        type: STRING
        nullable: false
      - name: order_date
        type: DATE
        nullable: false
      - name: total
        type: DECIMAL
        nullable: false
    partition_by:
      type: HASH
      columns:
        - region
      partitions:
        - name: europe
          values: [4]
        - name: americas
          values: [4]
        - name: asia
          values: [4]
    host: localhost
    port: 26257
    user: root

# Create a table with list partitioning
- name: Create customers table with list partitioning
  cockroachdb_table:
    name: customers
    database: sales
    columns:
      - name: id
        type: UUID
        primary_key: true
        default: "gen_random_uuid()"
      - name: name
        type: STRING
        nullable: false
      - name: country
        type: STRING
        nullable: false
      - name: city
        type: STRING
        nullable: false
    partition_by:
      type: LIST
      columns:
        - country
      partitions:
        - name: us_customers
          values: [["US"]]
        - name: uk_customers
          values: [["UK"]]
        - name: other_customers
          values: [["DEFAULT"]]
    host: localhost
    port: 26257
    user: root

# Create a table with range partitioning
- name: Create sales table with range partitioning
  cockroachdb_table:
    name: sales
    database: analytics
    columns:
      - name: id
        type: UUID
        primary_key: true
        default: "gen_random_uuid()"
      - name: product_id
        type: UUID
        nullable: false
      - name: sale_date
        type: DATE
        nullable: false
      - name: amount
        type: DECIMAL
        nullable: false
    partition_by:
      type: RANGE
      columns:
        - sale_date
      partitions:
        - name: q1_2025
          values: [["2025-01-01"], ["2025-04-01"]]
        - name: q2_2025
          values: [["2025-04-01"], ["2025-07-01"]]
        - name: q3_2025
          values: [["2025-07-01"], ["2025-10-01"]]
        - name: q4_2025
          values: [["2025-10-01"], ["2026-01-01"]]
    host: localhost
    port: 26257
    user: root

# Drop a table
- name: Drop users table
  cockroachdb_table:
    name: users
    database: myapp
    state: absent
    host: localhost
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt
"""

RETURN = r"""
changed:
  description: Whether the table was created, modified or removed
  returned: always
  type: bool
name:
  description: Table name
  returned: always
  type: str
  sample: "users"
database:
  description: Database name
  returned: always
  type: str
  sample: "myapp"
state:
  description: The new state of the table
  returned: always
  type: str
  sample: "present"
"""

def main():
    """
    Main entry point for the cockroachdb_table module.

    This function handles the creation, modification, and removal of tables in a CockroachDB database.
    It supports defining table structures with columns, data types, constraints, primary keys,
    partitioning schemes, and other table options.
    """
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
    _database = module.params['database']
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
            module.fail_json(msg="Database %s does not exist" % orig_database) # pylint: disable=consider-using-f-string

        # Switch to the target database
        db.execute_query("USE %s" % orig_database) # pylint: disable=consider-using-f-string

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
                                    module.fail_json(msg="HASH partitioning requires exactly one value (bucket count) per partition")
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
                                    module.fail_json(msg="RANGE partitioning requires exactly two values per partition: [from_value, to_value]")

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
                            create_query += " (\n  " + ",\n  ".join(partition_defs) + "\n)"

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
