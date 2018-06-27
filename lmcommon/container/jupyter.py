import uuid
import time
import os
import re
from typing import Optional, Tuple, List

import redis
import requests

from lmcommon.logging import LMLogger
from lmcommon.configuration import get_docker_client
from lmcommon.environment import ComponentManager
from lmcommon.container.core import infer_docker_image_name, get_container_ip
from lmcommon.labbook import LabBook, LabbookException

logger = LMLogger.get_logger()

DEFAULT_JUPYTER_PORT = 8888


def start_jupyter(labbook: LabBook, username: str, tag: Optional[str] = None,
                  check_reachable: bool = True,
                  proxy_prefix: Optional[str] = None) -> str:
    """ Main entrypoint to launching Jupyter. Note, the caller must
        determine for themselves the host and port.

    Returns:
        Path to jupyter (e.g., "/lab?token=xyz")
    """

    lb_key = tag or infer_docker_image_name(labbook_name=labbook.name,
                                            owner=labbook.owner['username'],
                                            username=username)
    docker_client = get_docker_client()
    lb_container = docker_client.containers.get(lb_key)
    if lb_container.status != 'running':
        raise LabbookException(f"{str(labbook)} container is not running")

    search_sh = f'sh -c "ps aux | grep \'jupyter lab\' | grep -v \' grep \'"'
    jupyter_tokens = lb_container.exec_run(search_sh)
    jupyter_ps = [l for l in jupyter_tokens.decode().split('\n') if l]

    if len(jupyter_ps) == 1:
        # Get token from PS in container
        t = re.search("token='?([a-zA-Z\d-]+)'?", jupyter_ps[0])
        if not t:
            raise LabbookException('Cannot detect Jupyter Lab token')
        token = t.groups()[0]
        return f'{proxy_prefix or ""}/lab?token={token}'
    elif len(jupyter_ps) == 0:
        token = str(uuid.uuid4()).replace('-', '')
        if proxy_prefix and proxy_prefix[0] != '/':
            proxy_prefix = f'/{proxy_prefix}'
        _start_jupyter_process(labbook, lb_container, username, lb_key, token,
                               proxy_prefix)
        suffix = f'{proxy_prefix or ""}/lab?token={token}'
        if check_reachable:
            _check_jupyter_reachable(lb_key, suffix)
        return suffix
    else:
        # If "ps aux" for jupyterlab returns multiple hits - this should never happen.
        for n, l in enumerate(jupyter_ps):
            logger.error(f'Multiple JupyerLab instances - ({n+1} of {len(jupyter_ps)}) - {l}')
        raise ValueError(f'Multiple ({len(jupyter_ps)}) Jupyter Lab instances detected')


def _shim_skip_python2_savehook(labbook: LabBook) -> bool:
    """Return True if the LabBook uses a Python 2 base image.
    If the base is Python 2, we cannot use the save hook.
    TODO - This should be fixed with upstream JupyterLab fixes. """
    cm = ComponentManager(labbook)
    return 'python2' in cm.base_fields['id'].lower().replace(' ', '')


def _start_jupyter_process(labbook: LabBook, lb_container,
                           username: str, lb_key: str, token: str,
                           proxy_prefix: Optional[str] = None) -> None:
    use_savehook = os.path.exists('/mnt/share/jupyterhooks') \
                   and not _shim_skip_python2_savehook(labbook)
    un = labbook.owner['username']
    cmd = (f"export PYTHONPATH=/mnt/share:$PYTHONPATH && "
           f'echo "{username},{un},{labbook.name},{token}" > /home/giguser/jupyter_token && '
           f"cd /mnt/labbook && "
           f"jupyter lab --port={DEFAULT_JUPYTER_PORT} --ip=0.0.0.0 "
           f"--NotebookApp.token='{token}' --no-browser "
           f'--ConnectionFileMixin.ip=0.0.0.0 ' +
           (f'--FileContentsManager.post_save_hook="jupyterhooks.post_save_hook" '
            if use_savehook else "") +
           (f'--NotebookApp.base_url="{proxy_prefix}" '
            if proxy_prefix else ''))

    lb_container.exec_run(f'sh -c "{cmd}"', detach=True, user='giguser')

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

    # Store token in redis for later activity monitoring
    # (activity data is stored in db1)
    redis_conn = redis.Redis(db=1)
    redis_conn.set(f"{lb_key}-jupyter-token", token)


def _check_jupyter_reachable(lb_key: str, suffix: str):
    for n in range(30):
        # Get IP of container on Docker Bridge Network
        lb_ip_addr = get_container_ip(lb_key)
        test_url = f'http://{lb_ip_addr}:{DEFAULT_JUPYTER_PORT}{suffix}'
        logger.debug(f"Attempt {n + 1}: Testing if JupyerLab is up at {test_url}...")
        try:
            r = requests.get(test_url, timeout=0.5)
            if r.status_code != 200:
                time.sleep(0.5)
            else:
                logger.info(f'Found JupyterLab up at {test_url} after {n/2.0} seconds')
                break
        except requests.exceptions.ConnectionError:
            # Assume API isn't up at all yet, so no connection can be made
            time.sleep(0.5)
    else:
        raise LabbookException(f'Could not reach JupyterLab at {test_url} after timeout')
