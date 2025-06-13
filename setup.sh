#!/bin/bash

# Setup script for CockroachDB Ansible modules

# Check if pip is installed
if ! command -v pip &> /dev/null
then
    echo "pip could not be found, installing..."
    curl -O https://bootstrap.pypa.io/get-pip.py
    python3 get-pip.py --user
fi

# Install required dependencies
echo "Installing required dependencies..."
pip install psycopg2-binary --user

# Clean up any previous ansible_collections build directory
echo "Cleaning up previous builds..."
rm -rf ansible_collections

# Create a symbolic link to the module directory in Ansible's module path
ANSIBLE_MODULE_DIR="$HOME/.ansible/plugins/modules"
mkdir -p "$ANSIBLE_MODULE_DIR"

echo "Creating symbolic links for modules..."
ln -sf "$(pwd)/plugins/modules/cockroachdb_db.py" "$ANSIBLE_MODULE_DIR/"
ln -sf "$(pwd)/plugins/modules/cockroachdb_user.py" "$ANSIBLE_MODULE_DIR/"
ln -sf "$(pwd)/plugins/modules/cockroachdb_table.py" "$ANSIBLE_MODULE_DIR/"
ln -sf "$(pwd)/plugins/modules/cockroachdb_index.py" "$ANSIBLE_MODULE_DIR/"
ln -sf "$(pwd)/plugins/modules/cockroachdb_info.py" "$ANSIBLE_MODULE_DIR/"
ln -sf "$(pwd)/plugins/modules/cockroachdb_backup.py" "$ANSIBLE_MODULE_DIR/"
ln -sf "$(pwd)/plugins/modules/cockroachdb_query.py" "$ANSIBLE_MODULE_DIR/"
ln -sf "$(pwd)/plugins/modules/cockroachdb_parameter.py" "$ANSIBLE_MODULE_DIR/"
ln -sf "$(pwd)/plugins/modules/cockroachdb_privilege.py" "$ANSIBLE_MODULE_DIR/"
ln -sf "$(pwd)/plugins/modules/cockroachdb_statistics.py" "$ANSIBLE_MODULE_DIR/"
ln -sf "$(pwd)/plugins/modules/cockroachdb_maintenance.py" "$ANSIBLE_MODULE_DIR/"

# Create a symbolic link to the module_utils directory in Ansible's module_utils path
ANSIBLE_MODULE_UTILS_DIR="$HOME/.ansible/plugins/module_utils"
mkdir -p "$ANSIBLE_MODULE_UTILS_DIR"

echo "Creating symbolic links for module utilities..."
ln -sf "$(pwd)/plugins/module_utils/cockroachdb.py" "$ANSIBLE_MODULE_UTILS_DIR/"

echo "Setup complete!"
echo "You can now use the CockroachDB modules in your Ansible playbooks."
