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
import os
import uuid
import shutil
import pprint
import pickle
import yaml

from lmcommon.environment import RepositoryManager, ComponentRepository
from lmcommon.fixtures import (mock_config_file, mock_config_with_repo, setup_index,
                               ENV_UNIT_TEST_REPO, ENV_UNIT_TEST_BASE, ENV_UNIT_TEST_REV)


class TestEnvironmentRepository(object):
    def test_get_list_index_base_image(self, setup_index, mock_config_with_repo):
        """Test accessing the list version of the index"""

        repo = ComponentRepository(mock_config_with_repo[0])
        data = repo.get_component_list("base")

        assert type(data) == list
        assert len(data) >= 1

        assert any(n.get('id') == ENV_UNIT_TEST_BASE for n in data)
        assert any(n.get('###repository###') == ENV_UNIT_TEST_REPO for n in data)

    def test_get_component_index_base(self, mock_config_with_repo):
        """Test accessing the detail version of the index"""
        repo = ComponentRepository(mock_config_with_repo[0])
        data = repo.get_component_versions('base',
                                           ENV_UNIT_TEST_REPO,
                                           ENV_UNIT_TEST_BASE)
        assert type(data) == list
        assert len(data) >= 1
        assert data[-1][1]['id'] == ENV_UNIT_TEST_BASE
        assert data[-1][1]['###repository###'] == ENV_UNIT_TEST_REPO

    def test_get_component_version_base(self, mock_config_with_repo):
        """Test accessing the a single version of the index"""
        repo = ComponentRepository(mock_config_with_repo[0])
        data = repo.get_component('base',
                                  ENV_UNIT_TEST_REPO,
                                  ENV_UNIT_TEST_BASE,
                                  ENV_UNIT_TEST_REV)

        assert type(data) == dict
        assert data['id'] == ENV_UNIT_TEST_BASE
        assert data['revision'] == ENV_UNIT_TEST_REV
        assert 'image' in data
        assert len(data['package_managers']) == 2
        assert data['###repository###'] == ENV_UNIT_TEST_REPO

    def test_get_component_version_base_does_not_exist(self, mock_config_with_repo):
        """Test accessing the a single version of the index that does not exist"""
        repo = ComponentRepository(mock_config_with_repo[0])
        with pytest.raises(ValueError):
            repo.get_component('base', 'gig-dev_environment-componentsXXX',
                               'quickstart-jupyterlab', '0.1')
        with pytest.raises(ValueError):
            repo.get_component('base', ENV_UNIT_TEST_REPO,
                               'quickstart-jupyterlab', '3')
        with pytest.raises(ValueError):
            repo.get_component('base', ENV_UNIT_TEST_REPO,
                               'quickstart-jupyterlabXXX', 0)
        with pytest.raises(ValueError):
            repo.get_component('base', 'gig-dev_environment-components',
                               'quickstart-jupyterlab', 99)
