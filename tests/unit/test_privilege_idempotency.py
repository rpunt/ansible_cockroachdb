#!/usr/bin/env python3

# Small test script to validate the cockroachdb_privilege module
# especially the grant option idempotency fix

import os
import sys
import json

# Add the plugins directory to the Python path
sys.path.insert(0, os.path.abspath('../plugins'))

# Load the module we want to test
from modules.cockroachdb_privilege import main

# Test data for simulation
test_args = {
    'state': 'grant',
    'privileges': ['SELECT'],
    'on_type': 'table',
    'object_name': 'test_table',
    'schema': 'public',
    'database': 'test_db',
    'roles': ['test_user'],
    'with_grant_option': True,
    'host': 'localhost',
    'port': 26257,
    'user': 'root',
    'ssl_mode': 'disable'
}

# Function to create a mock AnsibleModule class
def create_mock_ansible_module():
    class MockAnsibleModule:
        def __init__(self, argument_spec=None, supports_check_mode=False):
            self.params = test_args
            self.check_mode = False
            self.debug_messages = []

        def fail_json(self, **kwargs):
            print("FAIL:", json.dumps(kwargs))
            sys.exit(1)

        def exit_json(self, **kwargs):
            print("SUCCESS:", json.dumps(kwargs))

        def debug(self, msg):
            self.debug_messages.append(msg)
            print("DEBUG:", msg)

    return MockAnsibleModule()

# Function to create mock helper class
def create_mock_helper():
    class MockCockroachDBHelper:
        def __init__(self, module):
            self.module = module

        def execute_query(self, query):
            print(f"QUERY: {query}")
            # Mock responses for different queries
            if "SHOW GRANTS" in query:
                if 'test_table' in query:
                    return [
                        ["database", "test_user", "SELECT", "YES"]  # Already has grant option
                    ]
            return []

        def get_object_privileges(self, on_type, object_name, schema, roles):
            # Return privileges with grant option already set
            return {
                'test_user': [
                    {
                        'privilege': 'SELECT',
                        'grantable': True
                    }
                ]
            }

    return MockCockroachDBHelper(create_mock_ansible_module())

# Run the test
if __name__ == '__main__':
    # Import main function from module
    from modules.cockroachdb_privilege import main

    # Monkey patch the imports in the module
    sys.modules['ansible.module_utils.basic'] = type('MockBasic', (), {
        'AnsibleModule': create_mock_ansible_module
    })

    # Create module instance
    module = create_mock_ansible_module()

    # Call main function with mock objects
    print("=== Running first test with grant option privileges already present ===")
    print("This should be idempotent (not changed)")

    # Monkey patch the helper creation function to return our mock
    from modules.cockroachdb_privilege import CockroachDBHelper
    original_helper = CockroachDBHelper
    def mock_helper_constructor(module):
        return create_mock_helper()

    # Replace the helper constructor with our mock
    modules.cockroachdb_privilege.CockroachDBHelper = mock_helper_constructor

    # Run test
    try:
        main()
    except Exception as e:
        print(f"ERROR: {str(e)}")

    # Restore the original helper constructor
    modules.cockroachdb_privilege.CockroachDBHelper = original_helper
