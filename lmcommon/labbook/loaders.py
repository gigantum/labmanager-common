from typing import Optional
import subprocess
import shutil
import time
import os

from lmcommon.configuration.utils import call_subprocess
from lmcommon.labbook.labbook import LabBook, LabbookException
from lmcommon.gitlib.gitlab import GitLabManager
from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()


def from_remote(remote_url: str, username: str, owner: str,
                labbook_name: str, labbook: Optional[LabBook] = None,
                make_owner: bool = False) -> LabBook:
    """Clone a labbook from a remote Git repository.

    Args:
        remote_url: URL or path of remote repo
        username: Username of logged in user
        owner: Owner/namespace of labbook
        labbook_name: Name of labbook
        labbook: Optional labbook instance with config
        make_owner: After cloning, make the owner the "username"

    Returns:
        LabBook
    """

    if make_owner:
        owner = username

    if labbook is None:
        # If labbook instance is not passed in, make a new one with blank conf
        labbook = LabBook()

    lbconf = labbook.labmanager_config.config["git"]["working_directory"]
    starting_dir = os.path.expanduser(lbconf)

    # Expected full path of the newly imported labbook.
    lb_dir = os.path.join(starting_dir, username, owner, 'labbooks')
    est_root_dir = os.path.join(starting_dir, username, owner, 'labbooks', labbook_name)
    if os.path.exists(est_root_dir):
        errmsg = f"Cannot clone labbook, path already exists at `{est_root_dir}`"
        logger.error(errmsg)
        raise ValueError(errmsg)

    os.makedirs(lb_dir, exist_ok=True)

    if labbook.labmanager_config.config["git"]["lfs_enabled"] is True:
        logger.info(f"Cloning labbook with `git lfs clone ...` from remote `{remote_url}` into `{est_root_dir}...")
        t0 = time.time()
        try:
            call_subprocess(['git', 'lfs', 'clone', remote_url], cwd=lb_dir)
            labbook.git.set_working_directory(est_root_dir)
        except subprocess.CalledProcessError as e:
            logger.error(e)
            logger.error(f'git lfs clone: stderr={e.stderr.decode()}, stdout={e.stdout.decode()}')
            shutil.rmtree(est_root_dir, ignore_errors=True)
            raise
        logger.info(f"Git LFS cloned from `{remote_url}` in {time.time()-t0}s")
    else:
        labbook.git.clone(remote_url, directory=est_root_dir)
        labbook.git.fetch()

    # NOTE!! using self.checkout_branch fails w/Git error:
    # "Ref 'HEAD' did not resolve to an object"
    logger.info(f"Checking out gm.workspace")
    labbook.git.checkout("gm.workspace")

    labbook._set_root_dir(est_root_dir)
    labbook._load_labbook_data()

    with labbook.lock_labbook():
        logger.info(f"Checking out gm.workspace-{username}")
        if f'origin/gm.workspace-{username}' in labbook.get_branches()['remote']:
            labbook.checkout_branch(f"gm.workspace-{username}")
        else:
            labbook.checkout_branch(f"gm.workspace-{username}", new=True)

    if make_owner:
        with labbook.lock_labbook():
            logger.info(f"Cloning public repo; changing owner to {username}")
            labbook._load_labbook_data()
            if labbook._data:
                labbook._data['owner']['username'] = username
            else:
                raise LabbookException("LabBook _data not defined")
        labbook._save_labbook_data()
        with labbook.lock_labbook():
            labbook.remove_remote('origin')
            msg = f"Imported and changed owner to {username}"
            labbook.sweep_uncommitted_changes(extra_msg=msg)
    return labbook
