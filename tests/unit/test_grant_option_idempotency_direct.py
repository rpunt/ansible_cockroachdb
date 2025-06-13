#!/usr/bin/env python3

# Add a debug statement in the privilge module to see how the grant option idempotency check works
import sys
import os
from unittest.mock import patch, MagicMock
import json

# Mock the AnsibleModule class
class MockAnsibleModule:
    def __init__(self, **kwargs):
        self.params = {
            'state': 'grant',
            'privileges': ['SELECT'],
            'on_type': 'table',
            'object_name': 'test_priv_table',
            'schema': 'public',
            'database': 'test_db',
            'roles': ['test_user'],
            'with_grant_option': True,
            'host': 'localhost',
            'port': 26257,
            'user': 'root',
            'password': None,
            'ssl_mode': 'disable',
            'ssl_cert': None,
            'ssl_key': None,
            'ssl_rootcert': None,
            'connect_timeout': 30,
            'cascade': False
        }
        self.check_mode = False
        self.debug_messages = []

    def debug(self, msg):
        self.debug_messages.append(msg)
        print(f"DEBUG: {msg}")

    def exit_json(self, **kwargs):
        print(f"EXIT: {json.dumps(kwargs)}")
        sys.exit(0)

    def fail_json(self, **kwargs):
        print(f"FAIL: {json.dumps(kwargs)}")
        sys.exit(1)

# Mock the helper class
class MockHelper:
    def __init__(self, module):
        self.module = module

    def execute_query(self, query):
        print(f"QUERY: {query}")
        if "SHOW GRANTS" in query and "TABLE public.test_priv_table" in query:
            # Return a result that indicates the privilege is already granted with GRANT OPTION
            return [
                ["TABLE", "test_user", "SELECT", "YES"]
            ]
        return []

    def get_object_privileges(self, on_type, object_name, schema, roles=None):
        # Return privileges with grant option
        return {
            'test_user': [
                {
                    'privilege': 'SELECT',
                    'grantable': True  # Already has grant option
                }
            ]
        }

# Test the check_privileges_changes function
def test():
    # Import the module function to test
    sys.path.insert(0, os.path.abspath('../../plugins'))
    from modules.cockroachdb_privilege import check_privileges_changes

    # Create a mock module
    module = MockAnsibleModule()

    # Create a mock helper
    helper = MockHelper(module)

    # Call the function
    changes_needed, current_privileges = check_privileges_changes(
        module,
        helper,
        'grant',
        'table',
        'test_priv_table',
        'public',
        ['test_user'],
        ['SELECT'],
        True  # with_grant_option
    )

    # Print the result
    print("\n--- TEST RESULTS ---")
    print(f"Changes needed: {changes_needed}")
    print(f"Current privileges: {current_privileges}")
    print("\nDebug messages:")
    for msg in module.debug_messages:
        print(f"  {msg}")

    # Print the test verdict
    if not changes_needed:
        print("\nTEST PASSED: No changes needed - grant option idempotency works correctly!")
    else:
        print("\nTEST FAILED: Changes needed when they shouldn't be - grant option idempotency not working!")

    return changes_needed

if __name__ == "__main__":
    test()
