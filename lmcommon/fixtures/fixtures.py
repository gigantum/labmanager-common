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
import docker.errors
import pytest
import pprint

from lmcommon.configuration import Configuration, get_docker_client
from lmcommon.container import ContainerOperations
from lmcommon.environment import RepositoryManager, ComponentManager
from lmcommon.labbook import LabBook
from lmcommon.container import ContainerOperations
from lmcommon.activity.detaildb import ActivityDetailDB
from lmcommon.activity import ActivityStore
from lmcommon.imagebuilder import ImageBuilder
from lmcommon.gitlib.git import GitAuthor


ENV_UNIT_TEST_REPO = 'gig-dev_components2'
ENV_UNIT_TEST_BASE = 'quickstart-jupyterlab'
ENV_UNIT_TEST_REV = 1


def _create_temp_work_dir(override_dict: dict = None, lfs_enabled: bool = True):
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
            #'repo_url': ["https://github.com/gig-dev/environment-components.git"]
            'repo_url': ["https://github.com/gig-dev/components2.git"]
        },
        'flask': {
            'DEBUG': False
        },
        'git': {
            'working_directory': unit_test_working_dir,
            'backend': 'filesystem',
            'lfs_enabled': lfs_enabled
        },
        'auth': {
            'audience': "io.gigantum.api.dev"
        },
        'lock': {
            'redis': {
                'strict': False,
            }
        }
    }

    os.environ['HOST_WORK_DIR'] = unit_test_working_dir

    config = Configuration()
    merge_dict(config.config, default_override_config)
    if override_dict:
        config.config.update(override_dict)

    config_file = os.path.join(unit_test_working_dir, "temp_config.yaml")
    config.save(config_file)

    # Return (path-to-config-file, ephemeral-working-directory).
    return config_file, unit_test_working_dir


def _MOCK_create_remote_repo(self, username: str, access_token = None) -> None:
    """ Used to mock out creating a Labbook remote Gitlab repo. This is not a fixture per se,

    Usage:

    ```
        @mock.patch('lmcommon.labbook.LabBook._create_remote_repo', new=_MOCK_create_remote_repo)
        def my_test_(...):
            ...
    ```
    """
    import tempfile, uuid
    working_dir = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
    os.makedirs(working_dir, exist_ok=True)
    import git
    r = git.Repo.init(path=working_dir, bare=True)
    assert r.bare is True
    self.add_remote(remote_name="origin", url=working_dir)


@pytest.fixture()
def sample_src_file():
    with tempfile.NamedTemporaryFile(mode="w") as sample_f:
        # Fill sample file with some deterministic crap
        sample_f.write("n4%nm4%M435A EF87kn*C" * 40)
        sample_f.seek(0)
        yield sample_f.name


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


@pytest.fixture(scope="module")
def setup_index():
    """A pytest fixture that creates a temporary directory and a config file to match. Deletes directory after test"""
    # Create a temporary working directory

    conf_file, working_dir = _create_temp_work_dir()

    # Run clone and index operation
    erm = RepositoryManager(conf_file)
    erm.update_repositories()
    erm.index_repositories()

    yield erm, working_dir, conf_file  # provide the fixture value

    # Remove the temp_dir
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
def mock_config_file_with_auth_browser():
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
            'identity_manager': 'browser'
        }
    }

    conf_file, working_dir = _create_temp_work_dir(override_dict=overrides)
    yield conf_file, working_dir, auth_data  # provide the fixture value
    shutil.rmtree(working_dir)


@pytest.fixture()
def mock_config_with_activitystore():
    """A pytest fixture that creates a ActivityStore (and labbook) and deletes directory after test"""
    # Create a temporary working directory
    conf_file, working_dir = _create_temp_work_dir()
    lb = LabBook(conf_file, author=GitAuthor("default", "default@test.com"))
    lb.new({"username": "default"}, "labbook1", username="default", description="my first labbook")
    store = ActivityStore(lb)

    yield store, lb

    # Remove the temp_dir
    shutil.rmtree(working_dir)


@pytest.fixture()
def mock_config_with_detaildb():
    """A pytest fixture that creates a detail db (and labbook) and deletes directory after test"""
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
def mock_labbook_lfs_disabled():
    """A pytest fixture that creates a temporary directory and a config file to match. Deletes directory after test"""

    conf_file, working_dir = _create_temp_work_dir(lfs_enabled=False)
    lb = LabBook(conf_file)
    labbook_dir = lb.new(username="test", name="labbook1", description="my first labbook",
                             owner={"username": "test"})
    yield conf_file, labbook_dir, lb
    shutil.rmtree(working_dir)


@pytest.fixture()
def mock_labbook_with_populated_env():
    """A pytest fixture that creates a temporary directory and a config file to match. Deletes directory after test"""

    conf_file, working_dir = _create_temp_work_dir()
    lb = LabBook(conf_file)
    labbook_dir = lb.new(username="test", name="labbook1", description="my first labbook",
                             owner={"username": "test"})
    env = ComponentManager(lb)
    env.add
    yield conf_file, labbook_dir, lb
    shutil.rmtree(working_dir)


