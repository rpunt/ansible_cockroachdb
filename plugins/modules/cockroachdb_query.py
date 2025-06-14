#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2025, Cockroach Labs
# Apache License, Version 2.0 (see LICENSE or http://www.apache.org/licenses/LICENSE-2.0)

ANSIBLE_METADATA = {
    "metadata_version": "1.1",
    "status": ["preview"],
    "supported_by": "cockroach_labs",
}

DOCUMENTATION = '''
---
module: cockroachdb_query
short_description: Execute SQL queries against a CockroachDB database
description:
  - Execute arbitrary SQL queries against a CockroachDB database
  - For simple statements that don't return data, use I(query). For complex queries that return data, use I(query_file) or I(script).
options:
  query:
    description:
      - SQL query or statement to execute
    type: str
  query_file:
    description:
      - Path to a file containing SQL statements
      - Statements must be separated by semicolons
    type: path
  script:
    description:
      - Multi-line SQL script to execute
      - Statements must be separated by semicolons
    type: str
  database:
    description:
      - Database to connect to
    type: str
    required: true
  positional_args:
    description:
      - List of positional arguments for the query
      - These arguments replace $1, $2, etc. in the query
    type: list
    elements: raw
  named_args:
    description:
      - Dictionary of named arguments for the query
      - These arguments replace %(name)s style parameters in the query
    type: dict
  autocommit:
    description:
      - Whether to use autocommit mode
      - When False, the module will execute the query in an explicit transaction
    type: bool
    default: true
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
    choices: [ "disable", "allow", "prefer", "require", "verify-ca", "verify-full" ]
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
  - "Your Name (@yourgithub)"
'''

EXAMPLES = '''
# Execute a simple query
- name: Create an index
  cockroachdb_query:
    query: "CREATE INDEX idx_users_email ON users(email)"
    database: myapp
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt

# Execute a query with parameters
- name: Insert a user
  cockroachdb_query:
    query: "INSERT INTO users(username, email) VALUES($1, $2)"
    positional_args:
      - "johndoe"
      - "john.doe@example.com"
    database: myapp
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt

# Execute a query with named parameters
- name: Insert a user with named parameters
  cockroachdb_query:
    query: "INSERT INTO users(username, email) VALUES(%(username)s, %(email)s)"
    named_args:
      username: "johndoe"
      email: "john.doe@example.com"
    database: myapp
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt

# Execute a query and register the result
- name: Fetch active users
  cockroachdb_query:
    query: "SELECT id, username, email FROM users WHERE active = true"
    database: myapp
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt
  register: active_users

# Execute a multi-line script
- name: Execute a script
  cockroachdb_query:
    script: |
      CREATE TABLE IF NOT EXISTS products (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          name STRING NOT NULL,
          price DECIMAL NOT NULL,
          created_at TIMESTAMP DEFAULT now()
      );

      CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);

      INSERT INTO products(name, price) VALUES('Widget', 19.99);
    database: myapp
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt

# Execute a query from a file
- name: Execute a query from a file
  cockroachdb_query:
    query_file: /path/to/init_schema.sql
    database: myapp
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt
'''

RETURN = '''
changed:
  description: Whether the query caused a change
  returned: always
  type: bool
  sample: true
query:
  description: The executed query or a description of it
  returned: always
  type: str
  sample: "CREATE INDEX idx_users_email ON users(email)"
rowcount:
  description: Number of rows affected by the query
  returned: always
  type: int
  sample: 5
query_result:
  description: List of dictionaries representing the query results
  returned: when the query returns rows
  type: list
  elements: dict
  sample: [{"id": "d0d5e6fc-5044-4a72-94b0-64c8380a0a58", "username": "johndoe", "email": "john.doe@example.com"}]
statusmessage:
  description: Status message returned by the database driver
  returned: always
  type: str
  sample: "CREATE INDEX"
'''

import os
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.cockroachdb import CockroachDBHelper


