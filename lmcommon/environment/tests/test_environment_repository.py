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


@pytest.fixture()
def mock_config_file():
    """A pytest fixture that creates a temporary directory and a config file to match. Deletes directory after test"""
    # Create a temporary working directory
    temp_dir = os.path.join(tempfile.tempdir, uuid.uuid4().hex)
    os.makedirs(temp_dir)

    with tempfile.NamedTemporaryFile(mode="wt") as fp:
        # Write a temporary config file
        fp.write("""core:
  team_mode: false 
  
environment:
  repo_url:
    - "https://github.com/gig-dev/environment-components.git"
    
git:
  backend: 'filesystem'
  working_directory: '{}'""".format(temp_dir))
        fp.seek(0)

        # Build index
        erm = RepositoryManager(fp.name)
        erm.update_repositories()
        erm.index_repositories()

        yield fp.name, erm  # provide the fixture value

    # Remove the temp_dir
    shutil.rmtree(temp_dir)


class TestEnvironmentRepository(object):
    def test_get_list_index_base_image(self, mock_config_file):
        """Test accessing the list version of the index"""
        repo = ComponentRepository(mock_config_file[0])
        data = repo.get_component_list("base_image")

        assert type(data) == list
        assert data[0]['info']['name'] == 'ubuntu1604-python3'
        assert data[0]['namespace'] == 'gigantum'
        assert data[0]['repository'] == 'gig-dev_environment-components'

    def test_get_component_index_base_image(self, mock_config_file):
        """Test accessing the detail version of the index"""
        repo = ComponentRepository(mock_config_file[0])
        data = repo.get_component_versions('base_image', 'gig-dev_environment-components', 'gigantum',
                                         'ubuntu1604-python3')

        assert type(data) == list
        assert data[0][0] == '0.1.0'
        assert data[0][1]['info']['name'] == 'ubuntu1604-python3'
        assert data[0][1]['namespace'] == 'gigantum'
        assert data[0][1]['repository'] == 'gig-dev_environment-components'


