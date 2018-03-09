# Copyright (c) 2018 FlashX, LLC
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
import pprint
import getpass
import docker
import requests

from lmcommon.configuration import get_docker_client

from lmcommon.container import ContainerOperations
from lmcommon.container.utils import infer_docker_image_name
from lmcommon.fixtures import build_lb_image_for_jupyterlab, mock_config_with_repo
from lmcommon.container.exceptions import ContainerBuildException


class TestContainerOps(object):
    def test_build_image_fixture(self, build_lb_image_for_jupyterlab):
        # Note, the test is in the fixure (the fixture is needed by other tests around here).
        pass

    def test_start_jupyterlab(self, build_lb_image_for_jupyterlab):
        container_id = build_lb_image_for_jupyterlab[4]
        docker_image_id = build_lb_image_for_jupyterlab[3]
        client = build_lb_image_for_jupyterlab[2]
        ib = build_lb_image_for_jupyterlab[1]
        lb = build_lb_image_for_jupyterlab[0]

        l = [a for a in client.containers.get(container_id=container_id).exec_run(
            'sh -c "ps aux | grep jupyter | grep -v \' grep \'"', user='giguser').decode().split('\n') if a]
        assert len(l) == 0

        lb, info = ContainerOperations.start_dev_tool(labbook=lb, dev_tool_name='jupyterlab', username='unittester',
                                                      check_reachable=not (getpass.getuser() == 'circleci'))

        l = [a for a in client.containers.get(container_id=container_id).exec_run(
            'sh -c "ps aux | grep jupyter-lab | grep -v \' grep \'"', user='giguser').decode().split('\n') if a]
        assert len(l) == 1

        # Now, we test the second path through, start jupyterlab when it's already running.
        lb, info = ContainerOperations.start_dev_tool(labbook=lb, dev_tool_name='jupyterlab', username='unittester')

        # Validate there is only one instance running.
        l = [a for a in client.containers.get(container_id=container_id).exec_run(
            'sh -c "ps aux | grep jupyter-lab | grep -v \' grep \'"', user='giguser').decode().split('\n') if a]
        assert len(l) == 1

    def test_start_container(self, build_lb_image_for_jupyterlab):
        # Check the resulting port mapping to confirm there are some mapped ports in there.
        # At the moment, I don't know how to connect to these from the driver container.
        # Maybe randal can figure it out.
        r = build_lb_image_for_jupyterlab[5]
        pprint.pprint(f'{r} ({type(r)})')
        assert any(k == '8888/tcp' and r[k] for k in r.keys())

    def test_old_dockerfile_removed_when_new_build_fails(self, build_lb_image_for_jupyterlab):
        # Test that when a new build fails, old images are removed so they cannot be launched.
        my_lb = build_lb_image_for_jupyterlab[0]
        docker_image_id = build_lb_image_for_jupyterlab[3]

        my_lb, stopped = ContainerOperations.stop_container(my_lb, username="unittester")

        assert stopped

        olines = open(os.path.join(my_lb.root_dir, '.gigantum/env/Dockerfile')).readlines()[:6]
        with open(os.path.join(my_lb.root_dir, '.gigantum/env/Dockerfile'), 'w') as dockerfile:
            dockerfile.write('\n'.join(olines))
            dockerfile.write('\nRUN /bin/false')

        with pytest.raises(ContainerBuildException):
            ContainerOperations.build_image(labbook=my_lb, username="unittester")

        with pytest.raises(docker.errors.ImageNotFound):
            get_docker_client().images.get(infer_docker_image_name(labbook_name=my_lb.name, owner=my_lb.owner['username'],
                                                      username="unittester"))

        with pytest.raises(requests.exceptions.HTTPError):
            # Image not found so container cannot be started
            ContainerOperations.start_container(labbook=my_lb, username="unittester")