#!/usr/bin/python
# -*- coding: utf-8 -*-
# pylint: disable=line-too-long, broad-exception-caught

# Copyright: (c) 2025, Cockroach Labs
# Apache License, Version 2.0 (see LICENSE or http://www.apache.org/licenses/LICENSE-2.0)

"""
Ansible module for performing maintenance operations on a CockroachDB cluster.

This module provides tools for database administrators to maintain and optimize
CockroachDB clusters, including garbage collection, schema cleanup,
node management, query cancellation, and data distribution operations.

The documentation for this module is maintained in the plugins/docs/cockroachdb_maintenance.yml file.
"""

import re
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_native
from ansible_collections.cockroach_labs.cockroachdb.plugins.module_utils.cockroachdb import (
    CockroachDBHelper,
    HAS_PSYCOPG2,
    COCKROACHDB_IMP_ERR
)

ANSIBLE_METADATA = {
    "metadata_version": "1.1",
    "status": ["preview"],
    "supported_by": "cockroach_labs",
}

def main():
    argument_spec = dict(
        operation=dict(
            type='str',
            required=True,
            choices=[
                'gc',
                'schema_cleanup',
                'node_status',
                'node_decommission',
                'zone_config',
                'version_upgrade_check',
                'cancel_query',
                'cancel_session',
                'cancel_jobs',
                'troubleshoot_query',
                'rebalance_data',
                'reassign_ranges',
            ]
        ),
        database=dict(type='str'),
        table=dict(type='str'),
        node_id=dict(type='int'),
        ttl=dict(type='str'),
        query_id=dict(type='str'),
        session_id=dict(type='str'),
        job_id=dict(type='raw'),
        job_type=dict(type='str'),
        job_status=dict(type='str'),
        zone_configs=dict(
            type='dict',
            options=dict(
                target=dict(type='str'),
                config=dict(
                    type='dict',
                    options=dict(
                        num_replicas=dict(type='int'),
                        constraints=dict(type='list', elements='dict'),
                        lease_preferences=dict(type='list', elements='dict'),
                    )
                )
            )
        ),
        rebalance_options=dict(
            type='dict',
            options=dict(
                dry_run=dict(type='bool', default=False),
                max_moves=dict(type='int'),
                locality=dict(type='str'),
            )
        ),
        troubleshoot_options=dict(
            type='dict',
            options=dict(
                query_text=dict(type='str'),
                collect_explain=dict(type='bool', default=True),
                collect_trace=dict(type='bool', default=False),
                trace_options=dict(type='dict'),
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

    operation = module.params['operation']
    database = module.params['database']
    table = module.params['table']
    node_id = module.params['node_id']
    ttl = module.params['ttl']
    query_id = module.params['query_id']
    session_id = module.params['session_id']
    job_id = module.params['job_id']
    job_type = module.params['job_type']
    job_status = module.params['job_status']
    zone_configs = module.params['zone_configs'] or {}
    rebalance_options = module.params['rebalance_options'] or {}
    troubleshoot_options = module.params['troubleshoot_options'] or {}

    # Parameter validation based on operation
    if operation == 'gc' and (not database or not table or not ttl):
        module.fail_json(msg="database, table, and ttl are required for gc operation")

    if operation == 'schema_cleanup' and not database:
        module.fail_json(msg="database is required for schema_cleanup operation")

    if operation == 'node_decommission' and not node_id:
        module.fail_json(msg="node_id is required for node_decommission operation")

    if operation == 'cancel_query' and not query_id:
        module.fail_json(msg="query_id is required for cancel_query operation")

    if operation == 'cancel_session' and not session_id:
        module.fail_json(msg="session_id is required for cancel_session operation")

    if operation == 'zone_config' and not zone_configs:
        module.fail_json(msg="zone_configs is required for zone_config operation")

    if operation == 'troubleshoot_query' and not troubleshoot_options.get('query_text'):
        module.fail_json(msg="troubleshoot_options.query_text is required for troubleshoot_query operation")

    # Initialize helper
    helper = CockroachDBHelper(module)

    try:
        helper.connect()

        # Initialize result
        result = {
            'changed': False,
            'queries': [],
        }

        # Handle different operations
        if operation == 'gc':
            # Connect to the specific database
            helper.connect_to_database(database)

            # Parse TTL string to seconds
            ttl_seconds = 0
            if 'h' in ttl:
                ttl_seconds = int(ttl.replace('h', '')) * 3600
            elif 'd' in ttl:
                ttl_seconds = int(ttl.replace('d', '')) * 86400
            elif 'm' in ttl:
                ttl_seconds = int(ttl.replace('m', '')) * 60
            else:
                ttl_seconds = int(ttl)

            # Get current TTL with a more specific query
            current_ttl_query = f"""
                SHOW ZONE CONFIGURATION FOR TABLE {database}.{table}
            """

            current_ttl_result = helper.execute_query(current_ttl_query)
            current_ttl_seconds = None

            # Format is different in CRDB 23.2+, so we need to handle both formats
            try:
                # The output format is typically (table_name, config_expression)
                # We need to extract the gc.ttlseconds value from the config_expression
                for row in current_ttl_result:
                    # The config is usually in the second column as a string
                    if row and len(row) >= 2:
                        config_str = str(row[1])
                        # Look for gc.ttlseconds in the config string
                        ttl_match = re.search(r"gc\.ttlseconds\s*=\s*(\d+)", config_str)
                        if ttl_match:
                            # Extract the current TTL value from the match
                            current_ttl_seconds = int(ttl_match.group(1))
                            break
            except (IndexError, TypeError):
                # If there's an issue with row format, use default TTL
                current_ttl_seconds = 25 * 3600  # 25 hours (CockroachDB default)

            # Set new TTL only if it's different
            set_ttl_query = f"""
                ALTER TABLE {database}.{table} CONFIGURE ZONE USING gc.ttlseconds = {ttl_seconds}
            """

            # Determine if we need to make a change - exact second match required
            needs_change = (current_ttl_seconds is None or current_ttl_seconds != ttl_seconds)

            # Always include the queries for logging purposes
            result['queries'].append(set_ttl_query)

            # Execute query if not in check mode and TTL is different
            if needs_change and not module.check_mode:
                helper.execute_query(set_ttl_query)
                result['changed'] = True
            else:
                # Specifically setting to False to ensure it's not changed
                result['changed'] = False

            # Add details to result
            result['details'] = {
                'gc': {
                    'previous_ttl': f"{current_ttl_seconds // 3600}h" if current_ttl_seconds else "default",
                    'current_ttl': f"{ttl_seconds // 3600}h"
                }
            }



        elif operation == 'schema_cleanup':
            # Connect to the specific database
            helper.connect_to_database(database)

            # Find potential orphaned schema objects
            # This includes temporary tables, old views, unused indexes, etc.

            orphaned_tables_query = """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name LIKE 'temp_%'
                OR table_name LIKE '%_old'
                OR table_name LIKE '%_bak'
            """

            orphaned_indexes_query = """
                SELECT i.index_name, i.table_name
                FROM information_schema.statistics i
                LEFT JOIN information_schema.tables t
                ON i.table_name = t.table_name AND i.table_schema = t.table_schema
                WHERE i.index_name LIKE '%_old'
                OR i.index_name LIKE '%_bak'
                OR i.index_name LIKE 'temp_%'
            """

            orphaned_views_query = """
                SELECT table_name
                FROM information_schema.views
                WHERE table_schema = 'public'
                AND table_name LIKE '%_deprecated'
                OR table_name LIKE '%_old'
            """

            tables_to_drop = []
            indexes_to_drop = []
            views_to_drop = []

            # Gather orphaned schema objects
            tables_result = helper.execute_query(orphaned_tables_query)
            for row in tables_result:
                tables_to_drop.append(row[0])

            indexes_result = helper.execute_query(orphaned_indexes_query)
            for row in indexes_result:
                indexes_to_drop.append((row[0], row[1]))

            views_result = helper.execute_query(orphaned_views_query)
            for row in views_result:
                views_to_drop.append(row[0])

            # Build cleanup queries
            cleanup_queries = []
            cleanup_details = []

            for table in tables_to_drop:
                drop_query = f"DROP TABLE IF EXISTS {database}.public.{table}"
                cleanup_queries.append(drop_query)
                cleanup_details.append(f"Dropped orphaned table: {table}")

            for index_name, table_name in indexes_to_drop:
                drop_query = f"DROP INDEX IF EXISTS {database}.public.{table_name}@{index_name}"
                cleanup_queries.append(drop_query)
                cleanup_details.append(f"Dropped orphaned index: {index_name} on table {table_name}")

            for view in views_to_drop:
                drop_query = f"DROP VIEW IF EXISTS {database}.public.{view}"
                cleanup_queries.append(drop_query)
                cleanup_details.append(f"Dropped orphaned view: {view}")

            result['queries'].extend(cleanup_queries)

            # Execute cleanup queries if not in check mode
            if cleanup_queries and not module.check_mode:
                for query in cleanup_queries:
                    helper.execute_query(query)
                result['changed'] = True

            # Add details to result
            result['schema_objects'] = {
                'dropped_tables': len(tables_to_drop),
                'dropped_indexes': len(indexes_to_drop),
                'dropped_views': len(views_to_drop),
                'details': cleanup_details
            }

        elif operation == 'node_status':
            # Get node status
            nodes_query = """
                SELECT
                    node_id,
                    address,
                    build,
                    started_at,
                    is_available,
                    is_live,
                    locality
                FROM crdb_internal.gossip_nodes
            """

            nodes_metrics_query = """
                SELECT
                    node_id,
                    store_id,
                    capacity,
                    available,
                    used_bytes,
                    range_count
                FROM crdb_internal.kv_store_status
            """

            nodes_result = helper.execute_query(nodes_query)
            nodes_metrics = helper.execute_query(nodes_metrics_query)

            # Build nodes list with their status and metrics
            nodes = []
            node_metrics = {}

            # Process metrics first into a lookup dictionary
            for m_row in nodes_metrics:
                node_id = m_row[0]
                if node_id not in node_metrics:
                    node_metrics[node_id] = []

                node_metrics[node_id].append({
                    'store_id': m_row[1],
                    'capacity': m_row[2],
                    'available': m_row[3],
                    'used': m_row[4],
                    'range_count': m_row[5]
                })

            # Process nodes with their metrics
            for row in nodes_result:
                node = {
                    'id': row[0],
                    'address': row[1],
                    'build': row[2],
                    'started_at': row[3].isoformat() if row[3] else None,
                    'is_available': row[4],
                    'is_live': row[5],
                    'locality': row[6],
                    'metrics': node_metrics.get(row[0], [])
                }
                nodes.append(node)

            # No changes for this operation
            result['changed'] = False
            result['nodes'] = nodes

        elif operation == 'node_decommission':
            # First, check current node status
            nodes_query = """
                SELECT node_id, is_decommissioning, is_draining
                FROM crdb_internal.gossip_nodes
                WHERE node_id = %s
            """
            nodes_result = helper.execute_query(nodes_query, [node_id])

            is_already_decommissioning = False
            node_status = None
            result['changed'] = False  # Default to no change

            if nodes_result:
                is_already_decommissioning = nodes_result[0][1] or nodes_result[0][2]
                node_status = {
                    'id': nodes_result[0][0],
                    'is_decommissioning': nodes_result[0][1],
                    'is_draining': nodes_result[0][2],
                    'current_status': 'decommissioning' if is_already_decommissioning else 'active'
                }
                result['nodes'] = [node_status]
            else:
                # Node not found
                module.warn(f"Node {node_id} not found in cluster")
                result['nodes'] = [{
                    'id': node_id,
                    'current_status': 'not_found',
                    'message': 'Node not found in cluster'
                }]
                # Node not found means no change possible
                return result

            # Decommission a node only if not already decommissioning
            decommission_query = f"""
                SELECT crdb_internal.node_decommission({node_id}, true)
            """

            result['queries'].append(decommission_query)

            # Execute query if not in check mode and node is not already decommissioning
            if not module.check_mode and not is_already_decommissioning:
                helper.execute_query(decommission_query)
                result['changed'] = True

                # Get updated node status
                updated_nodes_result = helper.execute_query(nodes_query, [node_id])

                if updated_nodes_result:
                    updated_node_status = {
                        'id': updated_nodes_result[0][0],
                        'is_decommissioning': updated_nodes_result[0][1],
                        'is_draining': updated_nodes_result[0][2],
                        'current_status': 'decommissioning'
                    }
                    result['nodes'] = [updated_node_status]

        elif operation == 'zone_config':
            # Configure zone configuration
            target = zone_configs.get('target')
            config = zone_configs.get('config', {})

            if not target:
                module.fail_json(msg="zone_configs.target is required for zone_config operation")

            # Build zone configuration parts
            zone_parts = []

            if 'num_replicas' in config:
                zone_parts.append(f"num_replicas = {config['num_replicas']}")

            # Process constraints
            constraints = config.get('constraints', [])
            for constraint in constraints:
                constraint_type = constraint.get('type', 'required')  # default to required
                key = constraint.get('key')
                value = constraint.get('value')

                if key and value:
                    zone_parts.append(f"constraints = '{constraint_type}:{key}={value}'")

            # Process lease preferences
            lease_prefs = config.get('lease_preferences', [])
            for pref in lease_prefs:
                pref_constraints = pref.get('constraints', [])
                if pref_constraints:
                    constraints_parts = []
                    for pc in pref_constraints:
                        key = pc.get('key')
                        value = pc.get('value')
                        if key and value:
                            constraints_parts.append(f"{key}={value}")

                    if constraints_parts:
                        constraints_str = ', '.join(constraints_parts)
                        zone_parts.append(f"lease_preferences = '[[+{constraints_str}]]'")

            # Create zone configuration query
            if zone_parts:
                zone_settings = ", ".join(zone_parts)
                zone_query = f"""
                    ALTER {target} CONFIGURE ZONE USING {zone_settings}
                """

                result['queries'].append(zone_query)

                # Execute query if not in check mode
                if not module.check_mode:
                    helper.execute_query(zone_query)
                    result['changed'] = True

        elif operation == 'version_upgrade_check':
            # Check cluster readiness for version upgrade
            upgrade_check_query = """
                SELECT *
                FROM crdb_internal.cluster_settings
                WHERE variable = 'version'
            """

            jobs_query = """
                SELECT count(*)
                FROM [SHOW JOBS]
                WHERE status = 'running'
            """

            decommission_query = """
                SELECT count(*)
                FROM crdb_internal.gossip_nodes
                WHERE is_decommissioning = true OR is_draining = true
            """

            # Run queries
            version_result = helper.execute_query(upgrade_check_query)
            jobs_result = helper.execute_query(jobs_query)
            decommission_result = helper.execute_query(decommission_query)

            running_jobs = jobs_result[0][0] if jobs_result else 0
            decommissioning_nodes = decommission_result[0][0] if decommission_result else 0

            current_version = version_result[0][2] if version_result else "unknown"

            # Determine upgrade readiness
            is_ready = running_jobs == 0 and decommissioning_nodes == 0

            # No changes for this operation
            result['changed'] = False
            result['details'] = {
                'version_upgrade': {
                    'current_version': current_version,
                    'is_ready': is_ready,
                    'blocking_issues': {
                        'running_jobs': running_jobs,
                        'decommissioning_nodes': decommissioning_nodes
                    }
                }
            }

        elif operation == 'cancel_query':
            # First check if the query is still running
            check_query = f"""
                SELECT query_id
                FROM [SHOW QUERIES]
                WHERE query_id = '{query_id}'
            """

            query_exists = False
            result['changed'] = False  # Default to no change
            check_result = helper.execute_query(check_query)
            if check_result and len(check_result) > 0:
                query_exists = True

            # Cancel a specific query
            cancel_query = f"""
                CANCEL QUERY {query_id}
            """

            result['queries'].append(cancel_query)
            result['details'] = {
                'query_id': query_id,
                'query_exists': query_exists,
                'status': 'canceled' if query_exists and not module.check_mode else ('not running' if not query_exists else 'would be canceled')
            }

            # Execute query if not in check mode and the query exists
            if not module.check_mode and query_exists:
                helper.execute_query(cancel_query)
                result['changed'] = True

        elif operation == 'cancel_session':
            # First check if the session is still active
            check_session = f"""
                SELECT session_id
                FROM [SHOW SESSIONS]
                WHERE session_id = '{session_id}'
            """

            session_exists = False
            result['changed'] = False  # Default to no change
            check_result = helper.execute_query(check_session)
            if check_result and len(check_result) > 0:
                session_exists = True

            # Cancel a specific session
            cancel_session_query = f"""
                CANCEL SESSION {session_id}
            """

            result['queries'].append(cancel_session_query)
            result['details'] = {
                'session_id': session_id,
                'session_exists': session_exists,
                'status': 'canceled' if session_exists and not module.check_mode else ('not active' if not session_exists else 'would be canceled')
            }

            # Execute query if not in check mode and the session exists
            if not module.check_mode and session_exists:
                helper.execute_query(cancel_session_query)
                result['changed'] = True

        elif operation == 'cancel_jobs':
            # Cancel jobs by ID or by type
            cancelled_jobs = []
            jobs_to_cancel = []
            result['changed'] = False  # Initially set to False, will be set to True if any jobs are cancelled

            if job_id:
                # Convert to list if single value provided
                job_ids = job_id if isinstance(job_id, list) else [job_id]

                for jid in job_ids:
                    # First check if the job is in a cancellable state
                    job_query = f"""
                        SELECT job_id, job_type, status, description
                        FROM [SHOW JOBS]
                        WHERE job_id = {jid}
                    """
                    job_result = helper.execute_query(job_query)

                    # Only cancel job if it exists and is in a cancellable state
                    job_cancellable = False
                    job_details = None

                    if job_result:
                        status = job_result[0][2]
                        job_details = {
                            'id': job_result[0][0],
                            'type': job_result[0][1],
                            'status': status,
                            'description': job_result[0][3]
                        }

                        # Jobs that are running or pending can be cancelled
                        job_cancellable = status in ['running', 'pending']

                    if job_details:
                        job_details['cancellable'] = job_cancellable
                        cancelled_jobs.append(job_details)

                    if job_cancellable:
                        jobs_to_cancel.append(jid)

                        cancel_job_query = f"""
                            CANCEL JOB {jid}
                        """
                        result['queries'].append(cancel_job_query)

                        # Execute query if not in check mode
                        if not module.check_mode:
                            helper.execute_query(cancel_job_query)
                            result['changed'] = True

                            # Update job status in results
                            for job in cancelled_jobs:
                                if job['id'] == jid:
                                    job['status'] = 'canceled'

            elif job_type:
                # Build WHERE clause for job type and status
                where_clauses = [f"job_type = '{job_type}'"]

                if job_status:
                    where_clauses.append(f"status = '{job_status}'")
                else:
                    # Default to running jobs if no status specified
                    where_clauses.append("status = 'running'")

                where_clause = " AND ".join(where_clauses)

                # Find jobs
                jobs_query = f"""
                    SELECT job_id, job_type, status, description
                    FROM [SHOW JOBS]
                    WHERE {where_clause}
                """

                jobs_result = helper.execute_query(jobs_query)

                # Track if any jobs need to be cancelled
                jobs_changed = False

                # Cancel each job
                for row in jobs_result:
                    job_id = row[0]
                    status = row[2]

                    # Add job to list with details
                    job_details = {
                        'id': row[0],
                        'type': row[1],
                        'status': status,
                        'description': row[3],
                        'cancellable': status in ['running', 'pending']
                    }
                    cancelled_jobs.append(job_details)

                    # Only cancel jobs that are running or pending
                    if status in ['running', 'pending']:
                        cancel_job_query = f"""
                            CANCEL JOB {job_id}
                        """

                        result['queries'].append(cancel_job_query)

                        # Execute query if not in check mode
                        if not module.check_mode:
                            helper.execute_query(cancel_job_query)
                            jobs_changed = True

                            # Update job status in results
                            job_details['status'] = 'canceled'

                # Only mark changed if we actually cancelled any jobs
                if jobs_changed:
                    result['changed'] = True

            else:
                module.fail_json(msg="Either job_id or job_type must be specified for cancel_jobs operation")

            # Add cancelled jobs to result
            result['jobs'] = cancelled_jobs

        elif operation == 'troubleshoot_query':
            # Analyze and troubleshoot a query
            query_text = troubleshoot_options.get('query_text')
            collect_explain = troubleshoot_options.get('collect_explain', True)
            collect_trace = troubleshoot_options.get('collect_trace', False)

            troubleshooting_results = {}

            # Collect EXPLAIN plan
            if collect_explain:
                explain_query = f"""
                    EXPLAIN (VERBOSE, OPT, ENV) {query_text}
                """

                try:
                    explain_result = helper.execute_query(explain_query)
                    explain_output = "\n".join([row[0] for row in explain_result])
                    troubleshooting_results['explain_plan'] = explain_output
                except Exception as e:
                    troubleshooting_results['explain_error'] = str(e)

            # Collect execution trace if requested
            if collect_trace:
                try:
                    # Enable session tracing
                    helper.execute_query("SET tracing = on")

                    # Execute query with tracing
                    helper.execute_query(query_text)

                    # Disable tracing
                    helper.execute_query("SET tracing = off")

                    # Retrieve trace
                    trace_query = """
                        SELECT * FROM [SHOW TRACE FOR SESSION]
                    """

                    trace_result = helper.execute_query(trace_query)
                    trace_lines = []

                    for row in trace_result:
                        timestamp = row[0]
                        message = row[4]
                        trace_lines.append(f"[{timestamp}] {message}")

                    trace_output = "\n".join(trace_lines)
                    troubleshooting_results['execution_trace'] = trace_output

                except Exception as e:
                    troubleshooting_results['trace_error'] = str(e)
                finally:
                    # Ensure tracing is disabled
                    helper.execute_query("SET tracing = off")

            # No changes for this operation
            result['changed'] = False
            result['troubleshooting'] = troubleshooting_results

        elif operation == 'rebalance_data':
            # Rebalance data across nodes
            dry_run = rebalance_options.get('dry_run', False)
            max_moves = rebalance_options.get('max_moves')
            locality = rebalance_options.get('locality')

            # Get initial distribution
            distribution_query = """
                SELECT
                    node_id,
                    range_count,
                    lease_count
                FROM
                    crdb_internal.node_status
            """

            initial_distribution = {}
            dist_result = helper.execute_query(distribution_query)

            for row in dist_result:
                initial_distribution[row[0]] = {
                    'ranges': row[1],
                    'leases': row[2]
                }

            # Build rebalance query options
            rebalance_parts = []

            if dry_run:
                rebalance_parts.append("DRY RUN")

            if max_moves:
                rebalance_parts.append(f"WITH MAX MOVES {max_moves}")

            if locality:
                rebalance_parts.append(f"WITH LOCALITY '{locality}'")

            # Rebalance query
            rebalance_opts = " ".join(rebalance_parts)
            rebalance_query = f"""
                ALTER CLUSTER EXPERIMENTAL REBALANCE {rebalance_opts}
            """

            result['queries'].append(rebalance_query)

            # Execute query if not in check mode
            rebalance_result = {}

            if not module.check_mode:
                rebalance_output = helper.execute_query(rebalance_query)

                # Parse rebalance output
                if rebalance_output:
                    moves_match = re.search(r'moved (\d+) ranges', rebalance_output[0][0])
                    size_match = re.search(r'moved (\d+) bytes', rebalance_output[0][0])

                    ranges_moved = int(moves_match.group(1)) if moves_match else 0
                    data_moved = int(size_match.group(1)) if size_match else 0

                    rebalance_result = {
                        'ranges_moved': ranges_moved,
                        'data_size_moved_bytes': data_moved,
                        'before_distribution': initial_distribution
                    }

                    # Only mark as changed if not a dry run and some ranges moved
                    if not dry_run and ranges_moved > 0:
                        result['changed'] = True

                        # Get final distribution
                        final_dist_result = helper.execute_query(distribution_query)
                        final_distribution = {}

                        for row in final_dist_result:
                            final_distribution[row[0]] = {
                                'ranges': row[1],
                                'leases': row[2]
                            }

                        rebalance_result['after_distribution'] = final_distribution

            result['rebalance'] = rebalance_result or {
                'before_distribution': initial_distribution,
                'would_rebalance': True if not module.check_mode else False
            }

        elif operation == 'reassign_ranges':
            module.fail_json(msg="Operation 'reassign_ranges' not fully implemented yet")

        module.exit_json(**result)

    except Exception as e:
        module.fail_json(msg=f"Error in maintenance operation: {to_native(e)}")

    finally:
        if helper.conn:
            helper.conn.close()


if __name__ == '__main__':
    main()
