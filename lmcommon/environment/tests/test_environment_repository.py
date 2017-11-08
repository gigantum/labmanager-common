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
import pickle
import yaml

from lmcommon.environment import RepositoryManager, ComponentRepository
from lmcommon.fixtures import mock_config_file, mock_config_with_repo


class TestEnvironmentRepository(object):
    def test_get_list_index_base_image(self, mock_config_with_repo):
        """Test accessing the list version of the index"""
        repo = ComponentRepository(mock_config_with_repo[0])
        data = repo.get_component_list("base_image")

        assert type(data) == list
        assert len(data) == 2
        assert data[0]['info']['name'] == 'ubuntu1604-python3'
        assert data[0]['###namespace###'] == 'gigantum'
        assert data[0]['###repository###'] == 'gig-dev_environment-components'
        assert data[1]['info']['name'] == 'ubuntu1604-python3-dup'

    def test_get_component_index_base_image(self, mock_config_with_repo):
        """Test accessing the detail version of the index"""
        repo = ComponentRepository(mock_config_with_repo[0])
        data = repo.get_component_versions('base_image', 'gig-dev_environment-components', 'gigantum',
                                           'ubuntu1604-python3')

        assert type(data) == list
        assert len(data) == 4
        assert data[0][0] == '0.4'
        assert data[3][0] == '0.1'
        assert data[0][1]['info']['name'] == 'ubuntu1604-python3'
        assert data[0][1]['###namespace###'] == 'gigantum'
        assert data[0][1]['###repository###'] == 'gig-dev_environment-components'

    def test_get_component_version_base_image(self, mock_config_with_repo):
        """Test accessing the a single version of the index"""
        repo = ComponentRepository(mock_config_with_repo[0])
        data = repo.get_component('base_image', 'gig-dev_environment-components', 'gigantum',
                                  'ubuntu1604-python3', '0.2')

        assert type(data) == dict
        assert data['info']['name'] == 'ubuntu1604-python3'
        assert data['info']['version_major'] == 0
        assert data['info']['version_minor'] == 2
        assert 'author' in data
        assert 'image' in data
        assert len(data['available_package_managers']) == 2
        assert data['###namespace###'] == 'gigantum'
        assert data['###repository###'] == 'gig-dev_environment-components'

    def test_get_component_version_base_image_does_not_exist(self, mock_config_with_repo):
        """Test accessing the a single version of the index that does not exist"""
        repo = ComponentRepository(mock_config_with_repo[0])
        with pytest.raises(ValueError):
            repo.get_component('base_image', 'gig-dev_environment-componentsXXX', 'gigantum',
                               'ubuntu1604-python3', '0.1')
        with pytest.raises(ValueError):
            repo.get_component('base_image', 'gig-dev_environment-components', 'gigantumXXX',
                               'ubuntu1604-python3', '0.1')
        with pytest.raises(ValueError):
            repo.get_component('base_image', 'gig-dev_environment-components', 'gigantum',
                               'ubuntu1604-python3XXX', '0.1')
        with pytest.raises(ValueError):
            repo.get_component('base_image', 'gig-dev_environment-components', 'gigantum',
                               'ubuntu1604-python3', '0.1333333333')



