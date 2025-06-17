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


def main():
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