@pytest.fixture()
def mock_duplicate_labbook():
    """A pytest fixture that creates a temporary directory and a config file to match. Deletes directory after test"""

    conf_file, working_dir = _create_temp_work_dir()
    lb = LabBook(conf_file)
    labbook_dir = lb.new(username="test", name="labbook1", description="my first labbook",
                             owner={"username": "test"})
    yield conf_file, labbook_dir, lb
    shutil.rmtree(working_dir)


@pytest.fixture()
def remote_labbook_repo():

    # TODO: Remove after integration tests with LFS support are available
    conf_file, working_dir = _create_temp_work_dir(lfs_enabled=False)

    lb = LabBook(conf_file)
    labbook_dir = lb.new(username="test", name="sample-repo-lb", description="my first labbook",
                             owner={"username": "test"})
    lb.checkout_branch("testing-branch", new=True)
    with tempfile.TemporaryDirectory() as tmpdirname:
        with open(os.path.join(tmpdirname, 'codefile.c'), 'wb') as codef:
            codef.write(b'// Cody McCodeface ...')

        lb.insert_file("code", codef.name, "")

    lb.checkout_branch("gm.workspace")

    # Location of the repo to push/pull from
    yield lb.root_dir
    shutil.rmtree(working_dir)


@pytest.fixture()
def remote_bare_repo():
    conf_file, working_dir = _create_temp_work_dir()
    import git
    r = git.Repo.init(path=working_dir, bare=True)
    assert r.bare is True

    yield working_dir
    shutil.rmtree(working_dir)


@pytest.fixture()
def labbook_dir_tree():
    with tempfile.TemporaryDirectory() as tempdir:

        subdirs = [['.gigantum'],
                   ['.gigantum', 'env'],
                   ['.gigantum', 'env', 'base'],
                   ['.gigantum', 'env', 'custom'],
                   ['.gigantum', 'env', 'package_manager']]

        for subdir in subdirs:
            os.makedirs(os.path.join(tempdir, "my-temp-labbook", *subdir), exist_ok=True)

        with tempfile.TemporaryDirectory() as checkoutdir:
            repo = git.Repo.clone_from("https://github.com/gig-dev/components2.git", checkoutdir)
            shutil.copy(os.path.join(checkoutdir, "base/quickstart-jupyterlab/quickstart-jupyterlab_r0.yaml"),
                        os.path.join(tempdir, "my-temp-labbook", ".gigantum", "env", "base"))
            shutil.copy(os.path.join(checkoutdir, "custom/pillow/pillow_r0.yaml"),
                        os.path.join(tempdir, "my-temp-labbook", ".gigantum", "env", "custom"))

        yield os.path.join(tempdir, 'my-temp-labbook')


@pytest.fixture(scope='function')
def build_lb_image_for_jupyterlab(mock_config_with_repo):
    # Create a labook
    lb = LabBook(mock_config_with_repo[0])
    labbook_dir = lb.new(name="containerunittestbook", description="Testing docker building.",
                         owner={"username": "unittester"})
    # Create Component Manager
    cm = ComponentManager(lb)
    # Add a component
    cm.add_component("base", ENV_UNIT_TEST_REPO, ENV_UNIT_TEST_BASE, ENV_UNIT_TEST_REV)
    n = cm.add_package("pip", "requests", "2.18.4")

    ib = ImageBuilder(lb.root_dir)
    docker_lines = ib.assemble_dockerfile(write=True)
    pprint.pprint(docker_lines)
    assert 'RUN pip install requests==2.18.4' in docker_lines
    assert all(['==None' not in l for l in docker_lines.split()])
    assert all(['=None' not in l for l in docker_lines.split()])
    client = get_docker_client()
    client.containers.prune()

    assert os.path.exists(os.path.join(lb.root_dir, '.gigantum', 'env', 'entrypoint.sh'))

    try:
        lb, docker_image_id = ContainerOperations.build_image(labbook=lb, username="unittester")
        lb, container_id, port_maps = ContainerOperations.start_container(lb, username="unittester")

        assert isinstance(container_id, str)
        yield lb, ib, client, docker_image_id, container_id, port_maps

        try:
            _, s = ContainerOperations.stop_container(labbook=lb, username="unittester")
        except docker.errors.APIError:
            client.containers.get(container_id=container_id).stop(timeout=2)
            s = False
    finally:
        shutil.rmtree(lb.root_dir)
        # Stop and remove container if it's still there
        try:
            client.containers.get(container_id=container_id).stop(timeout=2)
            client.containers.get(container_id=container_id).remove()
        except:
            pass

        ContainerOperations.delete_image(labbook=lb, username='unittester')

        # Remove image if it's still there
        try:
            client.images.remove(docker_image_id, force=True, noprune=False)
        except:
            pass
