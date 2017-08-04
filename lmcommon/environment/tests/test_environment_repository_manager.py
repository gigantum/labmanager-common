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

from lmcommon.environment import EnvironmentRepositoryManager


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

        yield fp.name, temp_dir  # provide the fixture value

    # Remove the temp_dir
    shutil.rmtree(temp_dir)


class TestEnvironmentRepositoryManager(object):
    def test_update_repositories(self, mock_config_file):
        """Test creating an empty labbook"""
        erm = EnvironmentRepositoryManager(mock_config_file[0])

        erm.update_repositories()

        assert os.path.exists(os.path.join(mock_config_file[1], ".labmanager")) is True
        assert os.path.exists(os.path.join(mock_config_file[1], ".labmanager", "environment_repositories")) is True
        assert os.path.exists(os.path.join(mock_config_file[1], ".labmanager", "environment_repositories",
                                           "gig-dev_environment-components")) is True
        assert os.path.exists(os.path.join(mock_config_file[1], ".labmanager", "environment_repositories",
                                           "gig-dev_environment-components", "README.md")) is True

    def test_index_repositories(self, mock_config_file):
        """Test creating an empty labbook"""
        erm = EnvironmentRepositoryManager(mock_config_file[0])

        erm.update_repositories()

        erm.index_repositories()

        # Verify index file contents
        with open(os.path.join(erm.local_repo_directory, "base_image_index.pickle"), 'rb') as fh:
            data = pickle.load(fh)

        assert "gigantum" in data
        assert "ubuntu1604-python3" in data["gigantum"]
        assert "0.1.0" in data["gigantum"]["ubuntu1604-python3"]
        assert "info" in data["gigantum"]["ubuntu1604-python3"]["0.1.0"]
        assert "author" in data["gigantum"]["ubuntu1604-python3"]["0.1.0"]
        assert "image" in data["gigantum"]["ubuntu1604-python3"]["0.1.0"]
        assert "available_package_managers" in data["gigantum"]["ubuntu1604-python3"]["0.1.0"]
        assert "namespace" in data["gigantum"]["ubuntu1604-python3"]["0.1.0"]
