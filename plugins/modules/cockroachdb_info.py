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
module: cockroachdb_info
short_description: Get information about a CockroachDB cluster
description:
  - Retrieve information about a CockroachDB cluster, databases, and tables
options:
  gather_subset:
    description:
      - Specify which subset of information to gather
    default: ['cluster', 'databases', 'sizes']
    type: list
    elements: str
    choices: ['cluster', 'databases', 'tables', 'roles', 'sizes', 'settings', 'indexes']
  database:
    description:
      - Restrict information gathering to a specific database
    type: str
  table:
    description:
      - Restrict information gathering to a specific table (requires database to be specified)
    type: str
  type:
    description:
      - Shorthand to gather specific type of information (alternative to gather_subset)
    type: str
    choices: ['cluster', 'databases', 'tables', 'roles', 'sizes', 'settings', 'indexes']
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
# Get all available information about the CockroachDB cluster
- name: Gather all CockroachDB information
  cockroachdb_info:
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt
  register: crdb_info

# Get cluster settings only
- name: Gather CockroachDB cluster settings
  cockroachdb_info:
    gather_subset: ['settings']
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt
  register: crdb_settings

# Get information about a specific database
- name: Gather information about production database
  cockroachdb_info:
    gather_subset: ['tables', 'sizes']
    database: production
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt
  register: production_info
'''

RETURN = '''
cluster:
  description: Information about the CockroachDB cluster
  returned: when gather_subset includes cluster
  type: dict
  contains:
    version:
      description: CockroachDB version
      returned: always
      type: str
      sample: "22.1.6"
    enterprise:
      description: Whether this is an enterprise edition
      returned: always
      type: bool
      sample: false
    node_count:
      description: Number of nodes in the cluster
      returned: always
      type: int
      sample: 3
    id:
      description: Cluster ID
      returned: always
      type: str
      sample: "8a2d7ae6-63d5-4788-aecb-feaed98a331d"
databases:
  description: List of databases in the cluster
  returned: when gather_subset includes databases
  type: list
  elements: str
  sample: ["defaultdb", "postgres", "system", "production"]  tables:
    description: List of tables by database
    returned: when gather_subset includes tables
    type: dict
    contains:
      database_name:
        description: Tables in this database
        type: list
        elements: str
        sample: ["users", "products", "orders"]
  partitioned_tables:
    description: Partitioning information for tables
    returned: when gather_subset includes tables
    type: dict
    contains:
      database_name:
        description: Database containing partitioned tables
        type: dict
        contains:
          table_name:
            description: Partitioning details for the table
            type: dict
            contains:
              partition_type:
                description: Type of partitioning (HASH, LIST, RANGE)
                type: str
                sample: "LIST"
              partition_columns:
                description: Columns used for partitioning
                type: list
                elements: str
                sample: ["region"]
              partitions:
                description: List of partitions
                type: list
                elements: dict
                contains:
                  name:
                    description: Partition name
                    type: str
                    sample: "north_america"
                  values:
                    description: Partition values
                    type: raw
                    sample: ["US", "CA", "MX"]
indexes:
  description: List of indexes by table in each database
  returned: when gather_subset includes indexes or type=indexes
  type: dict
  contains:
    database_name:
      description: Database containing tables with indexes
      type: dict
      contains:
        table_name:
          description: Table containing the indexes
          type: list
          elements: dict
          contains:
            name:
              description: Index name
              type: str
              sample: "idx_users_email"
            is_unique:
              description: Whether the index is unique
              type: bool
              sample: false
            columns:
              description: Columns included in the index
              type: list
              sample: ["email"]
            storing:
              description: Columns stored but not indexed
              type: list
              sample: ["last_login_date"]
            index_type:
              description: Type of index
              type: str
              sample: "BTREE"
roles:
  description: List of roles in the cluster
  returned: when gather_subset includes roles
  type: list
  elements: dict
  contains:
    name:
      description: Role name
      type: str
      sample: "admin"
    superuser:
      description: Whether the role is a superuser
      type: bool
      sample: true
    inherit:
      description: Whether the role inherits privileges
      type: bool
      sample: true
    can_login:
      description: Whether the role can login
      type: bool
      sample: true
    can_create_db:
      description: Whether the role can create databases
      type: bool
      sample: false
sizes:
  description: Size information for databases and tables
  returned: when gather_subset includes sizes
  type: dict
  contains:
    databases:
      description: Size of each database in bytes
      type: dict
      sample: {"production": 1073741824, "defaultdb": 32768}
    tables:
      description: Size of each table in bytes by database
      type: dict
      contains:
        database_name:
          description: Tables in this database with their sizes
          type: dict
          sample: {"users": 524288, "products": 262144, "orders": 786432}
