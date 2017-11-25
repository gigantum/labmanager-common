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
import os
import yaml

from lmcommon.environment import ComponentManager, RepositoryManager
from lmcommon.fixtures import mock_config_file, mock_config_with_repo
from lmcommon.labbook import LabBook


class TestComponentManager(object):
    def test_initalize_labbook(self, mock_config_file):
        """Test preparing an empty labbook"""

        lb = LabBook(mock_config_file[0])

        labbook_dir = lb.new(name="labbook1", description="my first labbook",
                             owner={"username": "test"})

        # Verify missing dir structure
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'base_image')) is True
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'dev_env')) is True
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'package_manager')) is True
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'custom')) is True
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
        labbook_dir = lb.new(name="labbook1", description="my first labbook",
                             owner={"username": "test"})

        # Create Component Manager
        cm = ComponentManager(lb)

        # Add some sample components
        cm.add_package("apt-get", "ack")
        cm.add_package("pip3", "requests")
        cm.add_package("apt-get", "docker")
        cm.add_package("pip3", "docker")

        package_path = os.path.join(lb._root_dir, '.gigantum', 'env', 'package_manager')
        assert os.path.exists(package_path)

        # Ensure all four packages exist.
        package_files = [f for f in os.listdir(package_path)]
        package_files = [p for p in package_files if p != '.gitkeep']
        assert len(package_files) == 4

        # Ensure the fields in each of the 4 packages exist.
        for file in package_files:
            full_path = os.path.join(package_path, file)
            with open(full_path) as package_yaml:
                fields_dict = yaml.load(package_yaml.read())
                for required_field in 'package_manager', 'name', 'version':
                    assert required_field in fields_dict.keys()

        # Verify git/notes
        log = lb.git.log()
        assert len(log) == 10
        assert "_GTM_ACTIVITY_START_" in log[0]["message"]
        assert 'Added new software package' in log[0]["message"]
        assert "_GTM_ACTIVITY_START_" in log[4]["message"]
        assert 'Added new software package' in log[4]["message"]

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
        assert "_GTM_ACTIVITY_START_" in log[0]["message"]
        assert 'environment component:' in log[0]["message"]

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

    def test_get_component_list_base_image(self, mock_config_with_repo):
        """Test listing base images added a to labbook"""
        lb = LabBook(mock_config_with_repo[0])
        lb.new(name="labbook2a", description="my first labbook",
               owner={"username": "test"})
        cm = ComponentManager(lb)

        # mock_config_with_repo is a ComponentManager Instance
        cm.add_component("base_image",
                                        "gig-dev_environment-components",
                                        "gigantum",
                                        "ubuntu1604-python3",
                                        "0.4")

        dev_envs = cm.get_component_list('base_image')

        assert len(dev_envs) == 1
        assert dev_envs[0]['info']['name'] == 'ubuntu1604-python3'
        assert dev_envs[0]['info']['version_major'] == 0
        assert dev_envs[0]['info']['version_minor'] == 4
        assert dev_envs[0]['###namespace###'] == 'gigantum'

    def test_get_component_list_packages(self, mock_config_with_repo):
        """Test listing packages added a to labbook"""
        lb = LabBook(mock_config_with_repo[0])
        lb.new(name="labbook2b", description="my first labbook",
               owner={"username": "test"})
        cm = ComponentManager(lb)

        # mock_config_with_repo is a ComponentManager Instance
        cm.add_package("apt-get", "ack")
        cm.add_package("pip3", "requests")
        cm.add_package("apt-get", "docker")
        cm.add_package("pip3", "docker")

        packages = cm.get_component_list('package_manager')

        assert len(packages) == 4
        assert packages[0]['package_manager'] == 'apt-get'
        assert packages[0]['name'] == 'ack'
        assert packages[1]['package_manager'] == 'apt-get'
        assert packages[1]['name'] == 'docker'
        assert packages[2]['package_manager'] == 'pip3'
        assert packages[2]['name'] == 'docker'
        assert packages[3]['package_manager'] == 'pip3'
        assert packages[3]['name'] == 'requests'

    def test_get_component_list_custom(self, mock_config_with_repo):
        """Test listing custom dependencies added a to labbook"""
        lb = LabBook(mock_config_with_repo[0])
        lb.new(name="labbook2c", description="my first labbook",
               owner={"username": "test"})
        cm = ComponentManager(lb)

        # mock_config_with_repo is a ComponentManager Instance
        cm.add_component("custom",
                         "gig-dev_environment-components",
                         "gigantum",
                         "ubuntu-python3-pillow",
                         "0.3")
        cm.add_component("custom",
                         "gig-dev_environment-components",
                         "gigantum",
                         "ubuntu-python3-pillow-dup",
                         "0.2")

        custom_deps = cm.get_component_list('custom')

        assert len(custom_deps) == 2
        assert custom_deps[0]['info']['name'] == 'ubuntu-python3-pillow-dup'
        assert custom_deps[0]['info']['version_major'] == 0
        assert custom_deps[0]['info']['version_minor'] == 2
        assert custom_deps[0]['###namespace###'] == 'gigantum'
        assert custom_deps[1]['info']['name'] == 'ubuntu-python3-pillow'
        assert custom_deps[1]['info']['version_major'] == 0
        assert custom_deps[1]['info']['version_minor'] == 3
        assert custom_deps[1]['###namespace###'] == 'gigantum'


