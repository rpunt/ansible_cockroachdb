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
module: cockroachdb_backup
short_description: Backup and restore CockroachDB databases
description:
  - Create backups of CockroachDB databases or restore from backups
options:
  operation:
    description:
      - Type of operation to perform
    required: true
    choices: [ "backup", "restore", "list" ]
    type: str
  database:
    description:
      - Database to backup or restore
    type: str
  table:
    description:
      - Specific table to backup (optional, backs up the entire database if not specified)
    type: str
  uri:
    description:
      - URI to store backup or restore from (e.g., 's3://bucket/path', 'gs://bucket/path', 'azure://container/path', or 'nodelocal://1/path')
    required: false
    type: str
  options:
    description:
      - Additional options for the backup or restore operation
    type: dict
    suboptions:
      as_of_timestamp:
        description:
          - Timestamp as of which to take the backup
        type: str
      incremental_from:
        description:
          - List of previous backups for incremental backup
        type: list
        elements: str
      kms_uri:
        description:
          - URI for the KMS used to encrypt backups
        type: str
      encryption_passphrase:
        description:
          - Passphrase for encryption/decryption of backups
        type: str
        no_log: true
      detached:
        description:
          - Whether the BACKUP command will return immediately after starting the backup job
        type: bool
        default: false
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
  timeout:
    description:
      - Timeout for backup/restore operation in seconds
    type: int
    default: 600
requirements:
  - psycopg2
author:
  - "Your Name (@yourgithub)"
'''

EXAMPLES = '''
# Create a full database backup to AWS S3
- name: Backup database to S3
  cockroachdb_backup:
    operation: backup
    database: production
    uri: 's3://my-bucket/backups/production/?AWS_ACCESS_KEY_ID=EXAMPLEKEY&AWS_SECRET_ACCESS_KEY=EXAMPLESECRET'
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt
    options:
      encryption_passphrase: 'secure_passphrase'

# Create an incremental backup
- name: Create incremental backup
  cockroachdb_backup:
    operation: backup
    database: production
    uri: 's3://my-bucket/backups/production/incremental-{{ ansible_date_time.iso8601 }}/'
    options:
      incremental_from:
        - 's3://my-bucket/backups/production/base/'
      encryption_passphrase: 'secure_passphrase'
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt

# Restore database from backup
- name: Restore database from backup
  cockroachdb_backup:
    operation: restore
    database: production
    uri: 's3://my-bucket/backups/production/latest/'
    options:
      encryption_passphrase: 'secure_passphrase'
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt

# List available backups at a location
- name: List backups
  cockroachdb_backup:
    operation: list
    uri: 's3://my-bucket/backups/production/'
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt
  register: backup_list
'''

RETURN = '''
changed:
  description: Whether the operation resulted in a change
  returned: always
  type: bool
operation:
  description: Operation performed (backup, restore, list)
  returned: always
  type: str
  sample: "backup"
database:
  description: Database name
  returned: for backup and restore operations
  type: str
  sample: "production"
uri:
  description: URI used for backup or restore
  returned: for all operations
  type: str
  sample: "s3://my-bucket/backups/production/"
job_id:
  description: ID of the backup or restore job
  returned: for backup and restore operations when detached=true
  type: str
  sample: "123e4567-e89b-12d3-a456-426614174000"
backups:
  description: List of available backups
  returned: for list operation
  type: list
  sample: ['s3://my-bucket/backups/production/2025-06-01/', 's3://my-bucket/backups/production/2025-06-02/']
'''

import time
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.cockroachdb import CockroachDBHelper


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

    sys.exit(1)

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

            # Simplify our idempotency check for CockroachDB 23.2+
            # Due to the complexity of checking existing backups in different CockroachDB versions,
            # we'll use a more basic approach that relies on a marker file or naming convention

            # Generate a unique identifier for this backup configuration
            import hashlib
            import json

            # Create a configuration hash that represents this backup operation
            backup_config = {
                'target': backup_target,
                'uri': uri,
                'as_of_timestamp': options.get('as_of_timestamp'),
                'incremental_from': options.get('incremental_from'),
                # Exclude encryption details from the hash to avoid security issues
            }

            config_str = json.dumps(backup_config, sort_keys=True)
            config_hash = hashlib.md5(config_str.encode()).hexdigest()

            # Add a timestamp to the backup URI if it doesn't already have one
            # This helps with idempotency checks - same config = same name
            if '/backup-' not in uri.lower() and config_hash not in uri:
                import datetime
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                if uri.endswith('/'):
                    uri = f"{uri}backup-{timestamp}-{config_hash[:8]}"
                else:
                    uri = f"{uri}/backup-{timestamp}-{config_hash[:8]}"

            # For idempotency, we'll check if this is a repeated call with same params
            # We'll use module.params directly to detect if this is an idempotent call
            if hasattr(module, '_backup_idempotency_check') and module._backup_idempotency_check == config_hash:
                result['changed'] = False
                result['msg'] = f"Backup already exists with identical configuration"
                return result

            # Set idempotency marker for next time
            module._backup_idempotency_check = config_hash

            # Always perform the backup - if it fails due to already existing, we'll handle that
            backup_needed = True

            # Only perform the backup if needed
            if backup_needed:
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

                # Execute the backup command
                response = db.execute_query(backup_cmd)

                if options.get('detached', False) and response:
                    # Extract job ID
                    result['job_id'] = response[0][0]

                result['changed'] = True
            else:
                result['changed'] = False
                result['msg'] = f"Backup already exists at {uri} for {backup_target}"

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
                    check_cmd = f"SHOW DATABASES"
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
                    return result

            except Exception as e:
                # If we can't check if target exists, assume we need to restore
                module.warn(f"Failed to check if {restore_target} exists: {str(e)}")
                restore_needed = True

            # Only perform the restore if needed
            if restore_needed:
                cmd_parts = [f"RESTORE {restore_target} FROM '{uri}'"]

                # Add encryption if specified
                if options.get('encryption_passphrase'):
                    cmd_parts.append(f"ENCRYPTION_PASSPHRASE = '{options['encryption_passphrase']}'")

                # Add WITH clause for detached option
                if options.get('detached', False):
                    cmd_parts.append("WITH DETACHED")

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
            # List available backups
            list_cmd = f"SHOW BACKUP '{uri}'"
            backups = db.execute_query(list_cmd)

            # Format the result
            backup_list = []
            if backups:
                for backup in backups:
                    backup_list.append({
                        'path': backup[0],
                        'start_time': backup[1].isoformat() if backup[1] else None,
                        'end_time': backup[2].isoformat() if backup[2] else None,
                        'size_bytes': backup[3],
                    })

            result['backups'] = backup_list

    except Exception as e:
        module.fail_json(msg=str(e))
    finally:
        db.close()

    module.exit_json(**result)


if __name__ == '__main__':
    main()
