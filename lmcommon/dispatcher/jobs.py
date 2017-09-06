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
import time
import sys
import os

from docker.errors import NotFound

from lmcommon.configuration import get_docker_client
from lmcommon.logging import LMLogger

# PLEASE NOTE -- No global variables!
#
# None of the following methods can use global variables.
# ANY use of globals will cause the following methods to fail.


def build_docker_image(path, tag, pull, nocache) -> str:
    """Return a dictionary of metadata pertaining to the given task's Redis key.

    Args:
        path(str): Pass-through arg to directory containing Dockerfile.
        tag(str): Pass-through arg to tag of docker image.
        pull(bool): Pass-through arg for docker build.
        nocache(bool): Pass-through arg to docker build.

    Returns:
        Docker image ID
    """

    logger = LMLogger.get_logger()
    logger.info("Starting build_docker_image in pid {}".format(os.getpid()))

    try:
        docker_client = get_docker_client()
        docker_image = docker_client.images.build(path=path, tag=tag, pull=pull, nocache=nocache)
        logger.info("Completed build_docker_image in pid {}: {}".format(os.getpid(), str(docker_image)))
        return docker_image.id
    except Exception as e:
        logger.error("Error on build_docker_image in pid {}: {}".format(os.getpid(), e))
        raise


def start_docker_container(docker_image_id, exposed_ports, volumes_dict) -> str:
    """Return a dictionary of metadata pertaining to the given task's Redis key.

    Args:
        docker_image_id(str): Name of docker image to launch into container
        exposed_ports(dict): Dictionary mapping of exposed ports - pass through to docker container run
        volumes_dict(bool): Dictionary of mapped directories between guest and host -- pass through to docker run.

    Returns:
        Docker container desc
    """

    logger = LMLogger.get_logger()
    logger.info("Starting launch_docker_image({}) in pid {}".format(docker_image_id, os.getpid()))

    try:
        docker_client = get_docker_client()

        try:
            # Note: We might need to consider using force in c.remove(), but for now we decided against it
            # because force will stop a running container. If the user has unsaved work this could be bad.
            # Since the stop mutation stops and removes the container, under normal operation you
            # shouldn't have to force a start.
            c = docker_client.containers.get(docker_image_id)
            c.remove()
            logger.warning(
                "Warning in pid {}: Removed existing container by name `{}`".format(os.getpid(), docker_image_id))
        except NotFound:
            logger.info("In pid {}: No existing image `{}` to force delete. This is nominal.".format(os.getpid(),
                                                                                                     docker_image_id))

        img = docker_client.images.get(docker_image_id)
        if float(docker_client.version()['ApiVersion']) < 1.25:
            container = docker_client.containers.run(img,
                                                     detach=True,
                                                     name=docker_image_id,
                                                     ports=exposed_ports,
                                                     volumes=volumes_dict)
        else:
            docker_client.containers.prune()
            container = docker_client.containers.run(img,
                                                     detach=True,
                                                     init=True,
                                                     name=docker_image_id,
                                                     ports=exposed_ports,
                                                     volumes=volumes_dict)
        logger.info("Completed launch_docker_container in pid {}: {}".format(os.getpid(), str(container)))
        return str(container)
    except Exception as e:
        logger.error("Error on launch_docker_container in pid {}: {}".format(os.getpid(), e))
        raise


def stop_docker_container(image_tag):
    """Return a dictionary of metadata pertaining to the given task's Redis key.

    Args:
        image_tag(str): Container to stop

    Returns:
        0 to indicate no failure
    """

    logger = LMLogger.get_logger()
    logger.info("Starting stop_docker_container in pid {}".format(os.getpid()))

    try:
        docker_client = get_docker_client()
        container = docker_client.containers.get(image_tag)
        container.stop()
        container.remove()
        logger.info("Completed stop_docker_container in pid {}: {}".format(os.getpid(), str(container)))
        return 0
    except Exception as e:
        logger.error("Error on stop_docker_container in pid {}: {}".format(os.getpid(), e))
        raise


def index_labbook_filesystem():
    """To be implemented later. """
    raise NotImplemented


def test_exit_success():
    """Used only for testing -- vacuous method to always succeed and return 0. """
    return 0


def test_exit_fail():
    """Used only for testing -- always throws an exception"""
    raise Exception("Intentional Exception from job `test_exit_fail`")


def test_sleep(n):
    """Used only for testing -- example method with argument. """
    logger = LMLogger.get_logger()
    logger.info("Starting test_sleep({}) in pid {}".format(n, os.getpid()))

    try:
        time.sleep(n)
        logger.info("Completed test_sleep in pid {}".format(os.getpid()))
        return 0
    except Exception as e:
        logger.error("Error on test_sleep in pid {}: {}".format(os.getpid(), e))
        raise
