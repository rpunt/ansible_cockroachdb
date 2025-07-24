#!/usr/bin/python3

# Copyright: (c) 2025, Cockroach Labs
# Apache License, Version 2.0 (see LICENSE or http://www.apache.org/licenses/LICENSE-2.0)

"""
Ansible module for installing CockroachDB.

This module handles downloading and installing CockroachDB binaries from
official repositories or custom URLs. It supports various installation options
and manages file permissions and dependencies.

The documentation for this module is maintained in the plugins/docs/cockroachdb_install.yml file.
"""

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
import sys
import tempfile
import glob
import shutil
import subprocess
import traceback
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_native

ANSIBLE_METADATA = {
    "metadata_version": "1.1",
    "status": ["preview"],
    "supported_by": "cockroach_labs",
}

DOCUMENTATION = r'''
---
module: cockroachdb_install

short_description: Install CockroachDB binary

version_added: "1.0.0"

description:
    - This module installs CockroachDB binary from official repositories or custom URL.
    - Supports standard releases, master versions and custom binaries.
    - Handles architecture detection and appropriate binary selection.
    - Manages GIS libraries when available.

options:
    version:
        description:
            - Version of CockroachDB to install.
            - Use "master" for the latest development version.
            - Use "custom" for installing from a custom URL.
        required: true
        type: str
    bin_prefix:
        description:
            - Prefix for binary filename.
        required: false
        type: str
        default: "cockroach-"
    repo_url:
        description:
            - URL of the repository from which to download CockroachDB.
        required: false
        type: str
        default: "https://binaries.cockroachdb.com"
    custom_url:
        description:
            - URL to download a custom binary from.
            - Only used when version is set to "custom".
        required: false
        type: str
    force:
        description:
            - Force reinstallation even if binary already exists.
        required: false
        type: bool
        default: false

author:
    - Cockroach Labs (@cockroachdb)
'''

EXAMPLES = r'''
# Install CockroachDB version 22.2.0
- name: Install CockroachDB
  cockroachdb_install:
    version: "22.2.0"

# Install latest master version
- name: Install CockroachDB master
  cockroachdb_install:
    version: "master"

# Install from custom URL
- name: Install custom CockroachDB
  cockroachdb_install:
    version: "custom"
    custom_url: "https://example.com/path/to/cockroach.tgz"

# Force reinstallation of CockroachDB
- name: Force reinstall CockroachDB
  cockroachdb_install:
    version: "22.2.0"
    force: true
'''

RETURN = r'''
version:
    description: The version of CockroachDB that was installed
    type: str
    returned: always
    sample: "22.2.0"
binary_path:
    description: Path where the binary was installed
    type: str
    returned: always
    sample: "/usr/local/bin/cockroach"
architecture:
    description: The architecture for which the binary was installed
    type: str
    returned: always
    sample: "amd64"
installation_type:
    description: The type of installation performed
    type: str
    returned: always
    sample: "regular"
'''

