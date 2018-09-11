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
import hashlib
import time
import json
from typing import Callable, Optional

from lmcommon.configuration import get_docker_client
from lmcommon.logging import LMLogger
from lmcommon.labbook import LabBook
from lmcommon.container.utils import infer_docker_image_name
from lmcommon.container.exceptions import ContainerBuildException

logger = LMLogger.get_logger()


def get_labmanager_ip() -> Optional[str]:
    """Method to get the monitored lab book container's IP address on the Docker bridge network

    Returns:
        str of IP address
    """
    client = get_docker_client()
    container = [c for c in client.containers.list() if 'gigantum.labmanager' in c.name and 'gmlb-' not in c.name][0]
    ip = container.attrs['NetworkSettings']['Networks']['bridge']['IPAddress']
    logger.info("container {} IP: {}".format(container.name, ip))
    return ip


def get_container_ip(lb_key: str) -> str:
    """Return the IP address of the given labbook container"""
    client = get_docker_client()
    container = client.containers.get(lb_key)
    return container.attrs['NetworkSettings']['Networks']['bridge']['IPAddress']


def _get_cached_image(env_dir: str, image_name: str) -> Optional[str]:
    """
    Get Docker image id for the given environment specification (if it exsits).

    This helps to determine if we can avoid having to rebuild the Docker image
    by hashing the environemnt specification and determine if it changed. Any
    change in content or version will cause the checksum to be different,
    necessitating a rebuild. If there's no change, however, we can avoid potentially
    costly rebuilds of the image.

    Args:
        env_dir: Environment directoryt for a LabBook
        image_name: Name of the LabBook Docker image

    Returns:
        docker image id (Optional)
    """
    # Determine if we need to rebuild by testing if the environment changed
    cache_dir = '/mnt/gigantum/.labmanager/image-cache'
    if not os.path.exists(cache_dir):
        logger.info(f"Making environment cache at {cache_dir}")
        os.makedirs(cache_dir, exist_ok=True)
    env_cache_path = os.path.join(cache_dir, f"{image_name}.cache")

    m = hashlib.sha256()
    for root, dirs, files in os.walk(env_dir):
        for f in [n for n in files if '.yaml' in n]:
            m.update(os.path.join(root, f).encode())
            m.update(open(os.path.join(root, f)).read().encode())
    env_cksum = m.hexdigest()

    if os.path.exists(env_cache_path):
        old_env_cksum = open(env_cache_path).read()
    else:
        with open(env_cache_path, 'w') as cfile:
            cfile.write(env_cksum)
        return None

    if env_cksum == old_env_cksum:
        try:
            i = get_docker_client().images.get(name=image_name)
            return i.id
        except docker.errors.ImageNotFound:
            pass
    else:
        # Env checksum hash is outdated. Remove it.
        os.remove(env_cache_path)
        with open(env_cache_path, 'w') as cfile:
            cfile.write(env_cksum)
    return None


def _remove_docker_image(image_name: str) -> None:
    try:
        get_docker_client().images.get(name=image_name)
        get_docker_client().images.remove(image_name)
    except docker.errors.ImageNotFound:
        logger.warning(f"Attempted to delete Docker image {image_name}, but not found")


def build_docker_image(root_dir: str, override_image_tag: Optional[str], nocache: bool = False,
                       username: Optional[str] = None, feedback_callback: Optional[Callable] = None) -> str:
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
        feedback_callback: Optional method taking one argument (a string) to process each line of output

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

    reuse_image_id = _get_cached_image(env_dir, image_name)
    if reuse_image_id:
        logger.info(f"Reusing Docker image for {str(lb)}")
        if feedback_callback:
            feedback_callback(f"Using cached image {reuse_image_id}")
        return reuse_image_id

    try:
        image_id = None
        # From: https://docker-py.readthedocs.io/en/stable/api.html#docker.api.build.BuildApiMixin.build
        # This builds the image and generates output status text.
        for line in docker.from_env().api.build(path=env_dir, tag=image_name, pull=True, nocache=nocache, forcerm=True):
            ldict = json.loads(line)
            stream = (ldict.get("stream") or "").strip()
            if feedback_callback:
                feedback_callback(stream)
            status = (ldict.get("status") or "").strip()
            if feedback_callback:
                feedback_callback(status)

            if 'Successfully built'.lower() in stream.lower():
                # When build, final line is in form of "Successfully build 02faas3"
                # There is no other (simple) way to grab the image ID
                image_id = stream.split(' ')[-1]
    except docker.errors.BuildError as e:
        _remove_docker_image(image_name)
        raise ContainerBuildException(e)

    if not image_id:
        _remove_docker_image(image_name)
        raise ContainerBuildException(f"Cannot determine docker image on LabBook from {root_dir}")

    return image_id


def start_labbook_container(labbook_root: str, config_path: str,
                            override_image_id: Optional[str] = None,
                            username: Optional[str] = None) -> str:
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

    # run with nvidia if we have GPU support in the labmanager 
    # CUDA must be set (not None) and version must match between labbook and labmanager
    cudav = lb.labmanager_config.config["container"].get("cuda_version")
    logger.info(f"Host CUDA version {cudav}, LabBook CUDA ver {lb.cuda_version}")
    if cudav and lb.cuda_version:
        logger.info(f"Launching container with GPU support CUDA version {lb.cuda_version}")
        container_id = docker_client.containers.run(tag, detach=True, init=True, name=tag,
                                                    environment=env_var, volumes=volumes_dict,
                                                    runtime='nvidia', **resource_args).id
    else:
        container_id = docker_client.containers.run(tag, detach=True, init=True, name=tag,
                                                    environment=env_var, volumes=volumes_dict,
                                                    **resource_args).id

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
    return container_id


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
