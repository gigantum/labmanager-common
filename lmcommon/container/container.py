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
import confhttpproxy

from lmcommon.configuration import get_docker_client, Configuration
from lmcommon.logging import LMLogger
from lmcommon.labbook import LabBook, LabbookException
from lmcommon.portmap import PortMap

from lmcommon.container.utils import infer_docker_image_name
from lmcommon.container.exceptions import ContainerException
from lmcommon.container.core import (build_docker_image, stop_labbook_container,
                                     start_labbook_container, get_container_ip)
from lmcommon.container.jupyter import start_jupyter

logger = LMLogger.get_logger()


class ContainerOperations(object):

    @classmethod
    def build_image(
            cls, labbook: LabBook, override_image_tag: Optional[str] = None,
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
        logger.info(f"Building docker image for {str(labbook)}, "
                    f"using override name `{override_image_tag}`")
        docker_img_id = build_docker_image(labbook.root_dir,
                                           override_image_tag=override_image_tag,
                                           username=username,
                                           nocache=nocache)
        return labbook, docker_img_id

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
    def run_command(
            cls, cmd_text: str, labbook: LabBook, username: Optional[str] = None,
            override_image_tag: Optional[str] = None, fallback_image: str = None) -> bytes:
        """Run a command executed in the context of the LabBook's docker image.

        Args:
            cmd_text: Content of command to be executed.
            labbook: Subject labbook
            username: Optional active username
            override_image_tag: If set, does not automatically infer container name.
            fallback_image: If LabBook image can't be found, use this one instead.

        Returns:
            A tuple containing the labbook, Docker container id, and port mapping.
        """
        image_name = override_image_tag
        if not image_name:
            image_name = infer_docker_image_name(labbook_name=labbook.name,
                                                 owner=labbook.owner['username'],
                                                 username=username)
        # Get a docker client instance
        client = get_docker_client()

        # Verify image name exists. If it doesn't, fallback and use the base image
        try:
            client.images.get(image_name)
        except docker.errors.ImageNotFound:
            # Image not found...assume build has failed and fallback to base
            if not fallback_image:
                raise
            logger.warning(f"LabBook image not available for package query."
                           f"Falling back to base image `{fallback_image}`.")
            image_name = fallback_image

        t0 = time.time()
        try:
            # Note, for container docs see: http://docker-py.readthedocs.io/en/stable/containers.html
            container = client.containers.run(image_name, cmd_text, entrypoint=[], remove=False, detach=True,
                                              stdout=True)
            while container.status != "exited":
                time.sleep(.25)
                container.reload()
            result = container.logs(stdout=True, stderr=False)
            container.remove(v=True)

        except docker.errors.ContainerError as e:
            tfail = time.time()
            logger.error(f'Command ({cmd_text}) failed after {tfail-t0}s - '
                         f'output: {e.exit_status}, {e.stderr}')
            raise ContainerException(e)

        ts = time.time()
        if ts - t0 > 5.0:
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
        """ Stop the given labbook. Returns True in the second field if stopped,
            otherwise False (False can simply imply no container was running).

        Args:
            labbook: Subject labbook
            username: Optional username of active user

        Returns:
            A tuple of (Labbook, boolean indicating whether a container was successfully stopped).
        """
        # TODO - Potentially make container_id optional and query for id of container.
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
    def get_labbook_ip(cls, labbook: LabBook, username: str) -> Tuple[str, int]:
        """Return the IP on the docker network of the LabBook container

        Args:
            labbook: Subject LabBook
            username: Username of active user

        Returns:
            Tuple of externally facing IP and port
        """
        docker_key = infer_docker_image_name(labbook_name=labbook.name,
                                             owner=labbook.owner['username'],
                                             username=username)
        extport = PortMap(labbook.labmanager_config).lookup(labbook.key)[1]
        return get_container_ip(docker_key), extport

    @classmethod
    def start_dev_tool(
            cls, labbook: LabBook, dev_tool_name: str, username: str,
            tag: Optional[str] = None, check_reachable: bool = True,
            proxy_prefix: Optional[str] = None) -> Tuple[LabBook, str]:
        """ Start a given development tool (e.g., JupyterLab).

        Args:
            labbook: Subject labbook
            dev_tool_name: Name of development tool, only "jupyterlab" is currently allowed.
            username: Username of active LabManager user.
            tag: Tag of Docker container
            check_reachable: Affirm that dev tool launched and is reachable
            proxy_prefix: Give proxy route to IDE endpoint if needed

        Returns:
            (labbook, info): New labbook instance with modified state,
                             resource suffix needed to connect to dev tool.
                             (e.g., "/lab?token=xyz" -- it is the caller's
                             responsibility to know the host)
        """
        # A dictionary of dev tools and the port IN THE CONTAINER
        supported_dev_tools = ['jupyterlab']
        if dev_tool_name not in supported_dev_tools:
            raise LabbookException(f"'{dev_tool_name}' not currently supported")
        suffix = start_jupyter(labbook, username, tag, check_reachable,
                               proxy_prefix)
        return labbook, suffix
