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
import os
import shutil
import docker.errors
import pytest
import pprint

from lmcommon.configuration import get_docker_client
from lmcommon.container.container import ContainerOperations
from lmcommon.environment import ComponentManager
from lmcommon.labbook import LabBook
from lmcommon.imagebuilder import ImageBuilder
from lmcommon.fixtures.fixtures import mock_config_with_repo, ENV_UNIT_TEST_REPO, ENV_UNIT_TEST_BASE, ENV_UNIT_TEST_REV

# TODO: This should be update to the latest version of requests, and probably automated in the future
REQUESTS_LATEST_VERSION = "2.19.1"


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
    cm.add_packages("pip", [{"manager": "pip", "package": "requests", "version": "2.18.4"}])

    ib = ImageBuilder(lb)
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
        lb, container_id = ContainerOperations.start_container(lb, username="unittester")

        assert isinstance(container_id, str)
        yield lb, ib, client, docker_image_id, container_id, None, 'unittester'

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

        # Remove image if it's still there
        try:
            ContainerOperations.delete_image(labbook=lb, username='unittester')
            client.images.remove(docker_image_id, force=True, noprune=False)
        except:
            pass

        try:
            client.images.remove(docker_image_id, force=True, noprune=False)
        except:
            pass


@pytest.fixture(scope='class')
def build_lb_image_for_env(mock_config_with_repo):
    # Create a labook
    lb = LabBook(mock_config_with_repo[0])
    labbook_dir = lb.new(name="containerunittestbookenv", description="Testing environment functions.",
                         owner={"username": "unittester"})
    # Create Component Manager
    cm = ComponentManager(lb)
    # Add a component
    cm.add_component("base", ENV_UNIT_TEST_REPO, ENV_UNIT_TEST_BASE, ENV_UNIT_TEST_REV)

    ib = ImageBuilder(lb)
    ib.assemble_dockerfile(write=True)
    client = get_docker_client()
    client.containers.prune()

    try:
        lb, docker_image_id = ContainerOperations.build_image(labbook=lb, username="unittester")

        yield lb, 'unittester'

    finally:
        shutil.rmtree(lb.root_dir)

        # Remove image if it's still there
        try:
            client.images.remove(docker_image_id, force=True, noprune=False)
        except:
            pass


@pytest.fixture(scope='class')
def build_lb_image_for_env_conda(mock_config_with_repo):
    """A fixture that installs an old version of matplotlib and latest version of requests to increase code coverage"""
    lb = LabBook(mock_config_with_repo[0])
    labbook_dir = lb.new(name="containerunittestbookenvconda", description="Testing environment functions.",
                         owner={"username": "unittester"})
    cm = ComponentManager(lb)
    cm.add_component("base", ENV_UNIT_TEST_REPO, ENV_UNIT_TEST_BASE, ENV_UNIT_TEST_REV)
    cm.add_packages('conda3', [{'package': 'matplotlib', 'version': '2.0.0'},
                               {'package': 'requests', 'version': REQUESTS_LATEST_VERSION}])

    ib = ImageBuilder(lb)
    ib.assemble_dockerfile(write=True)
    client = get_docker_client()
    client.containers.prune()

    try:
        lb, docker_image_id = ContainerOperations.build_image(labbook=lb, username="unittester")

        yield lb, 'unittester'

    finally:
        shutil.rmtree(lb.root_dir)
        try:
            client.images.remove(docker_image_id, force=True, noprune=False)
        except:
            pass