settings:
  description: Cluster settings
  returned: when gather_subset includes settings
  type: dict
  sample: {
    "cluster.organization": "Acme Corp",
    "sql.defaults.distsql": "1",
    "server.time_until_store_dead": "5m0s"
  }
'''

import traceback
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.cockroachdb import CockroachDBHelper


def main():
    module_args = dict(
        gather_subset=dict(
            type='list',
            elements='str',
            default=['cluster', 'databases', 'sizes'],
            choices=['cluster', 'databases', 'tables', 'roles', 'sizes', 'settings', 'indexes']
        ),
        type=dict(
            type='str',
            choices=['cluster', 'databases', 'tables', 'roles', 'sizes', 'settings', 'indexes']
        ),
        database=dict(type='str', default='defaultdb'),
        table=dict(type='str'),
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
    )

    gather_subset = module.params['gather_subset']
    # If 'type' parameter is provided, add it to the gather_subset
    if module.params.get('type'):
        gather_subset = list(set(gather_subset + [module.params.get('type')]))
    target_database = module.params.get('database')

    result = {}

    db = CockroachDBHelper(module)

    try:
        # Connect to the CockroachDB server
        db.connect()

        # Gather cluster information
        if 'cluster' in gather_subset:
            cluster_info = {}

            # Get version
            cluster_info['version'] = db.get_version()

            # Check if enterprise
            cluster_info['enterprise'] = db.is_enterprise()

            # Get cluster ID - using system_tables=True to handle case where crdb_internal.cluster_info may not exist
            cluster_id_result = db.execute_query(
                "SELECT cluster_id FROM crdb_internal.cluster_info LIMIT 1",
                fail_on_error=False,
                system_tables=True
            )
            if cluster_id_result and cluster_id_result[0][0]:
                cluster_info['id'] = cluster_id_result[0][0]
            else:
                cluster_info['id'] = 'unknown'  # Default value if table doesn't exist or query fails

            # Get node count - using system_tables=True to handle case where crdb_internal.gossip_nodes may not exist
            node_count_result = db.execute_query(
                "SELECT count(*) FROM crdb_internal.gossip_nodes",
                fail_on_error=False,
                system_tables=True
            )
            if node_count_result and node_count_result[0][0]:
                cluster_info['node_count'] = node_count_result[0][0]
            else:
                cluster_info['node_count'] = 1  # Default to single node if table doesn't exist or query fails

            result['cluster'] = cluster_info

        # Gather database information
        if 'databases' in gather_subset:
            databases_result = db.execute_query(
                "SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY datname"
            )
            databases = [db[0] for db in databases_result] if databases_result else []

            # Filter by target database if provided
            if target_database and target_database in databases:
                databases = [target_database]

            result['databases'] = databases

        # Gather table information
        if 'tables' in gather_subset:
            tables_by_db = {}
            partitioned_tables_by_db = {}

            databases_to_check = []
            if target_database:
                if db.database_exists(target_database):
                    databases_to_check = [target_database]
                else:
                    module.fail_json(msg=f"Database {target_database} does not exist")
            elif 'databases' in result:
                databases_to_check = result['databases']
            else:
                databases_result = db.execute_query(
                    "SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY datname"
                )
                databases_to_check = [db[0] for db in databases_result] if databases_result else []

            target_table = module.params.get('table')

            for database in databases_to_check:
                # Skip system databases when listing tables
                if database in ['postgres', 'system']:
                    continue

                # Connect to the database
                db.execute_query(f"USE {database}")

                # Get tables
                if target_table:
                    if db.table_exists(target_table):
                        tables_result = [[target_table]]
                    else:
                        module.fail_json(msg=f"Table {target_table} does not exist in database {database}")
                else:
                    tables_result = db.execute_query(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
                    )

                if tables_result:
                    tables = [table[0] for table in tables_result]
                    tables_by_db[database] = tables

                    # Check for partitioning information
                    partitioned_tables = {}
                    for table_name in tables:
                        partition_info = db.get_partition_info(table_name)
                        if partition_info:
                            partitioned_tables[table_name] = partition_info

                    if partitioned_tables:
                        partitioned_tables_by_db[database] = partitioned_tables
                else:
                    tables_by_db[database] = []

            result['tables'] = tables_by_db

            # Include partitioned tables information if any
            if partitioned_tables_by_db:
                result['partitioned_tables'] = partitioned_tables_by_db

        # Gather role information
        if 'roles' in gather_subset:
            roles_result = db.execute_query("""
                SELECT
                    rolname,
                    rolsuper,
                    rolinherit,
                    rolcanlogin,
                    rolcreatedb
                FROM
                    pg_roles
                ORDER BY
                    rolname
            """)

            roles = []
            if roles_result:
                for role in roles_result:
                    roles.append({
                        'name': role[0],
                        'superuser': role[1],
                        'inherit': role[2],
                        'can_login': role[3],
                        'can_create_db': role[4]
                    })

            result['roles'] = roles

        # Gather size information
        if 'sizes' in gather_subset:
            sizes = {
                'databases': {},
                'tables': {}
            }

            databases_to_check = []
            if target_database:
                if db.database_exists(target_database):
                    databases_to_check = [target_database]
                else:
                    module.fail_json(msg=f"Database {target_database} does not exist")
            elif 'databases' in result:
                databases_to_check = result['databases']
            else:
                databases_result = db.execute_query(
                    "SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY datname"
                )
                databases_to_check = [db[0] for db in databases_result] if databases_result else []

            for database in databases_to_check:
                # Skip system databases when gathering sizes
                if database in ['postgres', 'system']:
                    continue

                # Get database size
                sizes['databases'][database] = db.get_database_size(database)

                # Get table sizes
                db.execute_query(f"USE {database}")
                tables_result = db.execute_query("""
                    SELECT
                        table_name
                    FROM
                        information_schema.tables
                    WHERE
                        table_schema = 'public'
                    ORDER BY
                        table_name
                """)

                if tables_result:
                    sizes['tables'][database] = {}
                    for table in tables_result:
                        table_name = table[0]
                        sizes['tables'][database][table_name] = db.get_table_size(table_name)

            result['sizes'] = sizes

        # Gather cluster settings
        if 'settings' in gather_subset:
            settings_result = db.execute_query("SHOW ALL CLUSTER SETTINGS")

            settings = {}
            if settings_result:
                for setting in settings_result:
                    if setting[0] and setting[1] is not None:
                        settings[setting[0]] = setting[1]

            result['settings'] = settings

        # Gather index information
        if 'indexes' in gather_subset or module.params.get('type') == 'indexes':
            indexes_by_db = {}

            databases_to_check = []
            if target_database:
                if db.database_exists(target_database):
                    databases_to_check = [target_database]
                else:
                    module.fail_json(msg=f"Database {target_database} does not exist")
            elif 'databases' in result:
                databases_to_check = result['databases']
            else:
                databases_result = db.execute_query(
                    "SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY datname"
                )
                databases_to_check = [db[0] for db in databases_result] if databases_result else []

            target_table = module.params.get('table')

            for database in databases_to_check:
                # Skip system databases when gathering indexes
                if database in ['postgres', 'system']:
                    continue

                # Connect to the database
                db.execute_query(f"USE {database}")
                indexes_by_db[database] = {}

                # Get tables in this database
                tables_to_check = []
                if target_table:
                    if db.table_exists(target_table):
                        tables_to_check = [target_table]
                    else:
                        module.fail_json(msg=f"Table {target_table} does not exist in database {database}")
                else:
                    tables_result = db.execute_query(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
                    )
                    if tables_result:
                        tables_to_check = [table[0] for table in tables_result]

                # Get indexes for each table
                for table in tables_to_check:
                    indexes_result = db.execute_query(f"""
                        SELECT
                            index_name,
                            is_unique,
                            column_names,
                            storing_names,
                            index_type
                        FROM
                            [SHOW INDEXES FROM {table}]
                        ORDER BY
                            index_name
                    """)

                    if indexes_result:
                        indexes_by_db[database][table] = []
                        for idx in indexes_result:
                            # Convert column names from string representation to list
                            column_names = idx[2]
                            if column_names.startswith('{') and column_names.endswith('}'):
                                column_names = column_names[1:-1].split(',')
                            else:
                                column_names = [column_names]

                            # Convert storing names from string representation to list
                            storing_names = idx[3]
                            if storing_names:
                                if storing_names.startswith('{') and storing_names.endswith('}'):
                                    storing_names = storing_names[1:-1].split(',')
                                else:
                                    storing_names = [storing_names]
                            else:
                                storing_names = []

                            indexes_by_db[database][table].append({
                                'name': idx[0],
                                'is_unique': idx[1],
                                'columns': column_names,
                                'storing': storing_names,
                                'index_type': idx[4]
                            })

            result['indexes'] = indexes_by_db

    except Exception as e:
        module.fail_json(msg=str(e), exception=traceback.format_exc())
    finally:
        db.close()

    module.exit_json(**result)


if __name__ == '__main__':
    main()
