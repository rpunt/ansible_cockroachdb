#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest
import sys
import os
import tempfile
import shutil
import glob
from unittest.mock import patch, MagicMock, call

# Add the plugins directory to the path
sys.path.insert(0, 'plugins/modules')
sys.path.insert(0, 'plugins/module_utils')

# Import the module functions to test
from cockroachdb_install import (
    get_architecture,
    is_already_installed,
    install_binary,
    download_file,
    extract_tarball,
    find_and_install_from_directory,
    _try_install_from_tarball,
    _try_install_direct_binary,
    copy_gis_libraries,
    install_from_url,
    install_cockroachdb
)


class TestCockroachDBInstallModule:
    """Test cases for the CockroachDB install module"""

    @pytest.fixture
    def mock_module(self):
        """Fixture to create a mock AnsibleModule instance"""
        mock_module = MagicMock()
        mock_module.params = {
            'version': '22.2.0',
            'bin_prefix': 'cockroach-',
            'repo_url': 'https://binaries.cockroachdb.com',
            'custom_url': None,
            'force': False
        }
        mock_module.debug = MagicMock()
        mock_module.warn = MagicMock()
        mock_module.fail_json = MagicMock(side_effect=Exception("Module failed"))
        return mock_module

    @pytest.fixture
    def mock_result(self):
        """Fixture to create a mock result dictionary"""
        return {
            'changed': False,
            'version': '22.2.0',
            'binary_path': '/usr/local/bin/cockroach',
            'architecture': 'amd64',
            'installation_type': ''
        }

    @pytest.fixture
    def temp_dir(self):
        """Fixture to create a temporary directory for tests"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

    def test_get_architecture_x86(self, mock_module):
        """Test architecture detection for x86_64"""
        with patch('cockroachdb_install.run_command') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = 'x86_64\n'
            mock_run.return_value = mock_result

            arch = get_architecture(mock_module)
            assert arch == 'amd64'
            mock_run.assert_called_once_with(mock_module, ['uname', '-m'])

    def test_get_architecture_arm(self, mock_module):
        """Test architecture detection for aarch64"""
        with patch('cockroachdb_install.run_command') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = 'aarch64\n'
            mock_run.return_value = mock_result

            arch = get_architecture(mock_module)
            assert arch == 'arm64'
            mock_run.assert_called_once_with(mock_module, ['uname', '-m'])

    def test_get_architecture_unsupported(self, mock_module):
        """Test architecture detection for unsupported arch"""
        with patch('cockroachdb_install.run_command') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = 'i386\n'
            mock_run.return_value = mock_result

            with pytest.raises(Exception):
                get_architecture(mock_module)
            mock_module.fail_json.assert_called_once()

    def test_is_already_installed_binary_missing(self, mock_module):
        """Test detection when binary is missing"""
        with patch('os.path.exists', return_value=False):
            result = is_already_installed(mock_module, '22.2.0')
            assert result is False

    def test_is_already_installed_master_version(self, mock_module):
        """Test detection for master version - always reinstall"""
        with patch('os.path.exists', return_value=True):
            result = is_already_installed(mock_module, 'master')
            assert result is False

    def test_is_already_installed_custom_version(self, mock_module):
        """Test detection for custom version - always reinstall"""
        with patch('os.path.exists', return_value=True):
            result = is_already_installed(mock_module, 'custom')
            assert result is False

    def test_is_already_installed_matches(self, mock_module):
        """Test detection when version matches"""
        with patch('os.path.exists', return_value=True), \
             patch('cockroachdb_install.run_command') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = 'CockroachDB v22.2.0'
            mock_run.return_value = mock_result

            result = is_already_installed(mock_module, '22.2.0')
            assert result is True

    def test_is_already_installed_no_match(self, mock_module):
        """Test detection when version doesn't match"""
        with patch('os.path.exists', return_value=True), \
             patch('cockroachdb_install.run_command') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = 'CockroachDB v21.2.0'
            mock_run.return_value = mock_result

            result = is_already_installed(mock_module, '22.2.0')
            assert result is False

    def test_install_binary(self, mock_module):
        """Test binary installation"""
        with patch('shutil.copy2') as mock_copy, \
             patch('os.chmod') as mock_chmod:
            install_binary(mock_module, '/src/cockroach')
            mock_copy.assert_called_once_with('/src/cockroach', '/usr/local/bin/cockroach')
            mock_chmod.assert_called_once_with('/usr/local/bin/cockroach', 0o755)

    def test_install_binary_error(self, mock_module):
        """Test binary installation error"""
        with patch('shutil.copy2', side_effect=Exception('Copy failed')):
            with pytest.raises(Exception):
                install_binary(mock_module, '/src/cockroach')
            mock_module.fail_json.assert_called_once()

    def test_download_file(self, mock_module):
        """Test file download"""
        with patch('cockroachdb_install.run_command') as mock_run, \
             patch('os.path.exists', return_value=True):
            download_file(mock_module, 'https://example.com/file.tgz')
            mock_run.assert_called_once()
            assert mock_run.call_args[0][1][0] == 'wget'

    def test_download_file_with_output_path(self, mock_module):
        """Test file download with output path"""
        with patch('cockroachdb_install.run_command') as mock_run, \
             patch('os.path.exists', return_value=True):
            download_file(mock_module, 'https://example.com/file.tgz', '/tmp/output.tgz')
            mock_run.assert_called_once()
            assert '-O' in mock_run.call_args[0][1]

    def test_download_file_failure(self, mock_module):
        """Test file download failure"""
        with patch('cockroachdb_install.run_command') as mock_run, \
             patch('os.path.exists', return_value=False):
            with pytest.raises(Exception):
                download_file(mock_module, 'https://example.com/file.tgz', '/tmp/output.tgz')
            mock_module.fail_json.assert_called_once()

    def test_extract_tarball(self, mock_module):
        """Test tarball extraction"""
        with patch('cockroachdb_install.run_command') as mock_run:
            extract_tarball(mock_module, 'file.tgz')
            mock_run.assert_called_once()
            assert 'tar' in mock_run.call_args[0][1]

    def test_extract_tarball_with_dir(self, mock_module):
        """Test tarball extraction to directory"""
        with patch('cockroachdb_install.run_command') as mock_run:
            extract_tarball(mock_module, 'file.tgz', '/tmp/extract')
            mock_run.assert_called_once()
            assert '-C' in mock_run.call_args[0][1]

    def test_find_and_install_from_directory_not_found(self, mock_module, mock_result):
        """Test finding binary when directory doesn't exist"""
        with patch('glob.glob', return_value=[]):
            result = find_and_install_from_directory(mock_module, 'cockroach*', mock_result)
            assert result is False

    def test_find_and_install_from_directory_no_binary(self, mock_module, mock_result):
        """Test finding binary when binary doesn't exist"""
        with patch('glob.glob', return_value=['cockroach-dir']), \
             patch('os.path.exists', return_value=False):
            result = find_and_install_from_directory(mock_module, 'cockroach*', mock_result)
            assert result is False

    def test_find_and_install_from_directory_success(self, mock_module, mock_result):
        """Test finding and installing binary successfully"""
        with patch('glob.glob', return_value=['cockroach-dir']), \
             patch('os.path.exists', return_value=True), \
             patch('cockroachdb_install.install_binary') as mock_install, \
             patch('cockroachdb_install.copy_gis_libraries') as mock_copy_gis:
            result = find_and_install_from_directory(mock_module, 'cockroach*', mock_result)
            assert result is True
            assert mock_result['changed'] is True
            mock_install.assert_called_once()
            mock_copy_gis.assert_not_called()  # No lib dir by default

    def test_find_and_install_from_directory_with_gis(self, mock_module, mock_result):
        """Test finding and installing binary with GIS libraries"""
        with patch('glob.glob', return_value=['cockroach-dir']), \
             patch('os.path.exists', side_effect=lambda path: True), \
             patch('cockroachdb_install.install_binary') as mock_install, \
             patch('cockroachdb_install.copy_gis_libraries') as mock_copy_gis:
            result = find_and_install_from_directory(mock_module, 'cockroach*', mock_result)
            assert result is True
            assert mock_result['changed'] is True
            mock_install.assert_called_once()
            mock_copy_gis.assert_called_once()

    def test_try_install_from_tarball_download_fails(self, mock_module, mock_result):
        """Test tarball installation when download fails"""
        with patch('cockroachdb_install.download_file', side_effect=Exception('Download failed')):
            result = _try_install_from_tarball(mock_module, 'https://example.com/file.tgz', mock_result)
            assert result is False
            mock_module.warn.assert_called_once()

    def test_try_install_from_tarball_no_tarball(self, mock_module, mock_result):
        """Test tarball installation when no tarball found"""
        with patch('cockroachdb_install.download_file'), \
             patch('glob.glob', return_value=[]):
            result = _try_install_from_tarball(mock_module, 'https://example.com/file.tgz', mock_result)
            assert result is False

    def test_try_install_from_tarball_success(self, mock_module, mock_result):
        """Test successful tarball installation"""
        with patch('cockroachdb_install.download_file'), \
             patch('glob.glob', side_effect=[['file.tgz'], []]), \
             patch('cockroachdb_install.extract_tarball'), \
             patch('cockroachdb_install.find_and_install_from_directory', return_value=True):
            result = _try_install_from_tarball(mock_module, 'https://example.com/file.tgz', mock_result)
            assert result is True

    def test_try_install_direct_binary_success(self, mock_module, mock_result):
        """Test successful direct binary installation"""
        with patch('cockroachdb_install.download_file'), \
             patch('os.path.exists', return_value=True), \
             patch('cockroachdb_install.install_binary'):
            result = _try_install_direct_binary(mock_module, 'https://example.com/cockroach', 'cockroach', mock_result)
            assert result is True
            assert mock_result['changed'] is True

    def test_try_install_direct_binary_not_found(self, mock_module, mock_result):
        """Test direct binary installation when binary not found"""
        with patch('cockroachdb_install.download_file'), \
             patch('os.path.exists', return_value=False):
            result = _try_install_direct_binary(mock_module, 'https://example.com/cockroach', 'cockroach', mock_result)
            assert result is False

    def test_copy_gis_libraries(self, mock_module, temp_dir):
        """Test copying GIS libraries"""
        # Create mock library files
        lib_path = os.path.join(temp_dir, 'lib')
        os.makedirs(lib_path)
        with open(os.path.join(lib_path, 'libgeos.so'), 'w') as f:
            f.write('mock lib')
        with open(os.path.join(lib_path, 'libgeos_c.so'), 'w') as f:
            f.write('mock lib')

        with patch('os.makedirs'), \
             patch('shutil.copy2') as mock_copy:
            copy_gis_libraries(mock_module, lib_path)
            assert mock_copy.call_count == 2

    def test_install_from_url_tarball_success(self, mock_module, mock_result):
        """Test successful installation from URL via tarball"""
        with patch('tempfile.TemporaryDirectory'), \
             patch('os.getcwd', return_value='/orig/dir'), \
             patch('os.chdir'), \
             patch('cockroachdb_install._try_install_from_tarball', return_value=True), \
             patch('cockroachdb_install._try_install_direct_binary', return_value=False):
            install_from_url(mock_module, 'https://example.com/file.tgz', mock_result)
            # No assertions needed - if it completes without exceptions, it worked

    def test_install_from_url_fallback(self, mock_module, mock_result):
        """Test fallback to direct binary when tarball fails"""
        with patch('tempfile.TemporaryDirectory'), \
             patch('os.getcwd', return_value='/orig/dir'), \
             patch('os.chdir'), \
             patch('cockroachdb_install._try_install_from_tarball', return_value=False), \
             patch('cockroachdb_install._try_install_direct_binary', return_value=True):
            install_from_url(
                mock_module,
                'https://example.com/file.tgz',
                mock_result,
                'https://example.com/cockroach',
                'cockroach'
            )
            # No assertions needed - if it completes without exceptions, it worked

    def test_install_from_url_all_fail(self, mock_module, mock_result):
        """Test failure when both approaches fail"""
        with patch('tempfile.TemporaryDirectory'), \
             patch('os.getcwd', return_value='/orig/dir'), \
             patch('os.chdir'), \
             patch('cockroachdb_install._try_install_from_tarball', return_value=False), \
             patch('cockroachdb_install._try_install_direct_binary', return_value=False):
            with pytest.raises(Exception):
                install_from_url(
                    mock_module,
                    'https://example.com/file.tgz',
                    mock_result,
                    'https://example.com/cockroach',
                    'cockroach'
                )
            mock_module.fail_json.assert_called_once()

    def test_install_cockroachdb_regular(self, mock_module, mock_result):
        """Test installation of regular version"""
        with patch('os.makedirs'), \
             patch('cockroachdb_install.install_from_url') as mock_install:
            install_cockroachdb(
                mock_module,
                '22.2.0',
                'cockroach-',
                'https://binaries.cockroachdb.com',
                None,
                'amd64',
                mock_result
            )
            assert mock_result['installation_type'] == 'regular'
            mock_install.assert_called_once()

    def test_install_cockroachdb_master(self, mock_module, mock_result):
        """Test installation of master version"""
        with patch('os.makedirs'), \
             patch('cockroachdb_install.install_from_url') as mock_install:
            install_cockroachdb(
                mock_module,
                'master',
                'cockroach-',
                'https://binaries.cockroachdb.com',
                None,
                'amd64',
                mock_result
            )
            assert mock_result['installation_type'] == 'master'
            mock_install.assert_called_once()

    def test_install_cockroachdb_custom(self, mock_module, mock_result):
        """Test installation of custom version"""
        with patch('os.makedirs'), \
             patch('cockroachdb_install.install_from_url') as mock_install:
            install_cockroachdb(
                mock_module,
                'custom',
                'cockroach-',
                'https://binaries.cockroachdb.com',
                'https://example.com/custom.tgz',
                'amd64',
                mock_result
            )
            assert mock_result['installation_type'] == 'custom'
            mock_install.assert_called_once()

    def test_install_cockroachdb_custom_no_url(self, mock_module, mock_result):
        """Test custom installation without URL"""
        with patch('os.makedirs'):
            with pytest.raises(Exception):
                install_cockroachdb(
                    mock_module,
                    'custom',
                    'cockroach-',
                    'https://binaries.cockroachdb.com',
                    None,
                    'amd64',
                    mock_result
                )
            mock_module.fail_json.assert_called_once()
