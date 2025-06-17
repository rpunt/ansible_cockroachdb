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

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_native

ANSIBLE_METADATA = {
    "metadata_version": "1.1",
    "status": ["preview"],
    "supported_by": "cockroach_labs",
}

try:
    from ansible_collections.cockroach_labs.cockroachdb.plugins.module_utils.cockroachdb import CockroachDBHelper, is_valid_identifier, COCKROACHDB_IMP_ERR, HAS_PSYCOPG2
except ImportError:
    # This is handled in the module
    pass


def main():
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
                    query = f"CREATE UNIQUE INDEX"
                else:
                    query = f"CREATE INDEX"

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
                query = f"DROP INDEX"

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
                query = """
                SELECT index_name
                FROM [SHOW INDEXES FROM {}]
                WHERE index_name = %s
                """.format(table)

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
