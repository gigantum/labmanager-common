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
import yaml

from lmcommon.environment import ComponentManager, RepositoryManager
from lmcommon.labbook import LabBook


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


class TestComponentManager(object):
    def test_initalize_labbook(self, mock_config_file):
        """Test preparing an empty labbook"""

        lb = LabBook(mock_config_file[0])

        labbook_dir = lb.new(name="labbook1", description="my first labbook",
                             owner={"username": "test"})

        # Verify missing dir structure
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'base_image')) is False
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'dev_env')) is False
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'package_manager')) is False
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'custom')) is False
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'entrypoint.sh')) is False

        cm = ComponentManager(lb)

        # Verify dir structure
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'base_image')) is True
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'dev_env')) is True
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'package_manager')) is True
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'custom')) is True
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'entrypoint.sh')) is True

    def test_add_package(self, mock_config_file):
        """Test adding a package such as one from apt-get or pip3. """

        # Build the environment component repo
        erm = RepositoryManager(mock_config_file[0])
        erm.update_repositories()
        erm.index_repositories()

        # Create a labook
        lb = LabBook(mock_config_file[0])

        # Create Component Manager
        cm = ComponentManager(lb)

        # Add some sample components
        cm.add_package("apt-get", "ack")
        cm.add_package("pip3", "requests")
        cm.add_package("apt-get", "docker")
        cm.add_package("pip3", "docker")

        for file in [f for f in os.listdir(lb._root_dir) if os.path.isfile(f)]:
            with open(f) as package_yaml:
                fields_dict = yaml.load(package_yaml)
                for required_field in 'package_manager', 'name', 'version'
                    assert required_field in fields_dict.keys()
        else:
            assert False, "No YAML files generated."



    def test_add_component(self, mock_config_file):
        """Test adding a component to a labbook"""
        # Build the environment component repo
        erm = RepositoryManager(mock_config_file[0])
        erm.update_repositories()
        erm.index_repositories()

        # Create a labook
        lb = LabBook(mock_config_file[0])

        labbook_dir = lb.new(name="labbook1", description="my first labbook",
                             owner={"username": "test"})

        # Create Component Manager
        cm = ComponentManager(lb)

        # Add a component
        cm.add_component("base_image", "gig-dev_environment-components", "gigantum", "ubuntu1604-python3", "0.4")

        # Verify file
        component_file = os.path.join(labbook_dir,
                                           '.gigantum',
                                           'env',
                                           'base_image',
                                           "gig-dev_environment-components_gigantum_ubuntu1604-python3.yaml")
        assert os.path.exists(component_file) is True
        with open(component_file, 'rt') as cf:
            data = yaml.load(cf)

        assert data['info']['name'] == 'ubuntu1604-python3'
        assert data['info']['version_major'] == 0
        assert data['info']['version_minor'] == 4
        assert data['###namespace###'] == 'gigantum'

        # Verify git/notes
        log = lb.git.log()
        assert len(log) == 4
        assert "gtmNOTE" in log[0]["message"]
        assert 'ubuntu1604-python3' in log[0]["message"]

    def test_add_duplicate_component(self, mock_config_file):
        """Test adding a duplicate component to a labbook"""
        # Build the environment component repo
        erm = RepositoryManager(mock_config_file[0])
        erm.update_repositories()
        erm.index_repositories()

        # Create a labook
        lb = LabBook(mock_config_file[0])

        labbook_dir = lb.new(name="labbook1", description="my first labbook",
                             owner={"username": "test"})

        # Create Component Manager
        cm = ComponentManager(lb)

        # Add a component
        cm.add_component("base_image", "gig-dev_environment-components", "gigantum", "ubuntu1604-python3", "0.4")

        # Verify file
        component_file = os.path.join(labbook_dir,
                                           '.gigantum',
                                           'env',
                                           'base_image',
                                           "gig-dev_environment-components_gigantum_ubuntu1604-python3.yaml")
        assert os.path.exists(component_file) is True

        # Add a component
        with pytest.raises(ValueError):
            cm.add_component("base_image", "gig-dev_environment-components", "gigantum", "ubuntu1604-python3", "0.4")

        # Force add a component
        cm.add_component("base_image", "gig-dev_environment-components", "gigantum", "ubuntu1604-python3", "0.4",
                         force=True)
        assert os.path.exists(component_file) is True