def run_command(module, cmd, cwd=None, check=True):
    """
    Helper function to run commands with proper error handling

    Args:
        module: The AnsibleModule instance
        cmd: List of command arguments
        cwd: Current working directory for the command
        check: Whether to check return code

    Returns:
        subprocess.CompletedProcess object with stdout and stderr
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        return result
    except subprocess.CalledProcessError as e:
        module.fail_json(
            msg=f"Command failed: {' '.join(cmd)}",
            stdout=e.stdout,
            stderr=e.stderr,
            rc=e.returncode
        )
    except Exception as e:
        module.fail_json(msg=f"Error executing command {' '.join(cmd)}: {to_native(e)}")


def get_architecture(module):
    """Detect system architecture and return compatible CockroachDB arch"""
    # Map system architecture to CockroachDB architecture names
    arch_mapping = {
        'aarch64': 'arm64',
        'x86_64': 'amd64'
    }

    try:
        arch_result = run_command(module, ['uname', '-m'])
        arch_output = arch_result.stdout.strip()

        if arch_output not in arch_mapping:
            module.fail_json(msg=f"Unsupported architecture: {arch_output}")

        return arch_mapping[arch_output]
    except Exception as e:
        module.fail_json(msg=f"Error detecting architecture: {to_native(e)}")


def is_already_installed(module, version):
    """
    Check if the specified version is already installed

    Args:
        module: AnsibleModule instance
        version: Version to check for

    Returns:
        bool: True if the version is already installed, False otherwise
    """
    binary_path = '/usr/local/bin/cockroach'

    if not os.path.exists(binary_path):
        module.debug(f"CockroachDB binary not found at {binary_path}")
        return False

    if version == "master" or version == "custom":
        # Always reinstall master or custom versions unless we add version detection
        module.debug(f"Version is '{version}', forcing reinstall")
        return False

    try:
        module.debug(f"Checking installed CockroachDB version")
        version_result = run_command(
            module,
            [binary_path, 'version'],
            check=False
        )

        if version_result.returncode != 0:
            module.debug(f"Failed to get version info: {version_result.stderr}")
            return False

        installed = version in version_result.stdout

        if installed:
            module.debug(f"Found version {version} already installed")
        else:
            module.debug(f"Version {version} not found in: {version_result.stdout.strip()}")

        return installed
    except Exception as e:
        module.debug(f"Error checking version: {to_native(e)}")
        return False


def install_binary(module, src_path, dest_path='/usr/local/bin/cockroach'):
    """Copy and set executable permissions on binary"""
    try:
        shutil.copy2(src_path, dest_path)
        os.chmod(dest_path, 0o755)
    except Exception as e:
        module.fail_json(msg=f"Error installing binary: {to_native(e)}")


def download_file(module, url, output_path=None):
    """Download a file from URL with proper error handling"""
    cmd = ['wget', '-q']
    if output_path:
        cmd.extend(['-O', output_path])
    cmd.append(url)

    run_command(module, cmd)

    if output_path and not os.path.exists(output_path):
        module.fail_json(msg=f"Failed to download file from {url}")


def extract_tarball(module, tarball_path, extract_dir=None):
    """Extract a tarball to the specified directory"""
    cmd = ['tar', 'xf', tarball_path]
    if extract_dir:
        cmd.extend(['-C', extract_dir])

    run_command(module, cmd)


def find_and_install_from_directory(module, search_pattern, result):
    """
    Find a cockroach binary and install it along with GIS libraries

    This function searches for directories matching the pattern, then looks for
    the cockroach binary within those directories and installs it.
    It also attempts to install GIS libraries if they exist.

    Args:
        module: AnsibleModule instance
        search_pattern: Glob pattern to find directories containing cockroach
        result: Result dictionary to update

    Returns:
        bool: True if installation was successful, False otherwise
    """
    # Find directories matching the pattern
    dirs = glob.glob(search_pattern)
    if not dirs:
        module.debug(f"No directories found matching pattern: {search_pattern}")
        return False

    # Get the first matching directory
    cockroach_dir = dirs[0]
    module.debug(f"Found directory: {cockroach_dir}")

    # Check for binary
    binary_path = os.path.join(cockroach_dir, 'cockroach')
    if not os.path.exists(binary_path):
        module.debug(f"Binary not found at: {binary_path}")
        return False

    # Install binary
    install_binary(module, binary_path)
    module.debug(f"Successfully installed binary from: {binary_path}")

    # Try to copy GIS libraries if they exist
    try:
        lib_path = os.path.join(cockroach_dir, 'lib')
        if os.path.exists(lib_path):
            copy_gis_libraries(module, lib_path)
            module.debug("Installed GIS libraries")
        else:
            module.debug(f"No lib directory found at: {lib_path}")
    except Exception as e:
        module.warn(f"Could not copy GIS libraries: {to_native(e)}")

    result['changed'] = True
    return True


def install_cockroachdb(module, version, bin_prefix, repo_url, custom_url, arch, result):
    """
    Central installer function that handles all installation types
    """
    # Create directory for cockroach GIS libraries if it doesn't exist
    os.makedirs('/usr/local/lib/cockroach', exist_ok=True)

    # Handle installation based on version type
    if version == "master":
        result['installation_type'] = 'master'
        tarball_url = f"https://edge-binaries.cockroachdb.com/cockroach/cockroach.linux-gnu-{arch}.LATEST.tgz"
        fallback_url = f"https://edge-binaries.cockroachdb.com/cockroach/cockroach.linux-gnu-{arch}.LATEST"
        fallback_binary_name = f"cockroach.linux-gnu-{arch}.LATEST"

        install_from_url(module, tarball_url, result, fallback_url, fallback_binary_name)

    elif version == "custom":
        result['installation_type'] = 'custom'
        if not custom_url:
            module.fail_json(msg="custom_url is required when version='custom'")

        install_from_url(module, custom_url, result)

    else:
        result['installation_type'] = 'regular'
        tarball_name = f"{bin_prefix}{version}.linux-{arch}.tgz"
        download_url = f"{repo_url}/{tarball_name}"

        install_from_url(module, download_url, result)


def install_from_url(module, url, result, fallback_url=None, fallback_binary_name=None):
    """
    Generic installer that downloads from URL and installs CockroachDB

    Args:
        module: AnsibleModule instance
        url: URL to download from (should be a tarball)
        result: Result dictionary to update
        fallback_url: Optional URL to try if tarball approach fails
        fallback_binary_name: Name of binary file if using fallback URL
    """
    # Use Python's context manager for temporary directory
    with tempfile.TemporaryDirectory() as extract_dir:
        current_dir = os.getcwd()

        try:
            os.chdir(extract_dir)

            # Try installing from tarball URL first
            if _try_install_from_tarball(module, url, result):
                return

            # If tarball approach failed and we have a fallback URL, try direct binary download
            if fallback_url and _try_install_direct_binary(module, fallback_url, fallback_binary_name, result):
                return

            # If we reached here, all installation methods failed
            module.fail_json(msg=f"Failed to download and install CockroachDB from {url}")
        finally:
            os.chdir(current_dir)


def _try_install_from_tarball(module, url, result):
    """Helper function to attempt installation from a tarball URL"""
    try:
        # Download the tarball
        download_file(module, url)

        # Find and extract the tarball
        tarballs = glob.glob('*.t*z*')
        if not tarballs:
            return False

        extract_tarball(module, tarballs[0])

        # Try to find and install from extracted directory
        if find_and_install_from_directory(module, 'cockroach*', result):
            return True

        # If not found in cockroach* directories, try a recursive search
        binaries = glob.glob('**/cockroach', recursive=True)
        if binaries:
            install_binary(module, binaries[0])
            result['changed'] = True
            return True

        return False
    except Exception as e:
        module.warn(f"Tarball installation failed: {to_native(e)}")
        return False


def _try_install_direct_binary(module, url, binary_name, result):
    """Helper function to attempt installation from a direct binary URL"""
    try:
        download_file(module, url)

        binary_path = binary_name or os.path.basename(url)
        if os.path.exists(binary_path):
            install_binary(module, binary_path)
            result['changed'] = True
            return True

        return False
    except Exception as e:
        module.warn(f"Direct binary installation failed: {to_native(e)}")
        return False


def copy_gis_libraries(module, lib_path):
    """Copy GIS libraries from the extracted package to the system"""
    dest_dir = '/usr/local/lib/cockroach'

    # Ensure destination directory exists
    os.makedirs(dest_dir, exist_ok=True)

    # Copy libgeos.so if it exists
    if os.path.exists(os.path.join(lib_path, 'libgeos.so')):
        shutil.copy2(os.path.join(lib_path, 'libgeos.so'),
                     os.path.join(dest_dir, 'libgeos.so'))

    # Copy libgeos_c.so if it exists
    if os.path.exists(os.path.join(lib_path, 'libgeos_c.so')):
        shutil.copy2(os.path.join(lib_path, 'libgeos_c.so'),
                     os.path.join(dest_dir, 'libgeos_c.so'))


def main():
    """
    Main function for the Ansible module
    """
    # Define the available parameters for this module
    module_args = dict(
        version=dict(type='str', required=True),
        bin_prefix=dict(type='str', required=False, default='cockroach-'),
        repo_url=dict(type='str', required=False, default='https://binaries.cockroachdb.com'),
        custom_url=dict(type='str', required=False),
        force=dict(type='bool', required=False, default=False)
    )

    # Define the result dictionary
    result = dict(
        changed=False,
        version='',
        binary_path='/usr/local/bin/cockroach',
        architecture='',
        installation_type=''
    )

    # Create an AnsibleModule object
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    try:
        # Get module parameters
        version = module.params['version']
        bin_prefix = module.params['bin_prefix']
        repo_url = module.params['repo_url']
        custom_url = module.params['custom_url']
        force = module.params['force']

        # Set result version
        result['version'] = version

        # Get system architecture
        arch = get_architecture(module)
        result['architecture'] = arch

        # Check if already installed and not forced
        if not force and is_already_installed(module, version):
            module.exit_json(**result)

        # Check if we are in check mode
        if module.check_mode:
            module.exit_json(**result)

        # Install CockroachDB
        install_cockroachdb(module, version, bin_prefix, repo_url, custom_url, arch, result)

    except Exception as e:
        module.fail_json(
            msg=f"Error installing CockroachDB: {to_native(e)}",
            exception=traceback.format_exc(),
            **result
        )

    # Return the result
    module.exit_json(**result)


if __name__ == '__main__':
    main()
