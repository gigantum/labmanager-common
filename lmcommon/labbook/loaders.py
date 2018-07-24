import time
import os

from lmcommon.labbook import LabBook
from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()


class Loader(object):
    pass

def from_remote(self, remote_url: str, username: str, owner: str, labbook_name: str):
    """Clone a labbook from a remote Git repository.

    Args:
        remote_url(str): URL or path of remote repo
        username(str): Username of logged in user
        owner(str): Owner/namespace of labbook
        labbook_name(str): Name of labbook

    Returns:
        None
    """

    if not remote_url:
        raise ValueError("remote_url cannot be None or empty")

    if not username:
        raise ValueError("username cannot be None or empty")

    if not owner:
        raise ValueError("owner cannot be None or empty")

    if not labbook_name:
        raise ValueError("labbook_name cannot be None or empty")

    starting_dir = os.path.expanduser(self.labmanager_config.config["git"]["working_directory"])

    # Expected full path of the newly imported labbook.
    lb_dir = os.path.join(starting_dir, username, owner, 'labbooks')
    est_root_dir = os.path.join(starting_dir, username, owner, 'labbooks', labbook_name)
    if os.path.exists(est_root_dir):
        errmsg = f"Cannot clone labbook, path already exists at `{est_root_dir}`"
        logger.error(errmsg)
        raise ValueError(errmsg)

    os.makedirs(lb_dir, exist_ok=True)

    if self.labmanager_config.config["git"]["lfs_enabled"] is True:
        logger.info(f"Cloning labbook with `git lfs clone ...` from remote `{remote_url}` into `{est_root_dir}...")

        t0 = time.time()
        try:
            call_subprocess(['git', 'lfs', 'clone', remote_url], cwd=lb_dir)
            self.git.set_working_directory(est_root_dir)
        except subprocess.CalledProcessError as e:
            logger.error(e)
            logger.error(f'git lfs clone: stderr={e.stderr.decode()}, stdout={e.stdout.decode()}')
            shutil.rmtree(est_root_dir, ignore_errors=True)
            raise
        logger.info(f"Git LFS cloned from `{remote_url}` in {time.time()-t0}s")
    else:
        self.git.clone(remote_url, directory=est_root_dir)
        self.git.fetch()

    logger.info(f"Checking out gm.workspace")
    # NOTE!! using self.checkout_branch fails w/Git error: "Ref 'HEAD' did not resolve to an object"
    self.git.checkout("gm.workspace")

    logger.info(f"Checking out gm.workspace-{username}")
    if f'origin/gm.workspace-{username}' in self.get_branches()['remote']:
        self.checkout_branch(f"gm.workspace-{username}")
    else:
        self.checkout_branch(f"gm.workspace-{username}", new=True)

    # Once the git repo is cloned, the problem just becomes a regular import from file system.
    self.from_directory(est_root_dir)