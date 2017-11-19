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
import json
import os
import shutil
import tempfile
import uuid
import collections
import git
from pkg_resources import resource_filename
import pytest

from lmcommon.configuration import Configuration
from lmcommon.environment import RepositoryManager
from lmcommon.labbook import LabBook
from lmcommon.activity.detaildb import ActivityDetailDB


def _create_temp_work_dir(override_dict: dict = None):
    """Helper method to create a temporary working directory and associated config file"""
    def merge_dict(d1, d2) -> None:
        """Method to merge 1 dictionary into another, updating and adding key/values as needed
        """
        for k, v2 in d2.items():
            v1 = d1.get(k)  # returns None if v1 has no value for this key
            if (isinstance(v1, collections.Mapping) and
                    isinstance(v2, collections.Mapping)):
                merge_dict(v1, v2)
            else:
                d1[k] = v2

    # Create a temporary working directory
    unit_test_working_dir = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
    os.makedirs(unit_test_working_dir)

    default_override_config = {
        'core': {
            'team_mode': False
        },
        'environment': {
            'repo_url': ["https://github.com/gig-dev/environment-components.git"]
        },
        'flask': {
            'DEBUG': False
        },
        'git': {
            'working_directory': unit_test_working_dir,
            'backend': 'filesystem'
        },
        'auth': {
            'audience': "io.gigantum.api.dev"
        },
        'lock': {
            'redis': {
                'strict': False,
                'db': 4
            }
        }
    }

    config = Configuration()
    merge_dict(config.config, default_override_config)
    if override_dict:
        config.config.update(override_dict)

    config_file = os.path.join(unit_test_working_dir, "temp_config.yaml")
    config.save(config_file)

    # Return (path-to-config-file, ephemeral-working-directory).
    return config_file, unit_test_working_dir


@pytest.fixture()
def mock_config_file_team():
    """A pytest fixture that creates a temporary directory and a config file to match. Deletes directory after test"""
    conf_file, working_dir = _create_temp_work_dir(override_dict={'core': {'team_mode': True}})
    yield conf_file, working_dir
    shutil.rmtree(working_dir)


@pytest.fixture()
def mock_config_file():
    """A pytest fixture that creates a temporary directory and a config file to match. Deletes directory after test"""
    conf_file, working_dir = _create_temp_work_dir()
    yield conf_file, working_dir
    shutil.rmtree(working_dir)


@pytest.fixture(scope="class")
def mock_config_with_repo():
    """A pytest fixture that creates a temporary directory and a config file to match. Deletes directory after test"""
    conf_file, working_dir = _create_temp_work_dir()
    erm = RepositoryManager(conf_file)
    erm.update_repositories()
    erm.index_repositories()
    yield conf_file, working_dir
    shutil.rmtree(working_dir)


@pytest.fixture()
def mock_config_file_with_auth():
    """A pytest fixture that creates a temporary directory and a config file to match. Deletes directory after test"""
    # Load auth config for testing
    test_auth_file = os.path.join(resource_filename('lmcommon',
                                                    'auth{}tests'.format(os.path.sep)), 'auth_config.json')
    if not os.path.exists(test_auth_file):
        test_auth_file = f"{test_auth_file}.example"

    with open(test_auth_file, 'rt') as conf:
        auth_data = json.load(conf)

    overrides = {
        'auth': {
            'provider_domain': 'gigantum.auth0.com',
            'signing_algorithm': 'RS256',
            'audience': auth_data['audience'],
            'identity_manager': 'local'
        }
    }

    conf_file, working_dir = _create_temp_work_dir(override_dict=overrides)
    yield conf_file, working_dir, auth_data  # provide the fixture value
    shutil.rmtree(working_dir)


@pytest.fixture()
def mock_config_with_notestore():
    """A pytest fixture that creates a notestore (and labbook) and deletes directory after test"""
    # Create a temporary working directory
    conf_file, working_dir = _create_temp_work_dir()
    lb = LabBook(conf_file)
    lb.new({"username": "default"}, "labbook1", username="default", description="my first labbook")
    #ns = NoteStore(lb)

    yield 1, lb

    # Remove the temp_dir
    shutil.rmtree(working_dir)


@pytest.fixture()
def mock_config_with_detaildb():
    """A pytest fixture that creates a notestore (and labbook) and deletes directory after test"""
    # Create a temporary working directory
    conf_file, working_dir = _create_temp_work_dir()
    lb = LabBook(conf_file)
    lb.new({"username": "default"}, "labbook1", username="default", description="my first labbook")
    db = ActivityDetailDB(lb.root_dir, lb.checkout_id)

    yield db, lb

    # Remove the temp_dir
    shutil.rmtree(working_dir)


@pytest.fixture()
def mock_labbook():
    """A pytest fixture that creates a temporary directory and a config file to match. Deletes directory after test"""

    conf_file, working_dir = _create_temp_work_dir()
    lb = LabBook(conf_file)
    labbook_dir = lb.new(username="test", name="labbook1", description="my first labbook",
                             owner={"username": "test"})
    yield conf_file, labbook_dir, lb
    shutil.rmtree(working_dir)


@pytest.fixture()
def labbook_dir_tree():
    with tempfile.TemporaryDirectory() as tempdir:

        subdirs = [['.gigantum'],
                   ['.gigantum', 'env'],
                   ['.gigantum', 'env', 'base_image'],
                   ['.gigantum', 'env', 'dev_env'],
                   ['.gigantum', 'env', 'custom'],
                   ['.gigantum', 'env', 'package_manager']]

        for subdir in subdirs:
            os.makedirs(os.path.join(tempdir, "my-temp-labbook", *subdir), exist_ok=True)

        with tempfile.TemporaryDirectory() as checkoutdir:
            repo = git.Repo.clone_from("https://github.com/gig-dev/environment-components-dev.git", checkoutdir)
            shutil.copy(os.path.join(checkoutdir, "base_image/gigantum/ubuntu1604-python3/ubuntu1604-python3-v0_4.yaml"),
                        os.path.join(tempdir, "my-temp-labbook", ".gigantum", "env", "base_image"))
            shutil.copy(os.path.join(checkoutdir, "dev_env/gigantum/jupyter-ubuntu/jupyter-ubuntu-v0_0.yaml"),
                        os.path.join(tempdir, "my-temp-labbook", ".gigantum", "env", "dev_env"))
            shutil.copy(os.path.join(checkoutdir, "custom/gigantum/ubuntu-python3-pillow/ubuntu-python3-pillow-v0_3.yaml"),
                        os.path.join(tempdir, "my-temp-labbook", ".gigantum", "env", "custom"))

        yield os.path.join(tempdir, 'my-temp-labbook')

