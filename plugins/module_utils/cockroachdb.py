#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2025, Cockroach Labs
# Apache License, Version 2.0 (see LICENSE or http://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import traceback
import re
import time
from ansible.module_utils.basic import missing_required_lib

COCKROACHDB_IMP_ERR = None
try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    HAS_PSYCOPG2 = True
except ImportError:
    COCKROACHDB_IMP_ERR = traceback.format_exc()
    HAS_PSYCOPG2 = False

# Use to validate identifiers to avoid SQL injection
def is_valid_identifier(identifier):
    """Check if the identifier is valid to avoid SQL injection"""
    return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier))

class CockroachDBHelper(object):
    """
    Helper class for managing CockroachDB connections and operations
    """

    def __init__(self, module):
        self.module = module
        self.host = module.params.get('host', 'localhost')
        self.port = module.params.get('port', 26257)
        self.user = module.params.get('user', 'root')
        self.password = module.params.get('password', '')
        self.database = module.params.get('database', 'defaultdb')
        self.ssl_mode = module.params.get('ssl_mode', 'verify-full')
        self.ssl_cert = module.params.get('ssl_cert')
        self.ssl_key = module.params.get('ssl_key')
        self.ssl_rootcert = module.params.get('ssl_rootcert')
        self.conn_timeout = module.params.get('connect_timeout', 30)
        self.conn = None

    def connect(self):
        """
        Connect to CockroachDB instance
        """
        if not HAS_PSYCOPG2:
            self.module.fail_json(msg=missing_required_lib("psycopg2"), exception=COCKROACHDB_IMP_ERR)

        try:
            conn_params = dict(
                host=self.host,
                port=self.port,
                user=self.user,
                dbname=self.database,
                connect_timeout=self.conn_timeout,
                application_name='ansible_cockroachdb',  # Identify the connection in logs
            )

            if self.password:
                conn_params['password'] = self.password

            if self.ssl_mode:
                conn_params['sslmode'] = self.ssl_mode

            if self.ssl_cert:
                conn_params['sslcert'] = self.ssl_cert

            if self.ssl_key:
                conn_params['sslkey'] = self.ssl_key

            if self.ssl_rootcert:
                conn_params['sslrootcert'] = self.ssl_rootcert

            # Attempt to connect with retries for transient network issues
            retries = 3
            delay = 2
            last_error = None

            for attempt in range(retries):
                try:
                    self.conn = psycopg2.connect(**conn_params)
                    self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                    # Test the connection with a simple query
                    cursor = self.conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
                    return self.conn
                except psycopg2.OperationalError as e:
                    last_error = e
                    if attempt < retries - 1:
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff
                    continue
                except Exception as e:
                    # Non-transient error, fail immediately
                    raise e

            self.module.fail_json(msg="Unable to connect to CockroachDB after multiple attempts: %s" % str(last_error))

        except Exception as e:
            self.module.fail_json(msg="Unable to connect to CockroachDB: %s" % str(e))

    def execute_query(self, query, params=None, fail_on_error=True, system_tables=False, fetch=True):
        """
        Execute a SQL query and return the results

        Args:
            query: The SQL query to execute
            params: The parameters for the query (optional)
            fail_on_error: Whether to fail with an error or return None (default: True)
            system_tables: Whether this query is accessing system tables (default: False)
                           If True, will not fail on "table does not exist" errors
            fetch: Whether to fetch and return results (default: True)
        """
        try:
            if not self.conn:
                self.connect()

            cursor = self.conn.cursor()
            try:
                cursor.execute(query, params or ())
                if fetch:
                    try:
                        result = cursor.fetchall()
                    except psycopg2.ProgrammingError:
                        result = []
                    return result
                return True
            finally:
                cursor.close()
        except psycopg2.Error as e:
            # Handle common CockroachDB errors with better messages
            error_message = str(e)

            # Special handling for system table queries - allows for version differences
            if system_tables and ("does not exist" in error_message and
                                  ("relation" in error_message or "table" in error_message)):
                if not fail_on_error:
                    return None

            if not fail_on_error:
                return None

            if "does not exist" in error_message:
                if "database" in error_message:
                    self.module.fail_json(msg=f"Database does not exist: {error_message}")
                elif "relation" in error_message or "table" in error_message:
                    self.module.fail_json(msg=f"Table does not exist: {error_message}")
                elif "role" in error_message:
                    self.module.fail_json(msg=f"Role does not exist: {error_message}")
                else:
                    self.module.fail_json(msg=f"Object does not exist: {error_message}")
            elif "unknown setting" in error_message:
                self.module.fail_json(msg=f"Unknown setting: {error_message}")
            elif "already exists" in error_message:
                self.module.fail_json(msg=f"Object already exists: {error_message}")
            elif "permission denied" in error_message:
                self.module.fail_json(msg=f"Permission denied: {error_message}")
            elif "syntax error" in error_message:
                self.module.fail_json(msg=f"SQL syntax error: {error_message}")
            else:
                self.module.fail_json(msg=f"Error executing query: {error_message}")
        except Exception as e:
            if not fail_on_error:
                return None
            self.module.fail_json(msg=f"Unexpected error executing query: {str(e)}")

    def close(self):
        """
        Close the database connection
        """
        if self.conn:
            self.conn.close()
            self.conn = None

    def connect_to_database(self, db_name):
        """
        Connect to a specific database

        Args:
            db_name: The name of the database to connect to
        """
        if not self.database_exists(db_name):
            self.module.fail_json(msg=f"Database '{db_name}' does not exist")

        # Close existing connection if any
        self.close()

        # Connect to the specified database
        conn_params = {
            'host': self.host,
            'port': self.port,
            'user': self.user,
            'password': self.password,
            'database': db_name,
            'sslmode': self.ssl_mode
        }

        # Add SSL parameters if provided
        if self.ssl_cert:
            conn_params['sslcert'] = self.ssl_cert

        if self.ssl_key:
            conn_params['sslkey'] = self.ssl_key

        if self.ssl_rootcert:
            conn_params['sslrootcert'] = self.ssl_rootcert

        try:
            self.conn = psycopg2.connect(**conn_params)
            self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            return self.conn
        except Exception as e:
            self.module.fail_json(msg=f"Unable to connect to database '{db_name}': {str(e)}")

    def database_exists(self, db_name):
        """
        Check if a database exists
        """
        result = self.execute_query(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            [db_name],
            fail_on_error=False,
            system_tables=True
        )
        return bool(result)

    def role_exists(self, role_name):
        """
        Check if a role exists
        """
        result = self.execute_query(
            "SELECT 1 FROM pg_roles WHERE rolname = %s",
            [role_name],
            fail_on_error=False,
            system_tables=True
        )
        return bool(result)

    def create_database(self, db_name):
        """
        Create a database
        """
        if not self.database_exists(db_name):
            self.execute_query("CREATE DATABASE %s" % db_name)
            return True
        return False

    def drop_database(self, db_name):
        """
        Drop a database
        """
        if self.database_exists(db_name):
            self.execute_query("DROP DATABASE %s" % db_name)
            return True
        return False

    def create_role(self, role_name, password=None, login=True):
        """
        Create a new role
        """
        if not self.role_exists(role_name):
            query = "CREATE ROLE %s" % role_name
            if login:
                query += " LOGIN"
            if password:
                query += " PASSWORD '%s'" % password
            self.execute_query(query)
            return True
        return False

    def drop_role(self, role_name):
        """
        Drop a role
        """
        if self.role_exists(role_name):
            self.execute_query("DROP ROLE %s" % role_name)
            return True
        return False

    def grant_privileges(self, db_name, role_name, privileges):
        """
        Grant privileges on a database to a role
        """
        if isinstance(privileges, list):
            privileges = ', '.join(privileges)
        query = "GRANT %s ON DATABASE %s TO %s" % (privileges, db_name, role_name)
        self.execute_query(query)
        return True

    def revoke_privileges(self, db_name, role_name, privileges):
        """
        Revoke privileges from a role on a database
        """
        query = f"REVOKE {', '.join(privileges)} ON DATABASE {db_name} FROM {role_name}"
        self.execute_query(query)

    def get_object_privileges(self, object_type, object_name, schema=None, roles=None):
        """
        Get privileges for roles on a specific database object

        Args:
            object_type: Type of object (database, table, etc.)
            object_name: Name of the object
            schema: Schema name for non-database objects
            roles: List of roles to check privileges for

        Returns:
            Dictionary mapping role names to lists of privileges
        """
        # Initialize result
        result = {}

        # Try to use the SHOW GRANTS query first for more accurate results
        try:
            # Build the appropriate object reference for SHOW GRANTS
            if object_type == 'database':
                show_grants_ref = f"DATABASE {object_name}"
            elif object_type == 'table':
                show_grants_ref = f"TABLE {schema}.{object_name}"
            elif object_type == 'schema':
                show_grants_ref = f"SCHEMA {object_name}"
            elif object_type == 'sequence':
                show_grants_ref = f"SEQUENCE {schema}.{object_name}"
            elif object_type == 'view':
                show_grants_ref = f"VIEW {schema}.{object_name}"
            else:
                show_grants_ref = f"{object_type.upper()} {schema}.{object_name}"

            # Direct query to check current grants
            query = f"SHOW GRANTS ON {show_grants_ref}"
            self.module.debug(f"Executing SHOW GRANTS query: {query}")
            grants_result = self.execute_query(query, fail_on_error=False)

            if grants_result:
                for row in grants_result:
                    # Format varies by object type but role/grantee is typically in position 1
                    # and privilege type in position 2 or 3
                    if len(row) >= 4:  # Common format for newer CockroachDB versions
                        # database, schema, or table name, role, privilege_type, is_grantable
                        _, grantee, privilege_type, is_grantable = row
                    elif len(row) >= 3:  # Alternative format
                        # Some versions may not have is_grantable column
                        _, grantee, privilege_type = row
                        is_grantable = 'NO'  # Default to 'NO' if not specified
                    else:
                        # Skip if format is unknown
                        continue

                    # Filter by roles if provided
                    if roles and grantee not in roles:
                        continue

                    if grantee not in result:
                        result[grantee] = []

                    priv_entry = {
                        'privilege': privilege_type,
                        'grantable': is_grantable == 'YES' or is_grantable == 't'
                    }
                    result[grantee].append(priv_entry)

                # If we got results, return them
                if result:
                    return result
        except Exception as e:
            # If SHOW GRANTS fails, log the error and fall back to information_schema
            self.module.debug(f"Error using SHOW GRANTS for {object_type}: {str(e)}")
            self.module.debug("Falling back to information_schema privilege checking")

        # Fall back to information_schema queries if SHOW GRANTS failed
        # Form the fully qualified object name based on object type
        qualified_name = object_name
        if object_type != 'database' and schema:
            qualified_name = f"{schema}.{object_name}"

        # Build the query based on the object type
        if object_type == 'database':
            query = """
                SELECT grantee, privilege_type, is_grantable
                FROM information_schema.role_table_grants
                WHERE table_catalog = %s AND table_schema = 'public'
            """
            params = [object_name]
        else:
            query = """
                SELECT grantee, privilege_type, is_grantable
                FROM information_schema.role_table_grants
                WHERE table_name = %s
            """
            params = [object_name]
            if schema:
                query += " AND table_schema = %s"
                params.append(schema)

        # Filter by roles if provided
        if roles:
            placeholders = ', '.join(['%s'] * len(roles))
            query += f" AND grantee IN ({placeholders})"
            params.extend(roles)

        # Execute query with system_tables=True to handle missing tables gracefully
        privileges_data = self.execute_query(query, params, system_tables=True, fail_on_error=False)

        # Process results
        if privileges_data:
            for row in privileges_data:
                role = row[0]
                privilege = row[1]
                grantable = row[2] == 'YES'

                if role not in result:
                    result[role] = []

                priv_entry = {
                    'privilege': privilege,
                    'grantable': grantable
                }
                result[role].append(priv_entry)

        return result

    def get_table_schema(self, table_name, database=None):
        """
        Get the schema definition for a table
        """
        if database:
            self.execute_query("USE %s" % database)

        columns = self.execute_query("""
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM
                information_schema.columns
            WHERE
                table_schema = 'public' AND table_name = %s
            ORDER BY
                ordinal_position
        """, [table_name])

        # Get primary key info
        pk_columns = self.execute_query("""
            SELECT
                ccu.column_name
            FROM
                information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
            WHERE
                tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_schema = 'public'
                AND tc.table_name = %s
            ORDER BY
                ccu.ordinal_position
        """, [table_name])

        pk_column_names = [row[0] for row in pk_columns]

        result = {
            'columns': [],
            'primary_key': pk_column_names
        }

        for col in columns:
            column_info = {
                'name': col[0],
                'type': col[1],
                'nullable': col[2] == 'YES',
                'default': col[3],
                'primary_key': col[0] in pk_column_names
            }
            result['columns'].append(column_info)

        return result

    def get_database_size(self, db_name):
        """
        Get the size of a database in bytes
        """
        result = self.execute_query("""
            SELECT sum(range_size)
            FROM [SHOW RANGES FROM DATABASE %s]
        """ % db_name)

        if result and result[0][0]:
            return result[0][0]
        return 0

    def get_table_size(self, table_name, database=None):
        """
        Get the size of a table in bytes
        """
        if database:
            self.execute_query("USE %s" % database)

        result = self.execute_query("""
            SELECT sum(range_size)
            FROM [SHOW RANGES FROM TABLE %s]
        """ % table_name)

        if result and result[0][0]:
            return result[0][0]
        return 0

    def get_version(self):
        """
        Get CockroachDB version
        """
        result = self.execute_query("SELECT version()")
        if result:
            # Parse version string to extract the actual version number
            version_str = result[0][0]
            version_match = re.search(r'CockroachDB v([0-9.]+)', version_str)
            if version_match:
                return version_match.group(1)
        return None

    def is_enterprise(self):
        """
        Check if this is an enterprise edition of CockroachDB
        """
        result = self.execute_query("SHOW CLUSTER SETTING cluster.organization")
        return bool(result and result[0][0])

    def table_exists(self, table_name, schema=None, database=None):
        """
        Check if a table exists

        Args:
            table_name: The name of the table
            schema: Optional schema name (default: 'public')
            database: Optional database name
        """
        params = [table_name]
        query = """
            SELECT 1 FROM information_schema.tables
            WHERE table_name = %s AND table_type = 'BASE TABLE'
        """

        if schema:
            query += " AND table_schema = %s"
            params.append(schema)

        if database:
            query += " AND table_catalog = %s"
            params.append(database)

        return bool(self.execute_query(
            query,
            params,
            fail_on_error=False,
            system_tables=True
        ))

    def view_exists(self, view_name, schema=None, database=None):
        """
        Check if a view exists

        Args:
            view_name: The name of the view
            schema: Optional schema name
            database: Optional database name

        Returns:
            Boolean indicating if the object exists
        """
        params = [view_name]
        query = """
            SELECT 1 FROM information_schema.tables
            WHERE table_name = %s
        """

        if schema:
            query += " AND table_schema = %s"
            params.append(schema)

        if database:
            query += " AND table_catalog = %s"
            params.append(database)

        return bool(self.execute_query(
            query,
            params,
            fail_on_error=False,
            system_tables=True
        ))

    def index_exists(self, index_name, table_name):
        """
        Check if an index exists on a table
        """
        result = self.execute_query("""
            SELECT 1
            FROM [SHOW INDEXES FROM {}]
            WHERE index_name = %s
        """.format(table_name), [index_name])
        return bool(result)

    def schema_exists(self, schema_name, database=None):
        """
        Check if a schema exists

        Args:
            schema_name: The name of the schema
            database: Optional database name
        """
        params = [schema_name]
        query = """
            SELECT 1
            FROM information_schema.schemata
            WHERE schema_name = %s
        """

        if database:
            query += " AND catalog_name = %s"
            params.append(database)

        return bool(self.execute_query(
            query,
            params,
            fail_on_error=False,
            system_tables=True
        ))

    def get_index_details(self, index_name, table_name):
        """
        Get detailed information about an index
        """
        result = self.execute_query("""
            SELECT i.index_name, i.is_unique, i.column_names, i.storing_names, i.index_type
            FROM [SHOW INDEXES FROM {}] AS i
            WHERE i.index_name = %s
        """.format(table_name), [index_name])

        if result:
            row = result[0]
            return {
                'name': row[0],
                'is_unique': row[1],
                'column_names': row[2],
                'storing_names': row[3],
                'index_type': row[4]
            }
        return None

    def get_partition_info(self, table_name, database=None):
        """
        Get partition information for a table
        """
        if database:
            self.execute_query("USE %s" % database)

        # Try to get partition information from the CockroachDB metadata
        try:
            # First check if the table is partitioned
            partition_query = """
                SELECT
                    partition_name,
                    partition_method,
                    partition_expression,
                    partition_value
                FROM
                    crdb_internal.table_partitions
                WHERE
                    table_name = %s
                ORDER BY
                    partition_ordinal_position
            """

            result = self.execute_query(partition_query, [table_name])

            if not result:
                # No partitioning information found
                return None

            partitions = []
            partition_type = None
            partition_columns = None

            for row in result:
                part_name = row[0]
                part_method = row[1]  # HASH, RANGE, LIST
                part_expr = row[2]    # Columns used for partitioning
                part_value = row[3]   # Values for the partition

                # Extract column names from expression
                if not partition_columns and part_expr:
                    # Simple parsing, assumes format like: "region" or "(region, country)"
                    columns_str = part_expr.strip('()')
                    partition_columns = [col.strip() for col in columns_str.split(',')]

                if not partition_type and part_method:
                    partition_type = part_method

                partitions.append({
                    'name': part_name,
                    'values': part_value,
                })

            return {
                'partition_type': partition_type,
                'partition_columns': partition_columns,
                'partitions': partitions
            }

        except Exception:
            # If table_partitions view doesn't exist or other error, try to fall back to SHOW CREATE TABLE
            try:
                create_table_result = self.execute_query("SHOW CREATE TABLE %s" % table_name)

                if create_table_result and create_table_result[0][1]:
                    create_stmt = create_table_result[0][1]

                    # Check if the statement contains PARTITION BY
                    if "PARTITION BY" in create_stmt.upper():
                        # Simple parsing - extract partition information
                        partition_info = {
                            'has_partitioning': True,
                            'create_statement': create_stmt
                        }

                        # Extract the partition type (HASH, LIST, RANGE)
                        if "PARTITION BY HASH" in create_stmt.upper():
                            partition_info['partition_type'] = 'HASH'
                        elif "PARTITION BY LIST" in create_stmt.upper():
                            partition_info['partition_type'] = 'LIST'
                        elif "PARTITION BY RANGE" in create_stmt.upper():
                            partition_info['partition_type'] = 'RANGE'

                        return partition_info
            except Exception:
                pass

            return None

    def sequence_exists(self, sequence_name, schema=None, database=None):
        """
        Check if a sequence exists

        Args:
            sequence_name: The name of the sequence
            schema: Optional schema name (default: 'public')
            database: Optional database name

        Returns:
            Boolean indicating if the sequence exists
        """
        params = [sequence_name]
        query = """
            SELECT 1 FROM information_schema.sequences
            WHERE sequence_name = %s
        """

        if schema:
            query += " AND sequence_schema = %s"
            params.append(schema)

        if database:
            query += " AND sequence_catalog = %s"
            params.append(database)

        return bool(self.execute_query(
            query,
            params,
            fail_on_error=False,
            system_tables=True
        ))

    def schema_exists(self, schema_name, database=None):
        """
        Check if a schema exists in a database

        Args:
            schema_name: The name of the schema to check
            database: Optional database name to check in

        Returns:
            Boolean indicating if the schema exists
        """
        query = "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s"
        params = [schema_name]

        if database:
            query += " AND catalog_name = %s"
            params.append(database)

        result = self.execute_query(
            query,
            params,
            fetch=True,
            fail_on_error=False,
            system_tables=True
        )

        return bool(result)
