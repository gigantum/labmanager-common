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
import pprint

from lmcommon.environment import ComponentManager, RepositoryManager
from lmcommon.fixtures import mock_config_file, mock_config_with_repo
from lmcommon.labbook import LabBook
import lmcommon.fixtures

class TestComponentManager(object):
    def test_initalize_labbook(self, mock_config_with_repo):
        """Test preparing an empty labbook"""

        lb = LabBook(mock_config_with_repo[0])

        labbook_dir = lb.new(name="labbook1", description="my first labbook",
                             owner={"username": "test"})

        pprint.pprint([n[0] for n in os.walk(labbook_dir)])
        # Verify missing dir structure
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'base')) is True
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'package_manager')) is True
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'custom')) is True
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'entrypoint.sh')) is False

        cm = ComponentManager(lb)

        # Verify dir structure
        assert os.path.exists(os.path.join(labbook_dir, '.gigantum', 'env', 'base')) is True
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
        cm.add_package("apt", "ack")
        cm.add_package("pip3", "requests")
        cm.add_package("apt", "docker")
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
                for required_field in 'manager', 'package', 'from_base':
                    assert required_field in fields_dict.keys()

        # Verify git/activity
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
        cm.add_component("base", lmcommon.fixtures.ENV_UNIT_TEST_REPO, lmcommon.fixtures.ENV_UNIT_TEST_BASE,
                         lmcommon.fixtures.ENV_UNIT_TEST_REV)

        # Verify file
        component_file = os.path.join(labbook_dir,
                                      '.gigantum',
                                      'env',
                                      'base',
                                      f"{lmcommon.fixtures.ENV_UNIT_TEST_REPO}_"
                                      f"{lmcommon.fixtures.ENV_UNIT_TEST_BASE}_"
                                      f"r{lmcommon.fixtures.ENV_UNIT_TEST_REV}.yaml")
        assert os.path.exists(component_file) is True
        with open(component_file, 'rt') as cf:
            data = yaml.load(cf)

        preinstalled_pkgs = os.listdir(os.path.join(labbook_dir,".gigantum/env/package_manager"))
        for p in [n for n in preinstalled_pkgs if '.yaml' in n]:
            with open(os.path.join(labbook_dir,".gigantum/env/package_manager", p)) as f:
                assert 'from_base: true' in f.read()

        assert data['id'] == lmcommon.fixtures.ENV_UNIT_TEST_BASE
        assert data['revision'] == lmcommon.fixtures.ENV_UNIT_TEST_REV

        # Verify git/activity
        log = lb.git.log()
        assert len(log) >= 4
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

        # Add a component;
        cm.add_component("base", lmcommon.fixtures.ENV_UNIT_TEST_REPO, lmcommon.fixtures.ENV_UNIT_TEST_BASE,
                         lmcommon.fixtures.ENV_UNIT_TEST_REV)

        c = f"{lmcommon.fixtures.ENV_UNIT_TEST_REPO}_{lmcommon.fixtures.ENV_UNIT_TEST_BASE}_r{lmcommon.fixtures.ENV_UNIT_TEST_REV}.yaml"
        # Verify file
        component_file = os.path.join(labbook_dir,
                                      '.gigantum',
                                      'env',
                                      'base',
                                      c)
        assert os.path.exists(component_file) is True

        # Add a component
        with pytest.raises(ValueError):
            cm.add_component("base", lmcommon.fixtures.ENV_UNIT_TEST_REPO, lmcommon.fixtures.ENV_UNIT_TEST_BASE,
                             lmcommon.fixtures.ENV_UNIT_TEST_REV)

        # Force add a component
        cm.add_component("base", lmcommon.fixtures.ENV_UNIT_TEST_REPO, lmcommon.fixtures.ENV_UNIT_TEST_BASE,
                         lmcommon.fixtures.ENV_UNIT_TEST_REV, force=True)
        assert os.path.exists(component_file) is True

    def test_get_component_list_base(self, mock_config_with_repo):
        """Test listing base images added a to labbook"""
        lb = LabBook(mock_config_with_repo[0])
        lb.new(name="labbook2a", description="my first labbook",
               owner={"username": "test"})
        cm = ComponentManager(lb)

        # mock_config_with_repo is a ComponentManager Instance
        cm.add_component("base", lmcommon.fixtures.ENV_UNIT_TEST_REPO, lmcommon.fixtures.ENV_UNIT_TEST_BASE,
                         lmcommon.fixtures.ENV_UNIT_TEST_REV)

        bases = cm.get_component_list('base')

        assert len(bases) == 1
        assert bases[0]['id'] == lmcommon.fixtures.ENV_UNIT_TEST_BASE
        assert bases[0]['revision'] == lmcommon.fixtures.ENV_UNIT_TEST_REV

    def test_get_component_list_packages(self, mock_config_with_repo):
        """Test listing packages added a to labbook"""
        lb = LabBook(mock_config_with_repo[0])
        lb.new(name="labbook2b", description="my first labbook",
               owner={"username": "test"})
        cm = ComponentManager(lb)

        # mock_config_with_repo is a ComponentManager Instance
        cm.add_package("apt", "ack")
        cm.add_package("pip3", "requests", package_version='2.18.4')
        cm.add_package("apt", "docker")
        cm.add_package("pip3", "docker")

        packages = cm.get_component_list('package_manager')

        assert len(packages) == 4
        assert packages[0]['manager'] == 'apt'
        assert packages[0]['package'] == 'ack'
        assert packages[1]['manager'] == 'apt'
        assert packages[1]['package'] == 'docker'
        assert packages[2]['manager'] == 'pip3'
        assert packages[2]['package'] == 'docker'
        assert packages[2].get('version') is None
        assert packages[3]['manager'] == 'pip3'
        assert packages[3]['package'] == 'requests'
        assert packages[3]['version'] == '2.18.4'

    def test_get_component_list_custom(self, mock_config_with_repo):
        """Test listing custom dependencies added a to labbook"""
        lb = LabBook(mock_config_with_repo[0])
        lb.new(name="labbook2c", description="my first labbook",
               owner={"username": "test"})
        cm = ComponentManager(lb)

        # mock_config_with_repo is a ComponentManager Instance
        cm.add_component("custom",
                         lmcommon.fixtures.ENV_UNIT_TEST_REPO,
                         "pillow",
                         0)

        custom_deps = cm.get_component_list('custom')

        assert len(custom_deps) == 1
        assert custom_deps[0]['id'] == 'pillow'
        assert custom_deps[0]['revision'] == 0
