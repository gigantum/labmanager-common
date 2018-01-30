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

import requests

from lmcommon.configuration import get_docker_client, Configuration
from lmcommon.logging import LMLogger
from lmcommon.labbook import LabBook, LabbookException
from lmcommon.dispatcher import Dispatcher, jobs
from lmcommon.portmap import PortMap
from lmcommon.imagebuilder.imagebuilder import dockerize_path
from lmcommon.environment import ComponentManager
logger = LMLogger.get_logger()


class ContainerOps(object):
    @classmethod
    def start_container(cls, labbook: LabBook, username: Optional[str] = None,
                        override_docker_image: Optional[str] = None,
                        background: bool = False) -> Tuple[LabBook, Dict[str, Optional[str]], Dict[str, Any]]:
        """ Start a Docker container for a given labbook LabBook. Return the new labbook instances
            and a list of TCP port mappings.

            Return list of [(9999, 8888), (7777, 1234)] implies port 9999 on the HOST machine maps
            to 8888 of the labbook container, etc.

        Args:
            labbook: Subject labbook
            override_docker_image: If set, does not automatically infer container name.
            background: If True run this in the background using the dispatcher

        Returns:
            A tuple containing (LabBook, Key Info, Port Maps), where Key Info is a dict containing
            the keys docker_container_id (if background is False) or background_job_key (if background is True).
            Port Maps contains the port mappings in docker format.
            """
        if not os.environ.get('HOST_WORK_DIR'):
            raise ValueError("Environment variable HOST_WORK_DIR must be set")

        if not override_docker_image:
            labbook_docker_id = f'gmlb-{username or str(uuid.uuid4())[:4]}-{labbook.owner}-{labbook.name}'
        else:
            labbook_docker_id = override_docker_image

        opened_ports: List[int] = []
        env_manager = ComponentManager(labbook)
        if 'jupyterlab' in env_manager.base_fields['development_tools']:
            opened_ports = [8888]

        portmap = PortMap(labbook.labmanager_config)
        exposed_ports = {f"{port}/tcp": portmap.assign(labbook.key, "0.0.0.0", port) for port in opened_ports}
        mnt_point = dockerize_path(labbook.root_dir.replace('/mnt/gigantum', os.environ['HOST_WORK_DIR']))

        # Map volumes - The labbook docker container is unaware of labbook name, all labbooks
        # map to /mnt/labbook.
        volumes_dict = {
            mnt_point: {'bind': '/mnt/labbook', 'mode': 'cached'},
            'labmanager_share_vol':  {'bind': '/mnt/share', 'mode': 'rw'}
        }

        # If re-mapping permissions, be sure to configure the container
        if 'LOCAL_USER_ID' in os.environ:
            env_var = ["LOCAL_USER_ID={}".format(os.environ['LOCAL_USER_ID'])]
            logger.info("Starting labbook container with user: {}".format(env_var))
        else:
            env_var = ["WINDOWS_HOST=1"]

        return_keys: Dict[str, Optional[str]] = {
            'background_job_key': None,
            'docker_container_id': None
        }

        # Finally, run the image in a container.
        logger.info(
            "Running container id {} -- ports {} -- volumes {}".format(labbook_docker_id, ', '.join(exposed_ports.keys()),
                                                                       ', '.join(volumes_dict.keys())))

        if background:
            logger.info(f"Launching container in background for container {labbook_docker_id}")
            job_dispatcher = Dispatcher()
            # FIXME XXX TODO -- Note that labbook.user throws an excpetion, so putting in labbook.owner for now
            job_metadata = {'labbook': '{}-{}-{}'.format(labbook.owner, labbook.owner, labbook.name),
                            'method': 'run_container'}

            try:
                key = job_dispatcher.dispatch_task(jobs.start_docker_container,
                                                   args=(labbook_docker_id, exposed_ports, volumes_dict, env_var),
                                                   metadata=job_metadata)
            except Exception as e:
                logger.exception(e, exc_info=True)
                raise

            logger.info(f"Background job key for run_container: {key}")
            return_keys['background_job_key'] = key.key_str
        else:
            logger.info("Launching container in-process for container {}".format(labbook_docker_id))
            docker_client = get_docker_client()
            if float(docker_client.version()['ApiVersion']) < 1.25:
                container = docker_client.containers.run(labbook_docker_id,
                                                         detach=True,
                                                         name=labbook_docker_id,
                                                         ports=exposed_ports,
                                                         environment=env_var,
                                                         volumes=volumes_dict)
            else:
                container = docker_client.containers.run(labbook_docker_id,
                                                         detach=True,
                                                         init=True,
                                                         name=labbook_docker_id,
                                                         ports=exposed_ports,
                                                         environment=env_var,
                                                         volumes=volumes_dict)
            # Brief pause to prevent certain race conditions.
            time.sleep(1)
            return_keys['docker_container_id'] = container.id

        return labbook, return_keys, exposed_ports

    @classmethod
    def start_dev_tool(cls, labbook: LabBook, dev_tool_name: str,
                       username: str, tag: Optional[str] = None) -> Tuple[LabBook, str]:
        """Start a given development tool (e.g., JupyterLab).

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

        lb_key = f"{username}-{labbook.owner['username']}-{labbook.name}" if not tag else tag
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
            print(jupyter_ps[0])
            if not t:
                raise LabbookException('Cannot detect Jupyter Lab token')
            token = t.groups()[0]
            return labbook, f'http://localhost:{port}/lab?token={token}'

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
