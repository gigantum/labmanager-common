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
import redis
import requests
import docker
import docker.errors


from lmcommon.configuration import get_docker_client, Configuration
from lmcommon.logging import LMLogger
from lmcommon.labbook import LabBook, LabbookException
from lmcommon.portmap import PortMap
from lmcommon.environment.componentmanager import ComponentManager

from lmcommon.container.utils import infer_docker_image_name
from lmcommon.container.exceptions import ContainerException
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
    def delete_image(cls, labbook: LabBook, override_image_tag: Optional[str] = None,
                    username: Optional[str] = None) -> Tuple[LabBook, bool]:
        """ Delete the Docker image for the given LabBook

        Args:
            labbook: Subject LabBook.
            override_image_tag: Tag of docker image (optional)
            username: The current logged in username

        Returns:
            A tuple containing the labbook, docker image id.

        Raises:
            Todo.
        """
        image_name = override_image_tag or infer_docker_image_name(labbook_name=labbook.name,
                                                                   owner=labbook.owner['username'],
                                                                   username=username)
        # We need to remove any images pertaining to this labbook before triggering a build.
        try:
            get_docker_client().images.get(name=image_name)
            get_docker_client().images.remove(image_name)
        except docker.errors.ImageNotFound:
            pass
        except Exception as e:
            logger.error("Error deleting docker images for {str(lb)}: {e}")
            return labbook, False
        return labbook, True

    @classmethod
    def run_command(cls, cmd_text: str, labbook: LabBook, username: Optional[str] = None,
                    override_image_tag: Optional[str] = None) -> bytes:
        """Run a command executed in the context of the LabBook's docker image.

        Args:
            labbook: Subject labbook
            username: Optional active username
            override_image_tag: If set, does not automatically infer container name.

        Returns:
            A tuple containing the labbook, Docker container id, and port mapping.
        """
        image_name = override_image_tag or infer_docker_image_name(labbook_name=labbook.name,
                                                                   owner=labbook.owner['username'],
                                                                   username=username)
        # Get a docker client instance
        client = get_docker_client()

        # Verify image name exists. If it doesn't, fallback and use the base image
        try:
            client.images.get(image_name)
        except docker.errors.ImageNotFound:
            # Image not found...assume build has failed and fallback to base
            logger.warning("LabBook image not available for package query. Falling back to base image.")
            cm = ComponentManager(labbook)
            base = cm.base_fields
            image_name = f"{base['image']['namespace']}/{base['image']['repository']}:{base['image']['tag']}"

        t0 = time.time()
        try:
            # Note, for container docs see: http://docker-py.readthedocs.io/en/stable/containers.html
            result = client.containers.run(image_name, cmd_text, entrypoint=[], remove=True)
        except docker.errors.ContainerError as e:
            tfail = time.time()
            logger.error(f'Command ({cmd_text}) failed after {tfail-t0}s - '
                         f'output: {e.exit_status}, {e.stderr}')
            raise ContainerException(e)

        ts = time.time()
        if ts - t0 > 3.0:
            logger.warning(f'Command ({cmd_text}) in {str(labbook)} took {ts-t0} sec')

        return result

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

        try:
            stopped = stop_labbook_container(n)
        finally:
            # Save state of LB when container turned off.
            with labbook.lock_labbook():
                labbook.sweep_uncommitted_changes()

        return labbook, stopped

    @classmethod
    def start_dev_tool(cls, labbook: LabBook, dev_tool_name: str,
                       username: str, tag: Optional[str] = None,
                       check_reachable: bool = True) -> Tuple[LabBook, str]:
        """ Start a given development tool (e.g., JupyterLab).

        Args:
            labbook: Subject labbook
            dev_tool_name: Name of development tool, only "jupyterlab" is currently allowed.
            username: Username of active LabManager user.
            tag: Tag of Docker container

        Returns:
            (labbook, info): New labbook instance with modified state, info needed to connect to dev tool.
        """
        # A dictionary of dev tools and the port at which they run IN THE CONTAINER
        supported_dev_tools = {'jupyterlab': 8888}

        if dev_tool_name not in supported_dev_tools:
            raise LabbookException(f"Development Tool '{dev_tool_name}' not currently supported")

        lb_key = tag or infer_docker_image_name(labbook_name=labbook.name, owner=labbook.owner['username'],
                                                username=username)
        docker_client = get_docker_client()

        lb_container = docker_client.containers.get(lb_key)
        if lb_container.status != 'running':
            raise LabbookException(f"{str(labbook)} container is not running")

        jupyter_ps = [l for l in lb_container.exec_run(
            f'sh -c "ps aux | grep \'jupyter lab\' | grep -v \' grep \'"').decode().split('\n') if l]

        if len(jupyter_ps) == 1:
            # If jupyterlab is already running, get port from portmap store
            pmap = PortMap(labbook.labmanager_config)
            host, port = pmap.lookup(labbook.key)

            # Get token from PS in container
            t = re.search("token='?([a-zA-Z\d-]+)'?", jupyter_ps[0])
            if not t:
                raise LabbookException('Cannot detect Jupyter Lab token')
            token = t.groups()[0]

            return labbook, f'http://{host}:{port}/lab?token={token}'

        elif len(jupyter_ps) == 0:
            # If jupyterlab is not already running.
            # Use a random hexadecimal string as token.
            token = str(uuid.uuid4()).replace('-', '')
            un = labbook.owner['username']
            cmd = (f"export PYTHONPATH=/mnt/share:$PYTHONPATH && "
                  f'echo "{username},{un},{labbook.name},{token}" > /home/giguser/jupyter_token && '
                  f"cd /mnt/labbook && "
                  f"jupyter lab --port={supported_dev_tools[dev_tool_name]} --ip=0.0.0.0 "
                  f"--NotebookApp.token='{token}' --no-browser "
                  f'--ConnectionFileMixin.ip=0.0.0.0 ' +
                  (f'--FileContentsManager.post_save_hook="jupyterhooks.post_save_hook"'
                    if os.path.exists('/mnt/share/jupyterhooks') else ""))
            bash = f'sh -c "{cmd}"'
            logger.info(cmd)
            lb_container.exec_run(bash, detach=True, user='giguser')
            # Pause briefly to avoid race conditions
            for timeout in range(10):
                time.sleep(1)
                new_ps_list = lb_container.exec_run(
                    f'sh -c "ps aux | grep jupyter | grep -v \' grep \'"').decode().split('\n')
                if any(['jupyter lab' in l or 'jupyter-lab' in l for l in new_ps_list]):
                    logger.info(f"JupyterLab started within {timeout + 1} seconds")
                    break
            else:
                raise ValueError('Jupyter Lab failed to start after 10 seconds')

            pmap = PortMap(labbook.labmanager_config)
            host, port = pmap.lookup(labbook.key)
            tool_url = f'http://{host}:{port}/lab?token={token}'

            # Store token in redis (activity data is stored in db1) for later activity monitoring
            redis_conn = redis.Redis(db=1)
            redis_conn.set(f"{lb_key}-jupyter-token", token)

            if check_reachable:
                for n in range(30):
                    # Get IP of container on Docker Bridge Network
                    client = get_docker_client()
                    container = client.containers.get(lb_key)
                    lb_ip_addr = container.attrs['NetworkSettings']['Networks']['bridge']['IPAddress']

                    test_url = f'http://{lb_ip_addr}:{supported_dev_tools[dev_tool_name]}/lab?token={token}'
                    logger.debug(f"Attempt {n + 1}: Testing if JupyerLab is up at {test_url}...")
                    try:
                        r = requests.get(test_url, timeout=0.5)

                        if r.status_code != 200:
                            time.sleep(0.5)
                        else:
                            logger.info(f'Found JupyterLab up at {tool_url} after {n/2.0} seconds')
                            break

                    except requests.exceptions.ConnectionError:
                        # Assume API isn't up at all yet, so no connection can be made
                        time.sleep(0.5)
                else:
                    raise LabbookException(f'Could not reach JupyterLab at {tool_url} after timeout')

            logger.info(f"JupyterLab up at {tool_url}")
            return labbook, tool_url

        else:
            # If "ps aux" for jupyterlab returns multiple hits - this should never happen.
            for n, l in enumerate(jupyter_ps):
                logger.error(f'Multiple JupyerLab instances - ({n+1} of {len(jupyter_ps)}) - {l}')
            raise ValueError(f'Multiple ({len(jupyter_ps)}) Jupyter Lab instances detected')
