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
import docker
import docker.errors
import time
from typing import Optional, List, Tuple, Any, Dict

from lmcommon.configuration import get_docker_client
from lmcommon.logging import LMLogger
from lmcommon.portmap import PortMap
from lmcommon.labbook import LabBook
from lmcommon.container.utils import infer_docker_image_name
from lmcommon.container.exceptions import ContainerBuildException

logger = LMLogger.get_logger()


def get_labmanager_ip() -> Optional[str]:
    """Method to get the monitored lab book container's IP address on the Docker bridge network

    Returns:
        str
    """
    client = get_docker_client()
    container = [c for c in client.containers.list()
                 if 'labmanager' in c.name and 'gigantum' in c.name and 'gmlb-' not in c.name][0]
    ip = container.attrs['NetworkSettings']['Networks']['bridge']['IPAddress']
    logger.info("container {} IP: {}".format(container.name, ip))
    return ip


def get_container_ip(lb_key: str) -> str:
    """Return the IP address of the given labbook container"""
    client = get_docker_client()
    container = client.containers.get(lb_key)
    return container.attrs['NetworkSettings']['Networks']['bridge']['IPAddress']


def build_docker_image(root_dir: str, override_image_tag: Optional[str], nocache: bool = False,
                       username: Optional[str] = None) -> str:
    """
    Build a new docker image from the Dockerfile at the given directory, give this image
    the name defined by the image_name argument.

    Note! This method is static, it should **NOT** use any global variables or any other
    reference to global state.

    Also note - This will delete any existing image pertaining to the given labbook.
    Thus if this call fails, there will be no docker images pertaining to that labbook.

    Args:
        root_dir: LabBook root directory (obtained by LabBook.root_dir)
        override_image_tag: Tag of docker image; in general this should not be explicitly set.
        username: Username of active user.
        nocache: If True do not use docker cache.

    Returns:
        A string container the short docker id of the newly built image.

    Raises:
        ContainerBuildException if container build fails.
    """

    if not os.path.exists(root_dir):
        raise ValueError(f'Expected env directory `{root_dir}` does not exist.')

    env_dir = os.path.join(root_dir, '.gigantum', 'env')
    lb = LabBook()
    lb.from_directory(root_dir)

    # Build image
    image_name = override_image_tag or infer_docker_image_name(labbook_name=lb.name,
                                                               owner=lb.owner['username'],
                                                               username=username)

    # We need to remove any images pertaining to this labbook before triggering a build.
    try:
        get_docker_client().images.get(name=image_name)
        get_docker_client().images.remove(image_name)
    except docker.errors.ImageNotFound:
        pass

    try:
        docker_image = get_docker_client().images.build(path=env_dir, tag=image_name, pull=True, nocache=nocache,
                                                        forcerm=True)
    except docker.errors.BuildError as e:
        raise ContainerBuildException(e)

    return docker_image.short_id.split(':')[1]


def start_labbook_container(labbook_root: str, config_path: str,
                            override_image_id: Optional[str] = None,
                            username: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    """ Start a Docker container from a given image_name.

    Args:
        labbook_root: Root dir of labbook
        config_path: Path to LabBook configuration file.
        override_image_id: Optional explicit docker image id (do not infer).
        username: Username of active user. Do not use with override_image_id.

    Returns:
        Tuple containing docker container id, dict mapping of exposed ports.

    Raises:
    """
    if username and override_image_id:
        raise ValueError('Argument username and override_image_id cannot both be set')

    lb = LabBook(config_path)
    lb.from_directory(labbook_root)
    if not override_image_id:
        tag = infer_docker_image_name(lb.name, lb.owner['username'], username)
    else:
        tag = override_image_id

    # List of tuples where the first entry is the CONTAINER port and second is the desired HOST port
    # TODO - This is the hard-coded ports for JupyterLab. This method should be parameterized
    # with port tuples in the future. (It cannot directly query other top-level modules otherwise
    # a circular dependency will occur)
    opened_ports: List[Tuple] = [(8888, 8890)]

    portmap = PortMap(lb.labmanager_config)
    exposed_ports = {f"{port[0]}/tcp": portmap.assign(lb.key, "0.0.0.0", port[1]) for port in opened_ports}
    mnt_point = labbook_root.replace('/mnt/gigantum', os.environ['HOST_WORK_DIR'])

    volumes_dict = {
        mnt_point: {'bind': '/mnt/labbook', 'mode': 'cached'},
        'labmanager_share_vol': {'bind': '/mnt/share', 'mode': 'rw'}
    }

    # If re-mapping permissions, be sure to configure the container
    if 'LOCAL_USER_ID' in os.environ:
        env_var = [f"LOCAL_USER_ID={os.environ['LOCAL_USER_ID']}"]
    else:
        env_var = ["WINDOWS_HOST=1"]

    # Get resource limits
    resource_args = dict()
    memory_limit = lb.labmanager_config.config['container']['memory']
    cpu_limit = lb.labmanager_config.config['container']['cpu']
    if memory_limit:
        # If memory_limit not None, pass to Docker to limit memory allocation to container
        resource_args["mem_limit"] = memory_limit
    if cpu_limit:
        # If cpu_limit not None, pass to Docker to limit CPU allocation to container
        # "nano_cpus" is an integer in factional parts of a CPU
        resource_args["nano_cpus"] = round(cpu_limit * 1e9)

    docker_client = get_docker_client()
    container_id = docker_client.containers.run(tag, detach=True, init=True, name=tag, ports=exposed_ports,
                                                environment=env_var, volumes=volumes_dict, **resource_args).id

    labmanager_ip = ""
    try:
        labmanager_ip = get_labmanager_ip() or ""
    except IndexError:
        logger.warning("Cannot find labmanager IP")

    labmanager_ip = labmanager_ip.strip()
    cmd = f"echo {labmanager_ip} > /home/giguser/labmanager_ip"
    for timeout in range(20):
        time.sleep(0.5)
        if docker_client.containers.get(container_id).status == 'running':
            r = docker_client.containers.get(container_id).exec_run(f'sh -c "{cmd}"')
            logger.info(f"Response to write labmanager_ip in {tag}: {r}")
            break
    else:
        logger.error("After 10 seconds could not write IP to labmanager container."
                     f" Container status = {docker_client.containers.get(container_id).status}")
    return container_id, exposed_ports


def stop_labbook_container(container_id: str) -> bool:
    """ Stop a running docker container.

    Args:
        container_id: ID of container to stop.

    Returns
        True if stopped, False if it was never running.
    """
    try:
        client = get_docker_client()
        build_container = client.containers.get(container_id)
        build_container.stop(timeout=10)
        build_container.remove()
        return True
    except docker.errors.NotFound:
        # No container to stop, but no reason to throw an exception
        return False
