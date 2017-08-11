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

from lmcommon.environment import RepositoryManager


@pytest.fixture(scope="module")
def setup_index():
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

        # Run clone and index operation
        erm = RepositoryManager(fp.name)
        erm.update_repositories()
        erm.index_repositories()

        yield erm, temp_dir  # provide the fixture value

    # Remove the temp_dir
    shutil.rmtree(temp_dir)


class TestEnvironmentRepositoryManager(object):
    def test_update_repositories(self, setup_index):
        """Test building the index"""
        assert os.path.exists(os.path.join(setup_index[1], ".labmanager")) is True
        assert os.path.exists(os.path.join(setup_index[1], ".labmanager", "environment_repositories")) is True
        assert os.path.exists(os.path.join(setup_index[1], ".labmanager", "environment_repositories",
                                           "gig-dev_environment-components")) is True
        assert os.path.exists(os.path.join(setup_index[1], ".labmanager", "environment_repositories",
                                           "gig-dev_environment-components", "README.md")) is True

    def test_index_repositories_base_image(self, setup_index):
        """Test creating and accessing the detail version of the base image index"""
        # Verify index file contents
        with open(os.path.join(setup_index[0].local_repo_directory, "base_image_index.pickle"), 'rb') as fh:
            data = pickle.load(fh)

        assert "gig-dev_environment-components" in data
        assert "gigantum" in data["gig-dev_environment-components"]
        assert "info" in data["gig-dev_environment-components"]
        assert "maintainer" in data["gig-dev_environment-components"]['info']
        assert "repo" in data["gig-dev_environment-components"]['info']
        assert "ubuntu1604-python3" in data["gig-dev_environment-components"]["gigantum"]
        assert "0.1" in data["gig-dev_environment-components"]["gigantum"]["ubuntu1604-python3"]
        assert "info" in data["gig-dev_environment-components"]["gigantum"]["ubuntu1604-python3"]["0.1"]
        assert "author" in data["gig-dev_environment-components"]["gigantum"]["ubuntu1604-python3"]["0.1"]
        assert "image" in data["gig-dev_environment-components"]["gigantum"]["ubuntu1604-python3"]["0.1"]
        assert "available_package_managers" in data["gig-dev_environment-components"]["gigantum"]["ubuntu1604-python3"]["0.1"]
        assert "###namespace###" in data["gig-dev_environment-components"]["gigantum"]["ubuntu1604-python3"]["0.1"]
        assert "###repository###" in data["gig-dev_environment-components"]["gigantum"]["ubuntu1604-python3"]["0.1"]

    def test_index_repositories_dev_env(self, setup_index):
        """Test creating and accessing the detail version of the dev env index"""
        # Verify index file contents
        with open(os.path.join(setup_index[0].local_repo_directory, "dev_env_index.pickle"), 'rb') as fh:
            data = pickle.load(fh)

        assert "gig-dev_environment-components" in data
        assert "gigantum" in data["gig-dev_environment-components"]
        assert "gigantum-dev" in data["gig-dev_environment-components"]
        assert "info" in data["gig-dev_environment-components"]
        assert "maintainer" in data["gig-dev_environment-components"]['info']
        assert "repo" in data["gig-dev_environment-components"]['info']
        assert "jupyter-ubuntu" in data["gig-dev_environment-components"]["gigantum"]
        assert "jupyter-ubuntu-dup" in data["gig-dev_environment-components"]["gigantum"]
        assert "0.0" in data["gig-dev_environment-components"]["gigantum"]["jupyter-ubuntu"]
        assert "0.1" in data["gig-dev_environment-components"]["gigantum"]["jupyter-ubuntu"]
        assert "info" in data["gig-dev_environment-components"]["gigantum"]["jupyter-ubuntu"]["0.1"]
        assert "author" in data["gig-dev_environment-components"]["gigantum"]["jupyter-ubuntu"]["0.1"]
        assert "install_commands" in data["gig-dev_environment-components"]["gigantum"]["jupyter-ubuntu"]["0.1"]
        assert "exec_commands" in data["gig-dev_environment-components"]["gigantum"]["jupyter-ubuntu"]["0.1"]
        assert "exposed_tcp_ports" in data["gig-dev_environment-components"]["gigantum"]["jupyter-ubuntu"]["0.1"]
        assert "###namespace###" in data["gig-dev_environment-components"]["gigantum"]["jupyter-ubuntu"]["0.1"]
        assert "###repository###" in data["gig-dev_environment-components"]["gigantum"]["jupyter-ubuntu"]["0.1"]

    def test_index_repositories_custom(self, setup_index):
        """Test creating and accessing the detail version of the dev env index"""
        # Verify index file contents
        with open(os.path.join(setup_index[0].local_repo_directory, "custom_index.pickle"), 'rb') as fh:
            data = pickle.load(fh)

        assert "gig-dev_environment-components" in data
        assert "gigantum" in data["gig-dev_environment-components"]
        assert "info" in data["gig-dev_environment-components"]
        assert "maintainer" in data["gig-dev_environment-components"]['info']
        assert "repo" in data["gig-dev_environment-components"]['info']
        assert "ubuntu-python3-pillow" in data["gig-dev_environment-components"]["gigantum"]
        assert "ubuntu-python3-pillow-dup" in data["gig-dev_environment-components"]["gigantum"]
        assert "0.1" in data["gig-dev_environment-components"]["gigantum"]["ubuntu-python3-pillow"]
        assert "0.2" in data["gig-dev_environment-components"]["gigantum"]["ubuntu-python3-pillow"]
        assert "0.3" in data["gig-dev_environment-components"]["gigantum"]["ubuntu-python3-pillow"]
        assert "info" in data["gig-dev_environment-components"]["gigantum"]["ubuntu-python3-pillow"]["0.3"]
        assert "author" in data["gig-dev_environment-components"]["gigantum"]["ubuntu-python3-pillow"]["0.3"]
        assert "docker" in data["gig-dev_environment-components"]["gigantum"]["ubuntu-python3-pillow"]["0.3"]
        assert "Pillow==4.2.1 " in data["gig-dev_environment-components"]["gigantum"]["ubuntu-python3-pillow"]["0.3"]["docker"]
        assert "###namespace###" in data["gig-dev_environment-components"]["gigantum"]["ubuntu-python3-pillow"]["0.3"]
        assert "###repository###" in data["gig-dev_environment-components"]["gigantum"]["ubuntu-python3-pillow"]["0.3"]

    def test_index_repositories_base_image_list(self, setup_index):
        """Test accessing the list version of the base image index"""
        # Verify index file contents
        with open(os.path.join(setup_index[0].local_repo_directory, "base_image_list_index.pickle"), 'rb') as fh:
            data = pickle.load(fh)

        assert len(data) == 2
        assert data[0]['info']['name'] == 'ubuntu1604-python3'

    def test_index_repositories_dev_env_list(self, setup_index):
        """Test accessing the list version of the dev env index"""
        # Verify index file contents
        with open(os.path.join(setup_index[0].local_repo_directory, "dev_env_list_index.pickle"), 'rb') as fh:
            data = pickle.load(fh)

        assert len(data) == 3
        assert data[0]['info']['name'] == 'jupyter-ubuntu'
        assert data[0]['###namespace###'] == 'gigantum'
        assert data[1]['info']['name'] == 'jupyter-ubuntu-dup'
        assert data[2]['info']['name'] == 'jupyter-ubuntu'
        assert data[2]['###namespace###'] == 'gigantum-dev'

    def test_index_repositories_custom_list(self, setup_index):
        """Test accessing the list version of the dev env index"""
        # Verify index file contents
        with open(os.path.join(setup_index[0].local_repo_directory, "custom_list_index.pickle"), 'rb') as fh:
            data = pickle.load(fh)

        assert len(data) == 2
        assert data[0]['info']['name'] == 'ubuntu-python3-pillow'
        assert data[0]['###namespace###'] == 'gigantum'
        assert data[1]['info']['name'] == 'ubuntu-python3-pillow-dup'

