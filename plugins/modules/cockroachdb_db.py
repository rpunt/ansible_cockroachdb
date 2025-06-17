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
from ansible.module_utils.cockroachdb import CockroachDBHelper

ANSIBLE_METADATA = {
    "metadata_version": "1.1",
    "status": ["preview"],
    "supported_by": "cockroach_labs",
}

def main():
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
