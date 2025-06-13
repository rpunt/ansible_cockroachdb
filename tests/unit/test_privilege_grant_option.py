#!/usr/bin/env python

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the plugins directory to the path
sys.path.append(os.path.abspath('../../plugins'))

# Import the function we want to test
from modules.cockroachdb_privilege import check_privileges_changes

class TestPrivilegeIdempotency(unittest.TestCase):
    def setUp(self):
        self.module = MagicMock()
        self.helper = MagicMock()

    def test_grant_option_idempotency(self):
        """Test that privileges with grant option are correctly marked as idempotent"""

        # Mock the grant check response to simulate privileges already granted with GRANT OPTION
        self.helper.execute_query.return_value = [
            ["TABLE", "test_user", "SELECT", "YES"]  # Grantable is YES
        ]

        # Set up a fake current privilege structure with grant option
        self.helper.get_object_privileges.return_value = {
            'test_user': [
                {
                    'privilege': 'SELECT',
                    'grantable': True  # Already has grant option
                }
            ]
        }

        # Call the function with grant option requested
        changes_needed, _ = check_privileges_changes(
            self.module,
            self.helper,
            'grant',
            'table',
            'test_table',
            'public',
            ['test_user'],
            ['SELECT'],
            True  # with_grant_option=True
        )

        # Should be idempotent (no changes needed)
        self.assertFalse(changes_needed, "Grant option idempotency check failed - changes marked as needed when should be idempotent")

if __name__ == '__main__':
    unittest.main()
