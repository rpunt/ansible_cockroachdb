#!/usr/bin/python
# -*- coding: utf-8 -*-
# pylint: disable=line-too-long, broad-exception-caught

# Copyright: (c) 2025, Cockroach Labs
# Apache License, Version 2.0 (see LICENSE or http://www.apache.org/licenses/LICENSE-2.0)

"""
Ansible module for managing CockroachDB databases.

This module handles the creation and removal of databases in a CockroachDB cluster.
It provides idempotent database management, ensuring that databases exist or don't
exist as required by your playbooks.

Key features:
- Create new databases with optional owner assignment
- Remove existing databases when no longer needed
- Verify database existence without making changes

The module connects to CockroachDB using the PostgreSQL wire protocol and
can utilize SSL certificates for secure connections.

For full documentation, see the plugins/docs/cockroachdb_db.yml file
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.rpunt.cockroachdb.plugins.module_utils.cockroachdb import (
    CockroachDBHelper,
)

ANSIBLE_METADATA = {
    "metadata_version": "1.1",
    "status": ["preview"],
    "supported_by": "cockroach_labs",
}

DOCUMENTATION = r"""
---
module: cockroachdb_db
short_description: Manage CockroachDB databases
description:
  - Create, drop, or manage CockroachDB databases
options:
  name:
    description:
      - Name of the database to create or remove
    required: true
    type: str
  state:
    description:
      - The database state
    default: present
    choices: ["present", "absent"]
    type: str
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
  owner:
    description:
      - Name of the role to set as owner of the database
    type: str
requirements:
  - psycopg2
author:
  - "Ryan Punt (@rpunt)"
"""

EXAMPLES = r"""
# Create a new CockroachDB database
- name: Create a new database
  cockroachdb_db:
    name: mydatabase
    state: present
    host: localhost
    port: 26257
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt

# Drop a database
- name: Drop database
  cockroachdb_db:
    name: mydatabase
    state: absent
    host: localhost
    user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt
"""

RETURN = r"""
name:
  description: Name of the database
  returned: always
  type: str
  sample: "mydatabase"
state:
  description: The new state of the database
  returned: always
  type: str
  sample: "present"
changed:
  description: Whether the database was changed
  returned: always
  type: bool
  sample: true
"""

def main():
    """
    Main entry point for the CockroachDB database management module.

    This function handles the creation and deletion of CockroachDB databases.
    It processes module parameters, validates inputs, connects to the cluster,
    and performs the requested database operations in an idempotent manner.

    Operations:
    - Create a new database if it doesn't exist (state=present)
    - Set database ownership when creating a new database
    - Drop an existing database if it exists (state=absent)
    - Check database existence without making changes (check_mode)

    The function handles idempotent operations by checking if the database exists
    before attempting to create or drop it, ensuring no unnecessary operations
    are performed.

    Returns:
        dict: Result object containing operation status and database details
              including the 'changed' status flag
    """
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', default='present', choices=['present', 'absent']),
        host=dict(type='str', default='localhost'),
        port=dict(type='int', default=26257),
        user=dict(type='str', default='root'),
        password=dict(type='str', no_log=True),
        database=dict(type='str', default='defaultdb'),
        ssl_mode=dict(type='str', default='verify-full', choices=['disable', 'allow', 'prefer', 'require', 'verify-ca', 'verify-full']),
        ssl_cert=dict(type='path'),
        ssl_key=dict(type='path'),
        ssl_rootcert=dict(type='path'),
        owner=dict(type='str'),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    name = module.params['name']
    state = module.params['state']
    owner = module.params['owner']

    db = CockroachDBHelper(module)

    changed = False
    result = {
        'changed': False,
        'database': name,
        'state': state
    }

    try:
        db_exists = db.database_exists(name)

        if module.check_mode:
            if state == 'present' and not db_exists:
                result['changed'] = True
            elif state == 'absent' and db_exists:
                result['changed'] = True
            module.exit_json(**result)

        if state == 'present':
            if not db_exists:
                db.create_database(name)
                changed = True
                result['changed'] = True

            # Set owner if provided
            if owner and changed:
                if db.role_exists(owner):
                    db.execute_query(f"ALTER DATABASE {name} OWNER TO {owner}")
                else:
                    module.fail_json(msg=f"Role {owner} does not exist")

        elif state == 'absent':
            if db_exists:
                db.drop_database(name)
                changed = True
                result['changed'] = True

    except Exception as e:
        module.fail_json(msg=str(e))
    finally:
        db.close()

    module.exit_json(**result)


if __name__ == '__main__':
    main()
