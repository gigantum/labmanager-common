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
import docker.errors
import time
from typing import Optional, List, Tuple, Any, Dict

from lmcommon.configuration import get_docker_client
from lmcommon.portmap import PortMap
from lmcommon.environment import ComponentManager
from lmcommon.labbook import LabBook
from lmcommon.container.utils import dockerize_path, infer_docker_image_name


def build_docker_image(root_dir: str, override_image_tag: Optional[str], nocache: bool = False,
                       username: Optional[str] = None) -> str:
    """
    Build a new docker image from the Dockerfile at the given directory, give this image
    the name defined by the image_name argument.

    Note! This method is static, it should **NOT** use any global variables or any other
    reference to global state.

    Args:
        root_dir: LabBook root directory (obtained by LabBook.root_dir)
        override_image_tag: Tag of docker image; in general this should not be explicitly set.
        username: Username of active user.
        nocache: If True do not use docker cache.

    Returns:
        A string container the short docker id of the newly built image.
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
    docker_image = get_docker_client().images.build(path=env_dir, tag=image_name, pull=True, nocache=nocache)
    return docker_image.short_id.split(':')[1]


def start_labbook_container(labbook_root: str, config_path: str, override_image_id: Optional[str] = None,
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

    opened_ports: List[int] = []
    env_manager = ComponentManager(lb)
    if 'jupyterlab' in env_manager.base_fields['development_tools']:
        opened_ports = [8888]

    exposed_p, portmap = opened_ports, PortMap(lb.labmanager_config)
    exposed_ports = {f"{port}/tcp": portmap.assign(lb.key, "0.0.0.0", port) for port in exposed_p}
    mnt_point = dockerize_path(labbook_root.replace('/mnt/gigantum', os.environ['HOST_WORK_DIR']))

    volumes_dict = {
        mnt_point: {'bind': '/mnt/labbook', 'mode': 'cached'},
        'labmanager_share_vol': {'bind': '/mnt/share', 'mode': 'rw'}
    }

    # If re-mapping permissions, be sure to configure the container
    if 'LOCAL_USER_ID' in os.environ:
        env_var = [f"LOCAL_USER_ID={os.environ['LOCAL_USER_ID']}"]
    else:
        env_var = ["WINDOWS_HOST=1"]

    docker_client = get_docker_client()
    container_id = docker_client.containers.run(tag,
        detach=True, init=True, name=tag, ports=exposed_ports,
        environment=env_var, volumes=volumes_dict).id

    # Brief pause to prevent certain race conditions.
    time.sleep(1)
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
