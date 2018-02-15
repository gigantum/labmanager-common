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

import os
import re
import time
import uuid
from typing import Any, List, Optional, Tuple, Dict

from lmcommon.configuration import get_docker_client, Configuration
from lmcommon.logging import LMLogger
from lmcommon.labbook import LabBook, LabbookException
from lmcommon.portmap import PortMap
from lmcommon.environment import ComponentManager

from lmcommon.container.utils import infer_docker_image_name
from lmcommon.container.core import (build_docker_image, stop_labbook_container,
                                     start_labbook_container)

logger = LMLogger.get_logger()


class ContainerOperations(object):

    @classmethod
    def build_image(cls, labbook: LabBook, override_image_tag: Optional[str] = None,
                    username: Optional[str] = None, nocache: bool = False) -> Tuple[LabBook, str]:
        """ Build docker image according to the Dockerfile just assembled.

        Args:
            labbook: Subject LabBook to build.
            override_image_tag: Tag of docker image
            nocache: Don't user the Docker cache if True
            username: The current logged in username

        Returns:
            A tuple containing the labbook, docker image id.

        Raises:
            Todo.
        """
        logger.info(f"Building docker image for {str(labbook)} using override name `{override_image_tag}`")
        return (labbook,
                build_docker_image(labbook.root_dir, override_image_tag=override_image_tag, username=username,
                                   nocache=nocache))

    @classmethod
    def start_container(cls, labbook: LabBook, username: Optional[str] = None,
                        override_image_tag: Optional[str] = None) -> Tuple[LabBook, str, Dict[Any, Any]]:
        """ Start a Docker container for a given labbook LabBook. Return the new labbook instances
            and a list of TCP port mappings.

            Return list of [(9999, 8888), (7777, 1234)] implies port 9999 on the HOST machine maps
            to 8888 of the labbook container, etc.

        Args:
            labbook: Subject labbook
            username: Optional active username
            override_image_tag: If set, does not automatically infer container name.

        Returns:
            A tuple containing the labbook, Docker container id, and port mapping.
        """
        if not os.environ.get('HOST_WORK_DIR'):
            raise ValueError("Environment variable HOST_WORK_DIR must be set")

        container_id, pmap = start_labbook_container(labbook_root=labbook.root_dir,
                                                     config_path=labbook.labmanager_config.config_file,
                                                     override_image_id=override_image_tag,
                                                     username=username)
        return labbook, container_id, pmap

    @classmethod
    def stop_container(cls, labbook: LabBook, username: Optional[str] = None) -> Tuple[LabBook, bool]:
        """ Stop the given labbook. Returns True in the second field if stopped, otherwise False (False can simply
        imply no container was running).

        Args:
            labbook: Subject labbook
            username: Optional username of active user

        Returns:
            A tuple of (Labbook, boolean indicating whether a container was successfully stopped).
        """
        # Todo - Potentially make container_id optional and query for id of container.

        n = infer_docker_image_name(labbook_name=labbook.name, owner=labbook.owner['username'], username=username)
        logger.info(f"Stopping {str(labbook)} ({n})")

        pm = PortMap(labbook.labmanager_config)
        pm.release(labbook.key)

        return labbook, stop_labbook_container(n)

    @classmethod
    def start_dev_tool(cls, labbook: LabBook, dev_tool_name: str,
                       username: str, tag: Optional[str] = None) -> Tuple[LabBook, str]:
        """ Start a given development tool (e.g., JupyterLab).

        Args:
            labbook: Subject labbook
            dev_tool_name: Name of development tool, only "jupyterlab" is currently allowed.
            username: Username of active LabManager user.
            tag: Tag of Docker container

        Returns:
            (labbook, info): New labbook instance with modified state, info needed to connect to dev tool.
        """
        supported_dev_tools = ['jupyterlab']
        if dev_tool_name not in supported_dev_tools:
            raise LabbookException(f"Development Tool '{dev_tool_name}' not currently supported")

        lb_key = tag or infer_docker_image_name(labbook_name=labbook.name, owner=labbook.owner['username'], username=username)
        docker_client = get_docker_client()

        lb_container = docker_client.containers.get(lb_key)
        if lb_container.status != 'running':
            raise LabbookException(f"{str(labbook)} container is not running")

        jupyter_ps = [l for l in lb_container.exec_run(
            f'sh -c "ps aux | grep \'jupyter lab\' | grep -v \' grep \'"').decode().split('\n') if l]

        if len(jupyter_ps) == 1:
            # If jupyter-lab is already running.
            p = re.search('--port=([\d]+)', jupyter_ps[0])
            if not p:
                raise LabbookException('Cannot detect Jupyter Lab port')
            port = p.groups()[0]
            t = re.search("token='?([a-zA-Z\d-]+)'?", jupyter_ps[0])
            if not t:
                raise LabbookException('Cannot detect Jupyter Lab token')
            token = t.groups()[0]
            return labbook, f'http://0.0.0.0:{port}/lab?token={token}'

        elif len(jupyter_ps) == 0:
            # If jupyter-lab is not already running.
            # Use a random hexadecimal string as token.
            token = str(uuid.uuid4()).replace('-', '')
            cmd = f"jupyter lab --port=8888 --ip=0.0.0.0 " \
                  f"--NotebookApp.token='{token}' --no-browser " \
                  f"--ConnectionFileMixin.ip=0.0.0.0"
            bash = f'sh -c "{cmd}"'
            result = lb_container.exec_run(bash, detach=True, user='giguser')
            # Pause briefly to avoid race conditions
            time.sleep(1)
            new_ps_list = lb_container.exec_run(
                f'sh -c "ps aux | grep jupyter | grep -v \' grep \'"').decode().split('\n')

            time.sleep(1)
            if not any(['jupyter lab' in l or 'jupyter-lab' in l for l in new_ps_list]):
                raise ValueError('Jupyter Lab failed to start')

            pmap = PortMap(labbook.labmanager_config)
            host, port = pmap.lookup(labbook.key)
            tool_url = f'http://{host}:{port}/lab?token={token}'
            logger.info(f"Jupyer Lab up at {tool_url}")
            return labbook, tool_url

        else:
            # If "ps aux" for jupyterlab returns multiple hits - this should never happen.
            for n, l in enumerate(jupyter_ps):
                logger.error(f'Multiple JupyerLab instances - ({n+1} of {len(jupyter_ps)}) - {l}')
            raise ValueError(f'Multiple ({len(jupyter_ps)}) Jupyter Lab instances detected')
