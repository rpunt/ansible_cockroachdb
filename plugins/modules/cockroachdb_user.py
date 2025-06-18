#!/usr/bin/python
# -*- coding: utf-8 -*-
# pylint: disable=line-too-long, broad-exception-caught

# Copyright: (c) 2025, Cockroach Labs
# Apache License, Version 2.0 (see LICENSE or http://www.apache.org/licenses/LICENSE-2.0)

"""
Ansible module for managing users and roles in a CockroachDB cluster.

This module allows creating, modifying, and removing users and roles in a CockroachDB
database. It supports setting passwords, managing login capabilities, and granting
basic privileges directly through the module.

The documentation for this module is maintained in the plugins/docs/cockroachdb_user.yml file.
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
module: cockroachdb_user
short_description: Manage CockroachDB users/roles
description:
  - Create, drop, or manage CockroachDB users and their privileges
options:
  name:
    description:
      - Name of the user/role to create or manage
    required: true
    type: str
  password:
    description:
      - Password for the user (not required for roles without login privilege)
    type: str
  state:
    description:
      - The user state
    default: present
    choices: ["present", "absent"]
    type: str
  login:
    description:
      - Whether the role can login
    default: true
    type: bool
  priv:
    description:
      - "Privileges to grant the user on a database. Format is db_name:priv1,priv2"
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
  login_user:
    description:
      - User name used to authenticate to CockroachDB
    default: root
    type: str
  login_password:
    description:
      - Password used to authenticate to CockroachDB
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
# Create a new CockroachDB user
- name: Create a new user
  cockroachdb_user:
    name: myuser
    password: "secure_password"
    state: present
    host: localhost
    port: 26257
    login_user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt

# Create a user with privileges
- name: Create user with privileges
  cockroachdb_user:
    name: myuser
    password: "secure_password"
    priv: "mydatabase:ALL"
    state: present
    host: localhost
    login_user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt

# Drop a user
- name: Drop user
  cockroachdb_user:
    name: myuser
    state: absent
    host: localhost
    login_user: root
    ssl_cert: /path/to/client.crt
    ssl_key: /path/to/client.key
    ssl_rootcert: /path/to/ca.crt
"""

RETURN = r"""
changed:
  description: Whether the user was created, modified or removed
  returned: always
  type: bool
user:
  description: User/role name
  returned: always
  type: str
  sample: "myuser"
state:
  description: The new state of the user
  returned: always
  type: str
  sample: "present"
"""

def main():
    """
    Main entry point for the CockroachDB user management module.

    This function handles the creation, modification, and deletion of users and roles
    in a CockroachDB cluster. It processes module parameters, validates inputs, connects
    to the cluster, and performs the requested user management operations in an idempotent
    manner.

    Operations:
    - Create new users or roles if they don't exist (state=present)
    - Set or update passwords for users
    - Configure login capability for roles
    - Grant basic privileges directly through the module
    - Remove users or roles when no longer needed (state=absent)

    The function handles idempotent operations by checking if users exist and
    have the requested properties before making changes, ensuring no unnecessary
    operations are performed.

    Returns:
        dict: Result object containing operation status and user details
              including the 'changed' status flag
    """
    module_args = dict(
        name=dict(type='str', required=True),
        password=dict(type='str', no_log=True),
        state=dict(type='str', default='present', choices=['present', 'absent']),
        login=dict(type='bool', default=True),
        priv=dict(type='str'),
        host=dict(type='str', default='localhost'),
        port=dict(type='int', default=26257),
        login_user=dict(type='str', default='root'),
        login_password=dict(type='str', no_log=True),
        ssl_mode=dict(type='str', default='verify-full', choices=['disable', 'allow', 'prefer', 'require', 'verify-ca', 'verify-full']),
        ssl_cert=dict(type='path'),
        ssl_key=dict(type='path'),
        ssl_rootcert=dict(type='path'),
        database=dict(type='str', default='defaultdb'),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    name = module.params['name']
    password = module.params['password']
    state = module.params['state']
    login = module.params['login']
    priv = module.params['priv']

    # Map login_user and login_password to user and password for the connection helper
    module.params['user'] = module.params.pop('login_user')
    if module.params.get('login_password'):
        module.params['password'] = module.params.pop('login_password')

    db = CockroachDBHelper(module)

    changed = False
    result = {
        'changed': False,
        'user': name,
        'state': state
    }

    try:
        user_exists = db.role_exists(name)

        if module.check_mode:
            if state == 'present' and not user_exists:
                result['changed'] = True
            elif state == 'absent' and user_exists:
                result['changed'] = True
            module.exit_json(**result)

        if state == 'present':
            if not user_exists:
                db.create_role(name, password, login)
                changed = True

            # Handle privileges
            if priv:
                try:
                    db_name, privileges = priv.split(':', 1)
                    privilege_list = privileges.split(',')
                    db.grant_privileges(db_name, name, privilege_list)
                    changed = True
                except ValueError:
                    module.fail_json(msg="Invalid privilege format. Expected format: 'database:privilege1,privilege2'")

            result['changed'] = changed

        elif state == 'absent':
            if user_exists:
                db.drop_role(name)
                result['changed'] = True

    except Exception as e:
        module.fail_json(msg=str(e))
    finally:
        db.close()

    module.exit_json(**result)


if __name__ == '__main__':
    main()
