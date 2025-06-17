#!/usr/bin/python
# -*- coding: utf-8 -*-
# pylint: disable=line-too-long, broad-exception-caught

# Copyright: (c) 2025, Cockroach Labs
# Apache License, Version 2.0 (see LICENSE or http://www.apache.org/licenses/LICENSE-2.0)

"""
Ansible module for managing CockroachDB backups and restores.

This module allows you to:
- Create full and incremental backups of CockroachDB databases and tables
- Restore databases from previously created backups
- List available backups in a storage location (S3, GCS, Azure, or local filesystem)

CockroachDB's backup system provides a reliable way to protect your data
with minimal impact on cluster performance. Backups can be encrypted,
incremental, and stored in various cloud storage providers.

For full documentation, see the plugins/docs/cockroachdb_backup.yml file
"""

# import sys
# import time
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.cockroachdb import CockroachDBHelper

ANSIBLE_METADATA = {
    "metadata_version": "1.1",
    "status": ["preview"],
    "supported_by": "cockroach_labs",
}

def main():
    module_args = dict(
        operation=dict(type='str', required=True, choices=['backup', 'restore', 'list']),
        database=dict(type='str'),
        table=dict(type='str'),
        uri=dict(type='str'),
        options=dict(type='dict', default={},
            options=dict(
                as_of_timestamp=dict(type='str'),
                incremental_from=dict(type='list', elements='str'),
                kms_uri=dict(type='str'),
                encryption_passphrase=dict(type='str', no_log=True),
                detached=dict(type='bool', default=False),
            )
        ),
        host=dict(type='str', default='localhost'),
        port=dict(type='int', default=26257),
        user=dict(type='str', default='root'),
        password=dict(type='str', no_log=True),
        ssl_mode=dict(type='str', default='verify-full', choices=['disable', 'allow', 'prefer', 'require', 'verify-ca', 'verify-full']),
        ssl_cert=dict(type='path'),
        ssl_key=dict(type='path'),
        ssl_rootcert=dict(type='path'),
        timeout=dict(type='int', default=600),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        required_if=[
            ('operation', 'backup', ['uri']),
            ('operation', 'restore', ['uri']),
            ('operation', 'list', ['uri']),
        ]
    )

    operation = module.params['operation']
    database = module.params.get('database')
    table = module.params.get('table')
    uri = module.params.get('uri')
    options = module.params.get('options', {})
    timeout = module.params.get('timeout', 600)

    result = {
        'changed': False,
        'operation': operation,
        'uri': uri
    }

    if database:
        result['database'] = database

    if table:
        result['table'] = table

    # Don't perform actual operations in check mode
    if module.check_mode:
        if operation in ['backup', 'restore']:
            result['changed'] = True
        module.exit_json(**result)

    db = CockroachDBHelper(module)

    try:
        # Connect to the CockroachDB server
        db.connect()

        if operation == 'backup':
            if not database and not table:
                module.fail_json(msg="Either 'database' or 'table' parameter is required for backup operation")

            # Construct BACKUP command
            backup_target = f"DATABASE {database}" if database and not table else f"TABLE {table}"

            # Check if backup already exists using SHOW BACKUPS IN for idempotency
            backup_exists = False

            # For idempotency, we check if any recent backup exists for this target
            # CockroachDB creates timestamped subdirectories for each backup
            try:
                # Check for existing backups in the collection
                check_cmd = f"SHOW BACKUPS IN '{uri}'"
                existing_backups = db.execute_query(check_cmd)

                if existing_backups and len(existing_backups) > 0:
                    # If any backups exist in this collection, check the most recent one
                    most_recent_backup = sorted(existing_backups, key=lambda x: x[0])[-1]
                    backup_path = most_recent_backup[0]

                    # Check if the backup is for the same target (database/table)
                    # by inspecting the backup manifest using the new syntax
                    backup_path = most_recent_backup[0]
                    try:
                        # Use the new SHOW BACKUP FROM ... IN ... syntax
                        # Extract collection path and backup subdirectory
                        show_cmd = f"SHOW BACKUP FROM '{backup_path}' IN '{uri}'"
                        backup_details = db.execute_query(show_cmd)

                        # Check if this backup contains our target database/table
                        target_found = False
                        if backup_details:
                            for detail_row in backup_details:
                                # Columns: database_name, parent_schema_name, object_name, object_type, ...
                                db_name = detail_row[0] if len(detail_row) > 0 else None
                                parent_schema = detail_row[1] if len(detail_row) > 1 else None
                                object_name = detail_row[2] if len(detail_row) > 2 else None
                                object_type = detail_row[3] if len(detail_row) > 3 else None

                                # For database backup: check if database exists in backup
                                if database and not table:
                                    if object_type == 'database' and object_name == database:
                                        target_found = True
                                        break
                                # For table backup: check if specific table exists in backup
                                elif table:
                                    if (object_type == 'table' and
                                        db_name == database and
                                        object_name == table):
                                        target_found = True
                                        break

                        if target_found:
                            backup_exists = True

                    except Exception as show_e:
                        # If we can't inspect the backup, be conservative and assume no match
                        pass

                if backup_exists:
                    result['changed'] = False
                    result['msg'] = f"Recent backup already exists for {backup_target} at {uri}"
                    module.exit_json(**result)

            except Exception as e:
                # If SHOW BACKUPS IN fails, the collection likely doesn't exist
                # This is expected for the first backup
                backup_exists = False

            # Build the backup command since no existing backup was found
            cmd_parts = [f"BACKUP {backup_target} INTO '{uri}'"]

            # Add AS OF SYSTEM TIME if specified
            if options.get('as_of_timestamp'):
                cmd_parts.append(f"AS OF SYSTEM TIME '{options['as_of_timestamp']}'")

            # Add incremental_from if specified
            if options.get('incremental_from'):
                incremental_locations = [f"'{loc}'" for loc in options['incremental_from']]
                cmd_parts.append(f"INCREMENTAL FROM {', '.join(incremental_locations)}")

            # Add KMS if specified
            if options.get('kms_uri'):
                cmd_parts.append(f"KMS = '{options['kms_uri']}'")

            # Add encryption if specified
            if options.get('encryption_passphrase'):
                cmd_parts.append(f"ENCRYPTION_PASSPHRASE = '{options['encryption_passphrase']}'")

            # Add WITH clause for detached option
            if options.get('detached', False):
                cmd_parts.append("WITH DETACHED")

            backup_cmd = " ".join(cmd_parts)

            try:
                # Execute the backup command
                response = db.execute_query(backup_cmd)

                if options.get('detached', False) and response:
                    # Extract job ID
                    result['job_id'] = response[0][0]

                result['changed'] = True

            except Exception as e:
                # Check if backup failed because it already exists or is a duplicate
                error_msg = str(e).lower()
                if ('already exists' in error_msg or
                    'duplicate' in error_msg or
                    'backup already exists' in error_msg or
                    'subdirectory already exists' in error_msg or
                    'directory is not empty' in error_msg):
                    # This is an idempotent case - backup already exists
                    result['changed'] = False
                    result['msg'] = f"Backup already exists at {uri}"
                else:
                    # For other errors, try one more check to see if backup exists
                    try:
                        # Parse the URI to determine if it's a collection with subdirectory
                        path_components = uri.replace('userfile:///', '').replace('s3://', '').replace('gs://', '').split('/')
                        if len(path_components) > 1:
                            # Likely a path with subdirectory
                            scheme = 'userfile://' if uri.startswith('userfile://') else ('s3://' if uri.startswith('s3://') else 'gs://')
                            collection_path = scheme + '/' + path_components[0]
                            subdirectory = '/'.join(path_components[1:])
                            check_cmd = f"SHOW BACKUP FROM '{subdirectory}' IN '{collection_path}'"
                        else:
                            # Fallback for simple paths
                            check_cmd = f"SHOW BACKUPS IN '{uri}'"

                        existing_backup = db.execute_query(check_cmd)
                        if existing_backup and len(existing_backup) > 0:
                            # Backup exists, so this is idempotent
                            result['changed'] = False
                            result['msg'] = f"Backup already exists at {uri}"
                        else:
                            # Re-raise the original error if backup doesn't exist
                            module.fail_json(msg=str(e))
                    except Exception as check_e:
                        # If we can't check, re-raise the original error
                        module.fail_json(msg=f"Backup operation failed: {str(e)}. Check also failed: {str(check_e)}")

        elif operation == 'restore':
            if not database and not table:
                module.fail_json(msg="Either 'database' or 'table' parameter is required for restore operation")

            # Construct RESTORE command
            restore_target = f"DATABASE {database}" if database and not table else f"TABLE {table}"
            target_name = database if database and not table else table.split('.')[-1] if '.' in table else table

            # Check if target already exists - simplified approach for idempotency
            target_exists = False
            restore_needed = True

            try:
                # For database restore, check if database exists
                if database and not table:
                    check_cmd = "SHOW DATABASES"
                    databases = db.execute_query(check_cmd)
                    if databases:
                        for db_row in databases:
                            if db_row[0] == database:
                                target_exists = True
                                break
                # For table restore, check if table exists
                else:
                    # Extract schema and table name
                    schema_name = 'public'
                    table_name = table
                    if '.' in table:
                        parts = table.split('.')
                        if len(parts) == 2:
                            schema_name, table_name = parts

                    check_cmd = f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema_name}' AND table_name = '{table_name}'"
                    tables = db.execute_query(check_cmd)
                    if tables and len(tables) > 0:
                        target_exists = True

                # If the target exists, we don't need to restore
                if target_exists:
                    restore_needed = False
                    result['changed'] = False
                    result['msg'] = f"Target {restore_target} already exists, restore not needed"
                    result['target_exists'] = target_exists

            except Exception as e:
                # If we can't check if target exists, assume we need to restore
                module.warn(f"Failed to check if {restore_target} exists: {str(e)}")
                restore_needed = True

            # Only perform the restore if needed
            if restore_needed:
                # Build WITH options
                with_options = []

                # Add encryption if specified
                if options.get('encryption_passphrase'):
                    with_options.append(f"encryption_passphrase = '{options['encryption_passphrase']}'")

                # Add detached option if specified
                if options.get('detached', False):
                    with_options.append("detached")

                # For database restore, we need to handle the case where we're restoring to a different name
                if database and not table:
                    # First, try to get what's in the backup to determine the original database name
                    try:
                        # Check if the URI is a full backup path or a collection with subdirectory
                        if '/' in uri.replace('userfile:///', '').replace('s3://', '').replace('gs://', ''):
                            # This looks like a full path to a specific backup
                            # Parse the URI to use the new SHOW BACKUP FROM ... IN ... syntax
                            path_components = uri.replace('userfile:///', '').replace('s3://', '').replace('gs://', '').split('/')
                            if len(path_components) > 1:
                                scheme = 'userfile://' if uri.startswith('userfile://') else ('s3://' if uri.startswith('s3://') else 'gs://')
                                subdirectory = path_components[-1]
                                collection_path = scheme + '/' + '/'.join(path_components[:-1])
                                show_backup_cmd = f"SHOW BACKUP FROM '{subdirectory}' IN '{collection_path}'"
                            else:
                                show_backup_cmd = f"SHOW BACKUPS IN '{uri}'"
                        else:
                            # This is a collection path
                            show_backup_cmd = f"SHOW BACKUPS IN '{uri}'"

                        backup_contents = db.execute_query(show_backup_cmd)
                        original_db_name = None

                        if backup_contents:
                            for row in backup_contents:
                                # Find the database entry (object_type = 'database')
                                if len(row) > 3 and row[3] == 'database':
                                    original_db_name = row[2]  # object_name column
                                    break

                        # If restoring to a different name, use new_db_name option
                        if original_db_name and original_db_name != database:
                            with_options.append(f"new_db_name = '{database}'")
                            # Use the original database name in the RESTORE command
                            restore_target = f"DATABASE {original_db_name}"

                    except Exception as e:
                        # If we can't determine the original name, proceed with the specified name
                        module.warn(f"Could not determine original database name from backup: {str(e)}")

                # Construct the restore command with the new syntax: FROM <subdirectory> IN <collection>
                # Parse the URI to use the new FROM ... IN ... syntax required by current CockroachDB versions
                if '/' in uri.replace('userfile:///', '').replace('s3://', '').replace('gs://', ''):
                    # This looks like a full path to a specific backup
                    path_components = uri.replace('userfile:///', '').replace('s3://', '').replace('gs://', '').split('/')
                    if len(path_components) > 1:
                        # Extract the scheme (userfile://, s3://, gs://)
                        scheme = 'userfile://' if uri.startswith('userfile://') else ('s3://' if uri.startswith('s3://') else ('gs://' if uri.startswith('gs://') else ''))
                        # The last component is typically the backup timestamp directory
                        subdirectory = path_components[-1]
                        # Everything before the last component is the collection path
                        collection_path = scheme + '/' + '/'.join(path_components[:-1])
                        cmd_parts = [f"RESTORE {restore_target} FROM '{subdirectory}' IN '{collection_path}'"]
                    else:
                        # Fallback if parsing fails
                        cmd_parts = [f"RESTORE {restore_target} FROM '{uri}'"]
                else:
                    # Simple URI without subdirectory structure - use standard syntax
                    cmd_parts = [f"RESTORE {restore_target} FROM '{uri}'"]

                if with_options:
                    cmd_parts.append(f"WITH {', '.join(with_options)}")

                restore_cmd = " ".join(cmd_parts)

                # Execute the restore command
                response = db.execute_query(restore_cmd)

                if options.get('detached', False) and response:
                    # Extract job ID
                    result['job_id'] = response[0][0]

                result['changed'] = True
            else:
                result['changed'] = False
                result['target_exists'] = target_exists

        elif operation == 'list':
            # List/show backup contents using the new syntax
            try:
                # Parse the URI to determine if it's a collection path or specific backup path
                # Example: 'userfile:///backup-collection/idempotency-test/2025/06/16-202742.43'
                # Should become: collection='userfile:///backup-collection/idempotency-test', subdirectory='2025/06/16-202742.43'

                if '://' in uri:
                    scheme_and_path = uri.split('://', 1)
                    scheme = scheme_and_path[0] + '://'
                    path = scheme_and_path[1]
                else:
                    scheme = ''
                    path = uri

                # Remove leading slashes and split the path
                path = path.lstrip('/')
                path_components = path.split('/')

                if len(path_components) >= 3:  # backup-collection/idempotency-test/2025/06/16-202742.43 format
                    # For nested backup collections, the last component is the backup ID
                    backup_subdirectory = path_components[-1]  # Just the backup ID
                    collection_parts = path_components[:-1]  # Everything except the last part
                    collection_path = scheme + '/' + '/'.join(collection_parts)

                    # Use new syntax: SHOW BACKUP FROM <subdirectory> IN <collection>
                    list_cmd = f"SHOW BACKUP FROM '{backup_subdirectory}' IN '{collection_path}'"
                elif len(path_components) >= 2:  # collection/backup_id format
                    collection_path = scheme + '/' + path_components[0]
                    backup_subdirectory = '/'.join(path_components[1:])
                    list_cmd = f"SHOW BACKUP FROM '{backup_subdirectory}' IN '{collection_path}'"
                else:
                    # Use new backup listing syntax for simple paths
                    list_cmd = f"SHOW BACKUPS IN '{uri}'"

                backup_contents = db.execute_query(list_cmd)
            except Exception as e:
                # If new syntax fails, try an alternative approach
                try:
                    # For the latest CockroachDB versions, we need to adapt our approach
                    if '/' in uri:
                        # Attempt to split the URI into collection and subdirectory
                        scheme = 'userfile://' if uri.startswith('userfile://') else ('s3://' if uri.startswith('s3://') else 'gs://')
                        path = uri.replace('userfile:///', '').replace('s3://', '').replace('gs://', '')
                        path_parts = path.split('/')
                        collection = scheme + '/' + path_parts[0]
                        subdirectory = '/'.join(path_parts[1:])
                        list_cmd = f"SHOW BACKUP FROM '{subdirectory}' IN '{collection}'"
                    else:
                        list_cmd = f"SHOW BACKUPS IN '{uri}'"
                    backup_contents = db.execute_query(list_cmd)
                except Exception as fallback_e:
                    module.fail_json(msg=f"Failed to show backup contents: {str(e)}. Fallback also failed: {str(fallback_e)}")

            # Format the result - this shows the contents of a backup, not a list of backups
            content_list = []
            if backup_contents:
                for content in backup_contents:
                    # SHOW BACKUP returns: database_name, parent_schema_name, object_name, object_type, backup_type, start_time, end_time, size_bytes, rows, is_full_cluster, regions
                    content_item = {
                        'database_name': content[0] if len(content) > 0 and content[0] else None,
                        'parent_schema_name': content[1] if len(content) > 1 and content[1] else None,
                        'object_name': content[2] if len(content) > 2 else None,
                        'object_type': content[3] if len(content) > 3 else None,
                        'backup_type': content[4] if len(content) > 4 else None,
                        'start_time': str(content[5]) if len(content) > 5 and content[5] else None,
                        'end_time': str(content[6]) if len(content) > 6 and content[6] else None,
                        'size_bytes': content[7] if len(content) > 7 and content[7] else None,
                        'rows': content[8] if len(content) > 8 and content[8] else None,
                        'is_full_cluster': content[9] if len(content) > 9 and content[9] else None,
                    }

                    content_list.append(content_item)

            result['backup_contents'] = content_list

    except Exception as e:
        module.fail_json(msg=str(e))
    finally:
        db.close()

    module.exit_json(**result)


if __name__ == '__main__':
    main()
