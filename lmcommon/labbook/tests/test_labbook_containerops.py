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
import tempfile
import os
import shutil
import yaml
import pprint
import getpass
import requests
import time

import git

import lmcommon
from lmcommon.configuration import get_docker_client
from lmcommon.labbook import LabBook, LabbookException
from lmcommon.dispatcher import jobs
from lmcommon.imagebuilder import ImageBuilder
from lmcommon.environment import ComponentManager
from lmcommon.labbook.operations import ContainerOps
from lmcommon.fixtures import (mock_config_file, mock_labbook, mock_config_with_repo,
                               remote_labbook_repo, sample_src_file, ENV_UNIT_TEST_BASE,
                               ENV_UNIT_TEST_REV, ENV_UNIT_TEST_REPO, build_lb_image_for_jupyterlab)


@pytest.mark.skipif(getpass.getuser() == 'circleci', reason="Cannot build images on CircleCI")
class TestContainerOps(object):
    def test_start_jupyterlab(self, build_lb_image_for_jupyterlab):
        container_id = build_lb_image_for_jupyterlab[4]
        docker_image_id = build_lb_image_for_jupyterlab[3]
        client = build_lb_image_for_jupyterlab[2]
        ib = build_lb_image_for_jupyterlab[1]
        lb = build_lb_image_for_jupyterlab[0]

        l = [a for a in client.containers.get(container_id=container_id).exec_run(
            'sh -c "ps aux | grep jupyter | grep -v \' grep \'"', user='giguser').decode().split('\n') if a]
        assert len(l) == 0

        lb, info = ContainerOps.start_dev_tool(labbook=lb, dev_tool_name='jupyterlab', username='test',
                                               tag=docker_image_id)

        l = [a for a in client.containers.get(container_id=container_id).exec_run(
            'sh -c "ps aux | grep jupyter-lab | grep -v \' grep \'"', user='giguser').decode().split('\n') if a]
        assert len(l) == 1

        # Now, we test the second path through, start jupyterlab when it's already running.
        lb, info = ContainerOps.start_dev_tool(labbook=lb, dev_tool_name='jupyterlab', username='test',
                                               tag=docker_image_id)

        # Validate there is only one instance running.
        l = [a for a in client.containers.get(container_id=container_id).exec_run(
            'sh -c "ps aux | grep jupyter-lab | grep -v \' grep \'"', user='giguser').decode().split('\n') if a]
        assert len(l) == 1

    def test_start_container(self, build_lb_image_for_jupyterlab):
        # Check the resulting port mapping to confirm there are some mapped ports in there.
        # At the momoent, I don't know how to connect to these from the driver container.
        # Maybe randal can figure it out.
        r = build_lb_image_for_jupyterlab[6]
        pprint.pprint(f'{r} ({type(r)})')
        assert any(k == '8888/tcp' and r[k] for k in r.keys())
