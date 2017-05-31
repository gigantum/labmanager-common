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
import yaml
from unittest.mock import PropertyMock, patch
from lmcommon.configuration import Configuration


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


class TestConfiguration(object):
    def test_init(self, mock_config_file):
        """Test loading a config file explicitly"""
        configuration = Configuration(mock_config_file)

        assert 'core' in configuration.config
        assert 'team_mode' in configuration.config["core"]
        assert configuration.config["core"]["team_mode"] is True
        assert 'git' in configuration.config

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
