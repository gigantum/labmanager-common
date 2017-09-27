# Copyright (c) 2017 FlashX, LLC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import pytest
import tempfile
from unittest.mock import PropertyMock, patch

from lmcommon.configuration import (Configuration, _get_docker_server_api_version, get_docker_client)

@pytest.fixture(scope="module")
def mock_config_file():
    with tempfile.NamedTemporaryFile(mode="wt") as fp:
        # Write a temporary config file
        fp.write("""core:
  team_mode: true 
git:
  working_directory: '~/gigantum'""")
        fp.seek(0)

        yield fp.name  # provide the fixture value


@pytest.fixture(scope="module")
def mock_config_file_no_delete():
    with tempfile.NamedTemporaryFile(mode="wt", delete=False) as fp:
        # Write a temporary config file
        fp.write("""core:
  team_mode: true 
git:
  working_directory: '~/gigantum'""")
        fp.close()

        yield fp.name  # provide the fixture value

    del fp.name


@pytest.fixture(scope="module")
def mock_config_file_inherit():
    with tempfile.NamedTemporaryFile(mode="wt", delete=False) as parent_fp:
        # Write a temporary config file
        parent_fp.write("""test: 'new field'
core:
  team_mode: false""")
        parent_fp.close()

    with tempfile.NamedTemporaryFile(mode="wt", delete=False) as fp:
        # Write a temporary config file
        fp.write("""from: {}
core:
  team_mode: true 
git:
  working_directory: '~/gigantum'""".format(parent_fp.name))
        fp.close()

        yield fp.name  # provide the fixture value

    del fp.name


class TestConfiguration(object):
    def test_init(self, mock_config_file):
        """Test loading a config file explicitly"""
        configuration = Configuration(mock_config_file)

        assert 'core' in configuration.config
        assert 'team_mode' in configuration.config["core"]
        assert configuration.config["core"]["team_mode"] is True
        assert 'git' in configuration.config

    def test_init_inherit(self, mock_config_file_inherit):
        """Test loading a config file explicitly from a file that inherits properties"""
        configuration = Configuration(mock_config_file_inherit)

        assert 'core' in configuration.config
        assert 'team_mode' in configuration.config["core"]
        assert configuration.config["core"]["team_mode"] is False
        assert 'git' in configuration.config
        assert 'test' in configuration.config
        assert 'from' in configuration.config
        assert configuration.config["test"] == 'new field'

    def test_init_load_from_package(self):
        """Test loading the default file from the package"""
        configuration = Configuration()

        assert 'core' in configuration.config
        assert 'git' in configuration.config

    def test_init_load_from_install(self, mock_config_file):
        """Test loading the default file from the installed location"""
        with patch('lmcommon.configuration.Configuration.INSTALLED_LOCATION', new_callable=PropertyMock,
                   return_value=mock_config_file):
            configuration = Configuration()

            assert 'core' in configuration.config
            assert 'git' in configuration.config

    def test_save(self, mock_config_file_no_delete):
        """Test writing changes to a config file"""
        configuration = Configuration(mock_config_file_no_delete)

        assert 'core' in configuration.config
        assert 'team_mode' in configuration.config["core"]
        assert configuration.config["core"]["team_mode"] is True
        assert 'git' in configuration.config

        configuration.config["core"]["team_mode"] = False
        configuration.config["git"]["working_directory"] = "/some/dir/now/"
        configuration.save()

        del configuration

        configuration = Configuration(mock_config_file_no_delete)

        assert 'core' in configuration.config
        assert 'team_mode' in configuration.config["core"]
        assert configuration.config["core"]["team_mode"] is False
        assert 'git' in configuration.config
        assert configuration.config["git"]["working_directory"] == "/some/dir/now/"

    def test_get_docker_version_str(self):
        """Docker API version strings are in the format of X.XX. """
        try:
            f_val = float(_get_docker_server_api_version())
            assert f_val > 1.0 and f_val < 2.0
        except ValueError:
            pass

    def test_get_docker_client(self):
        """Test no exceptions when getting docker client both for max-compatible versions and default versions. """
        docker_client = get_docker_client(check_server_version=True)
        docker_client_2 = get_docker_client(check_server_version=False)
