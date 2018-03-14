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

        labbook_dir = lb.new(name="labbook-test-init", description="my first labbook",
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

    def test_add_package(self, mock_config_with_repo):
        """Test adding a package such as one from apt-get or pip3. """
        # Create a labook
        lb = LabBook(mock_config_with_repo[0])
        labbook_dir = lb.new(name="labbook1-test-add-pkg", description="my first labbook",
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
        assert 'managed package: ' in log[0]["message"]
        assert "_GTM_ACTIVITY_START_" in log[4]["message"]
        assert 'managed package: ' in log[4]["message"]

    def test_add_duplicate_package(self, mock_config_with_repo):
        """Test adding a duplicate package to a labbook"""
        # Create a labook
        lb = LabBook(mock_config_with_repo[0])

        labbook_dir = lb.new(name="labbook-add-package-dup", description="my first labbook",
                             owner={"username": "test"})

        # Create Component Manager
        cm = ComponentManager(lb)

        # Add a component;
        cm.add_package('pip', 'requests', '2.18.4')

        # Verify file
        package_file = os.path.join(labbook_dir,
                                      '.gigantum',
                                      'env',
                                      'package_manager',
                                      'pip_requests.yaml')
        assert os.path.exists(package_file) is True

        # Add a component
        with pytest.raises(ValueError):
            cm.add_package('pip', 'requests', '2.18.4')

        # Force add a component
        cm.add_package('pip', 'requests', '2.18.2', force=True)
        assert os.path.exists(package_file) is True

        with open(package_file, 'rt') as pf:
            data = yaml.load(pf)
            assert data['version'] == '2.18.2'

    def test_add_component(self, mock_config_with_repo):
        """Test adding a component to a labbook"""
        # Create a labook
        lb = LabBook(mock_config_with_repo[0])

        labbook_dir = lb.new(name="labbook-test-add-component", description="my first labbook",
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
                                      f"{lmcommon.fixtures.ENV_UNIT_TEST_BASE}.yaml")
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

    def test_add_duplicate_component(self, mock_config_with_repo):
        """Test adding a duplicate component to a labbook"""
        # Create a labook
        lb = LabBook(mock_config_with_repo[0])

        labbook_dir = lb.new(name="labbook-add-dup", description="my first labbook",
                             owner={"username": "test"})

        # Create Component Manager
        cm = ComponentManager(lb)

        # Add a component;
        cm.add_component("base", lmcommon.fixtures.ENV_UNIT_TEST_REPO, lmcommon.fixtures.ENV_UNIT_TEST_BASE,
                         lmcommon.fixtures.ENV_UNIT_TEST_REV)

        c = f"{lmcommon.fixtures.ENV_UNIT_TEST_REPO}_{lmcommon.fixtures.ENV_UNIT_TEST_BASE}.yaml"
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

    def test_remove_package_errors(self, mock_config_with_repo):
        """Test removing a package with expected errors"""

        # Create a labook
        lb = LabBook(mock_config_with_repo[0])
        labbook_dir = lb.new(name="labbook-remove-pkg-errors", description="testing package removal errors",
                             owner={"username": "test"})

        # Create Component Manager
        cm = ComponentManager(lb)

        # Try removing package that doesn't exist
        with pytest.raises(ValueError):
            cm.remove_package('apt', 'ack')

        # Add a package as if it's from the base
        cm.add_package("pip3", "requests", from_base=True)

        # Try removing package that you can't because it comes from a base
        with pytest.raises(ValueError):
            cm.remove_package('pip3', 'requests')

    def test_remove_package(self, mock_config_with_repo):
        """Test removing a package such as one from apt-get or pip3. """
        # Create a labook
        lb = LabBook(mock_config_with_repo[0])
        labbook_dir = lb.new(name="test-remove-pkg", description="test removing packages",
                             owner={"username": "test"})

        # Create Component Manager
        cm = ComponentManager(lb)

        # Add some sample components
        cm.add_package("apt", "ack")
        cm.add_package("pip", "requests")
        cm.add_package("apt", "docker")
        cm.add_package("pip", "docker", package_version="1.3")
        cm.add_package("pip", "matplotlib", from_base=True)

        package_path = os.path.join(lb._root_dir, '.gigantum', 'env', 'package_manager')
        assert os.path.exists(package_path)

        # Ensure all four packages exist
        assert os.path.exists(os.path.join(package_path, "apt_ack.yaml"))
        assert os.path.exists(os.path.join(package_path, "pip_requests.yaml"))
        assert os.path.exists(os.path.join(package_path, "apt_docker.yaml"))
        assert os.path.exists(os.path.join(package_path, "pip_docker.yaml"))
        assert os.path.exists(os.path.join(package_path, "pip_matplotlib.yaml"))

        # Remove packages
        cm.remove_package("apt", "ack")
        cm.remove_package("pip", "requests")
        cm.remove_package("apt", "docker")
        cm.remove_package("pip", "docker")

        with pytest.raises(ValueError):
            cm.remove_package("pip", "matplotlib")

        # Ensure files are gone
        assert not os.path.exists(os.path.join(package_path, "apt_ack.yaml"))
        assert not os.path.exists(os.path.join(package_path, "pip_requests.yaml"))
        assert not os.path.exists(os.path.join(package_path, "apt_docker.yaml"))
        assert not os.path.exists(os.path.join(package_path, "pip_docker.yaml"))
        assert os.path.exists(os.path.join(package_path, "pip_matplotlib.yaml"))

        # Ensure git is clean
        status = lb.git.status()
        assert status['untracked'] == []
        assert status['staged'] == []
        assert status['unstaged'] == []

        # Ensure activity is being written
        log = lb.git.log()
        assert "_GTM_ACTIVITY_START_" in log[0]["message"]
        assert 'Remove pip managed package' in log[0]["message"]

    def test_remove_component_errors(self, mock_config_with_repo):
        """Test removing a component from a labbook expecting errors"""
        # Create a labook
        lb = LabBook(mock_config_with_repo[0])

        labbook_dir = lb.new(name="labbook-test-remove-component-errors", description="my first labbook",
                             owner={"username": "test"})

        # Create Component Manager
        cm = ComponentManager(lb)

        # Add a component
        cm.add_component("base", lmcommon.fixtures.ENV_UNIT_TEST_REPO, lmcommon.fixtures.ENV_UNIT_TEST_BASE,
                         lmcommon.fixtures.ENV_UNIT_TEST_REV)

        with pytest.raises(ValueError):
            cm.remove_component("base", lmcommon.fixtures.ENV_UNIT_TEST_REPO, "adfasdfasdfasdf")

    def test_remove_component(self, mock_config_with_repo):
        """Test removing a component from a labbook"""
        # Create a labook
        lb = LabBook(mock_config_with_repo[0])

        labbook_dir = lb.new(name="labbook-test-remove-component", description="my first labbook",
                             owner={"username": "test"})

        # Create Component Manager
        cm = ComponentManager(lb)

        # Add a component
        cm.add_component("base", lmcommon.fixtures.ENV_UNIT_TEST_REPO, lmcommon.fixtures.ENV_UNIT_TEST_BASE,
                         lmcommon.fixtures.ENV_UNIT_TEST_REV)

        component_filename = "{}_{}.yaml".format(lmcommon.fixtures.ENV_UNIT_TEST_REPO,
                                                     lmcommon.fixtures.ENV_UNIT_TEST_BASE)
        component_path = os.path.join(lb._root_dir, '.gigantum', 'env', 'base', component_filename)
        assert os.path.exists(component_path)

        # Remove component
        cm.remove_component("base", lmcommon.fixtures.ENV_UNIT_TEST_REPO, lmcommon.fixtures.ENV_UNIT_TEST_BASE)

        # Ensure file is gone
        assert not os.path.exists(component_path)

        # Ensure git is clean
        status = lb.git.status()
        assert status['untracked'] == []
        assert status['staged'] == []
        assert status['unstaged'] == []

        # Ensure activity is being written
        log = lb.git.log()
        assert "_GTM_ACTIVITY_START_" in log[0]["message"]
        assert 'Remove base component' in log[0]["message"]

    def test_misconfigured_base_no_base(self, mock_config_with_repo):
        lb = LabBook(mock_config_with_repo[0])
        lb.new(owner={"username": "test"}, name="test-base-1", description="validate tests.")
        cm = ComponentManager(lb)

        with pytest.raises(ValueError):
            a = cm.base_fields

    def test_misconfigured_base_two_bases(self, mock_config_with_repo):
        lb = LabBook(mock_config_with_repo[0])
        lb.new(owner={"username": "test"}, name="test-base-2", description="validate tests.")

        cm = ComponentManager(lb)

        # mock_config_with_repo is a ComponentManager Instance
        cm.add_component("base", lmcommon.fixtures.ENV_UNIT_TEST_REPO, "ut-jupyterlab-1", 0)
        cm.add_component("base", lmcommon.fixtures.ENV_UNIT_TEST_REPO, "ut-jupyterlab-2", 0)

        with pytest.raises(ValueError):
            a = cm.base_fields

    def test_get_base(self, mock_config_with_repo):
        lb = LabBook(mock_config_with_repo[0])
        lb.new(owner={"username": "test"}, name="test-base-3", description="validate tests.")

        cm = ComponentManager(lb)

        # mock_config_with_repo is a ComponentManager Instance
        cm.add_component("base", lmcommon.fixtures.ENV_UNIT_TEST_REPO, "ut-jupyterlab-1", 0)

        base_data = cm.base_fields

        assert type(base_data) == dict
        assert base_data['name'] == 'Unit Test1'
        assert base_data['os_class'] == 'ubuntu'
        assert base_data['schema'] == 1
