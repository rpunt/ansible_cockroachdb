#!/usr/bin/python
# -*- coding: utf-8 -*-
# pylint: disable=line-too-long, broad-exception-caught

# Copyright: (c) 2025, Cockroach Labs
# Apache License, Version 2.0 (see LICENSE or http://www.apache.org/licenses/LICENSE-2.0)

"""
Ansible module for managing CockroachDB indexes.

This module enables the creation and management of various types of indexes in CockroachDB,
which are crucial for query performance optimization. It supports creating, modifying,
and dropping different index types with comprehensive configuration options.

Key features:
- Create standard B-tree indexes with customizable options
- Support for unique indexes to enforce data uniqueness constraints
- Configure expression indexes for complex indexing needs
- Specify columns to be stored but not indexed with the STORING clause
- Create partial indexes with WHERE clauses to index subsets of data
- Drop existing indexes when no longer needed

Indexes in CockroachDB are essential for query performance, and this module helps
automate their management as part of your infrastructure-as-code workflow.

For full documentation, see the plugins/docs/cockroachdb_index.yml file
"""

from ansible.module_utils.basic import AnsibleModule, missing_required_lib
from ansible.module_utils._text import to_native
try:
    from ansible_collections.rpunt.cockroachdb.plugins.module_utils.cockroachdb import (
        CockroachDBHelper,
        is_valid_identifier,
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

DOCUMENTATION = r"""
---
module: cockroachdb_index
short_description: Manage CockroachDB indexes
description:
  - Create, drop, or manage CockroachDB indexes
options:
  name:
    description:
      - Name of the index to create or remove
    required: true
    type: str
  database:
    description:
      - Database name where the table and index are located
    required: true
    type: str
  table:
    description:
      - Table name where the index should be created or removed
    required: true
    type: str
  state:
    description:
      - The index state
    default: present
    choices: ["present", "absent"]
    type: str
  columns:
    description:
      - List of columns to include in the index
    type: list
    elements: str
    required: false
  expressions:
    description:
      - List of expressions to include in the index
    type: list
    elements: str
    required: false
  unique:
    description:
      - Whether the index should be a unique index
    type: bool
    default: false
  storing:
    description:
      - Columns to store with the index but not index
    type: list
    elements: str
    required: false
  where:
    description:
      - Optional filtering expression for a partial index
    type: str
    required: false
  if_not_exists:
    description:
      - Add IF NOT EXISTS clause to CREATE INDEX
    type: bool
    default: false
  concurrently:
    description:
      - Use CONCURRENTLY option when creating or dropping the index
    type: bool
    default: false
  host:
    description:
      - The CockroachDB database host address
    default: localhost
    type: str
  port:
    description:
      - The CockroachDB database port
    default: 26257
    type: int
  user:
    description:
      - The username to connect to the database
    default: root
    type: str
  password:
    description:
      - The password to connect to the database
    type: str
    required: false
  ssl_mode:
    description:
      - SSL mode for database connection
    type: str
    choices: ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]
    default: verify-full
  ssl_cert:
    description:
      - Path to client certificate file
    type: str
    required: false
  ssl_key:
    description:
      - Path to client key file
    type: str
    required: false
  ssl_rootcert:
    description:
      - Path to root CA certificate file
    type: str
    required: false
  connect_timeout:
    description:
      - Database connection timeout in seconds
    type: int
    default: 30
requirements:
  - psycopg2
author:
  - "Ryan Punt (@rpunt)"
"""

EXAMPLES = r"""
# Create a basic index
- name: Create index on users table
  cockroachdb_index:
    name: idx_users_email
    database: production
    table: users
    columns:
      - email
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt

# Create a unique index
- name: Create unique index on users table
  cockroachdb_index:
    name: idx_users_username
    database: production
    table: users
    columns:
      - username
    unique: true

# Create a composite index
- name: Create composite index on orders table
  cockroachdb_index:
    name: idx_orders_customer_date
    database: sales
    table: orders
    columns:
      - customer_id
      - order_date

# Create a partial index
- name: Create partial index on orders table for high-value orders
  cockroachdb_index:
    name: idx_high_value_orders
    database: sales
    table: orders
    columns:
      - customer_id
      - order_date
    where: "total_amount > 1000"

# Create an expression index
- name: Create expression index for lowercase email
  cockroachdb_index:
    name: idx_users_lower_email
    database: production
    table: users
    expressions:
      - "lower(email)"

# Drop an index
- name: Remove index
  cockroachdb_index:
    name: idx_users_email
    database: production
    table: users
    state: absent
"""

RETURN = r"""
index:
  description: Index name that was created or dropped
  returned: always
  type: str
  sample: idx_users_email
table:
  description: Table name containing the index
  returned: always
  type: str
  sample: users
database:
  description: Database name containing the table and index
  returned: always
  type: str
  sample: production
state:
  description: State of the index after task execution
  returned: always
  type: str
  sample: present
queries:
  description: List of executed SQL queries
  returned: on success
  type: list
  sample: ["CREATE INDEX idx_users_email ON users (email)"]
"""


def main():
    """
    Main entry point for the CockroachDB index management module.

    This function handles the creation and deletion of indexes in CockroachDB tables.
    It processes module parameters, validates inputs, connects to the cluster,
    and performs the requested index operations in an idempotent manner.

    Features:
    - Create standard or unique indexes on database tables
    - Support for column-based indexes or expression-based indexes
    - Support for partial indexes with WHERE clauses
    - Support for STORING additional columns in the index
    - Drop existing indexes when no longer needed
    - Concurrent index creation and deletion
    - Idempotent operations with IF NOT EXISTS option

    The function handles security by validating identifiers to prevent SQL injection
    and checks for the existence of tables before attempting to create indexes.

    Returns:
        dict: Result object containing operation status, index details, and
              the SQL queries executed during the operation
    """
    argument_spec = dict(
        name=dict(type='str', required=True),
        database=dict(type='str', required=True),
        table=dict(type='str', required=True),
        state=dict(type='str', default='present', choices=['present', 'absent']),
        columns=dict(type='list', elements='str', required=False),
        expressions=dict(type='list', elements='str', required=False),
        unique=dict(type='bool', default=False),
        storing=dict(type='list', elements='str', required=False),
        where=dict(type='str', required=False),
        if_not_exists=dict(type='bool', default=False),
        concurrently=dict(type='bool', default=False),
        host=dict(type='str', default='localhost'),
        port=dict(type='int', default=26257),
        user=dict(type='str', default='root'),
        password=dict(type='str', no_log=True),
        ssl_mode=dict(type='str', default='verify-full', choices=['disable', 'allow', 'prefer', 'require', 'verify-ca', 'verify-full']),
        ssl_cert=dict(type='str'),
        ssl_key=dict(type='str'),
        ssl_rootcert=dict(type='str'),
        connect_timeout=dict(type='int', default=30),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        mutually_exclusive=[['columns', 'expressions']],
        required_one_of=[['columns', 'expressions']],
    )

    if not HAS_PSYCOPG2:
        module.fail_json(msg=missing_required_lib('psycopg2'), exception=COCKROACHDB_IMP_ERR)

    name = module.params['name']
    database = module.params['database']
    table = module.params['table']
    state = module.params['state']
    columns = module.params['columns']
    expressions = module.params['expressions']
    unique = module.params['unique']
    storing = module.params['storing']
    where_clause = module.params['where']
    if_not_exists = module.params['if_not_exists']
    concurrently = module.params['concurrently']

    # Validate identifiers to prevent SQL injection
    for identifier in [name, database, table]:
        if not is_valid_identifier(identifier):
            module.fail_json(msg=f"Invalid identifier: {identifier}")

    if columns:
        for column in columns:
            if not is_valid_identifier(column):
                module.fail_json(msg=f"Invalid column name: {column}")

    if storing:
        for column in storing:
            if not is_valid_identifier(column):
                module.fail_json(msg=f"Invalid storing column name: {column}")

    result = dict(
        changed=False,
        index=name,
        table=table,
        database=database,
        state=state,
        queries=[]
    )

    db_helper = CockroachDBHelper(module)

    try:
        db_helper.connect()
        db_helper.connect_to_database(database)

        # Check if table exists
        if not db_helper.table_exists(table):
            module.fail_json(msg=f"Table '{table}' does not exist in database '{database}'")

        # Check if index exists
        index_exists = db_helper.index_exists(name, table)

        if state == 'present' and not index_exists:
            if not module.check_mode:
                # Create index
                query_parts = []

                if concurrently:
                    query_parts.append("CONCURRENTLY")

                if unique:
                    query = "CREATE UNIQUE INDEX"
                else:
                    query = "CREATE INDEX"

                if if_not_exists:
                    query += " IF NOT EXISTS"

                query += f" {name} ON {table}"

                # Handle columns or expressions
                if columns:
                    column_list = ", ".join(columns)
                    query += f" ({column_list})"
                elif expressions:
                    expr_list = ", ".join(expressions)
                    query += f" ({expr_list})"

                # Add STORING clause if specified
                if storing:
                    storing_list = ", ".join(storing)
                    query += f" STORING ({storing_list})"

                # Add WHERE clause if specified
                if where_clause:
                    query += f" WHERE {where_clause}"

                db_helper.execute_query(query)
                result['queries'].append(query)
                result['changed'] = True
                result['msg'] = f"Index {name} created on table {table}"

        elif state == 'absent' and index_exists:
            if not module.check_mode:
                # Drop index
                query = "DROP INDEX"

                if concurrently:
                    query += " CONCURRENTLY"

                query += f" {table}@{name}"

                db_helper.execute_query(query)
                result['queries'].append(query)
                result['changed'] = True
                result['msg'] = f"Index {name} dropped from table {table}"

        if index_exists:
            # Get index details
            try:
                # Try with simplified schema to avoid compatibility issues
                # pylint: disable=consider-using-f-string
                query = """
                SELECT index_name
                FROM [SHOW INDEXES FROM {}]
                WHERE index_name = %s
                """.format(
                    table
                )

                rows = db_helper.execute_query(query, (name,), fetch=True)
                if rows:
                    result['index_details'] = {
                        'name': rows[0][0]
                    }
            except Exception:
                # If we can't get details, that's okay - we know it exists
                pass

    except Exception as e:
        module.fail_json(msg=f"Database error: {to_native(e)}")
    finally:
        db_helper.close()

    module.exit_json(**result)


if __name__ == '__main__':
    main()