def main():
    module_args = dict(
        query=dict(type='str'),
        query_file=dict(type='path'),
        script=dict(type='str'),
        database=dict(type='str', required=True),
        positional_args=dict(type='list', elements='raw'),
        named_args=dict(type='dict'),
        autocommit=dict(type='bool', default=True),
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
        mutually_exclusive=[
            ['query', 'query_file', 'script'],
            ['positional_args', 'named_args']
        ],
        required_one_of=[
            ['query', 'query_file', 'script']
        ],
    )

    query = module.params['query']
    query_file = module.params['query_file']
    script = module.params['script']
    database = module.params['database']
    positional_args = module.params['positional_args']
    named_args = module.params['named_args']
    autocommit = module.params['autocommit']

    # Set database for connection
    module.params['database'] = database

    db = CockroachDBHelper(module)

    result = {
        'changed': False,
        'query': query or script or f"File: {query_file}" if query_file else "No query provided",
        'rowcount': 0,
        'statusmessage': ''
    }

    try:
        # Connect to the database
        conn = db.connect()

        # Get the SQL to execute
        if query_file:
            if not os.path.exists(query_file):
                module.fail_json(msg=f"Query file {query_file} not found")

            with open(query_file, 'r') as f:
                sql = f.read()
                result['query'] = f"File: {query_file}"
        elif script:
            sql = script
            # Truncate the script for result display
            if len(script) > 100:
                result['query'] = script[:100] + "..."
            else:
                result['query'] = script
        else:
            sql = query

        # Don't execute in check mode
        if module.check_mode:
            # Simple check if this is a modifying query
            modifying_keywords = ['INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'GRANT', 'REVOKE']
            for keyword in modifying_keywords:
                if keyword in sql.upper():
                    result['changed'] = True
                    break
            module.exit_json(**result)

        # Set the transaction mode
        if not autocommit:
            conn.autocommit = False
            cursor = conn.cursor()
        else:
            conn.autocommit = True
            cursor = conn.cursor()

        # Execute the query
        query_results = []

        # Split the script into statements if needed
        if script or query_file:
            statements = [s.strip() for s in sql.split(';') if s.strip()]

            for statement in statements:
                if not statement.strip():
                    continue

                try:
                    if positional_args:
                        cursor.execute(statement, positional_args)
                    elif named_args:
                        cursor.execute(statement, named_args)
                    else:
                        cursor.execute(statement)

                    # Try to fetch results
                    try:
                        cols = [desc[0] for desc in cursor.description] if cursor.description else []
                        rows = cursor.fetchall() if cols else []

                        for row in rows:
                            query_results.append(dict(zip(cols, row)))

                    except Exception:
                        # No results or not a query that returns results
                        pass

                    # Add to the total rowcount
                    if cursor.rowcount > 0:
                        result['rowcount'] += cursor.rowcount
                        # If any statement modifies data, we consider it a change
                        if cursor.rowcount > 0:
                            result['changed'] = True
                except Exception as e:
                    if not autocommit:
                        conn.rollback()
                    module.fail_json(msg=f"Error executing SQL statement: {statement}. Error: {str(e)}")
        else:
            # Single query
            try:
                if positional_args:
                    cursor.execute(query, positional_args)
                elif named_args:
                    cursor.execute(query, named_args)
                else:
                    cursor.execute(query)

                # Try to fetch results
                try:
                    if cursor.description:
                        cols = [desc[0] for desc in cursor.description]
                        rows = cursor.fetchall()

                        for row in rows:
                            query_results.append(dict(zip(cols, row)))
                except Exception:
                    # No results or not a query that returns results
                    pass

                # Update the result
                result['rowcount'] = cursor.rowcount
                result['statusmessage'] = cursor.statusmessage

                # If rowcount is positive, consider it a change
                if cursor.rowcount > 0:
                    result['changed'] = True

                # For DDL statements, mark as changed even if rowcount is 0
                if cursor.statusmessage and any(keyword in cursor.statusmessage.upper()
                                            for keyword in ['CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'GRANT', 'REVOKE']):
                    result['changed'] = True
            except Exception as e:
                if not autocommit:
                    conn.rollback()
                module.fail_json(msg=f"Error executing query: {str(e)}")

        # Commit the transaction if not in autocommit mode
        if not autocommit:
            conn.commit()

        # Add the query results if there are any
        if query_results:
            result['query_result'] = query_results

    except Exception as e:
        module.fail_json(msg=str(e))
    finally:
        db.close()

    module.exit_json(**result)


if __name__ == '__main__':
    main()
