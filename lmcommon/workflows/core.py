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

import subprocess
import datetime
import time
from typing import Optional, List

from lmcommon.gitlib.gitlab import GitLabManager
from lmcommon.labbook import LabBook, LabbookException, LabbookMergeException
from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()


class WorkflowsException(Exception):
    pass


class MergeError(WorkflowsException):
    pass


class GitLabRemoteError(WorkflowsException):
    pass


def call_subprocess(cmd_tokens: List[str], cwd: str, check: bool = True) -> None:
    """Execute a subprocess call and properly benchmark and log

    Args:
        cmd_tokens: List of command tokens, e.g., ['ls', '-la']
        cwd: Current working directory
        check: Raise exception if command fails

    Returns:
        None

    Raises:
        subprocess.CalledProcessError
    """
    logger.debug(f"Executing `{' '.join(cmd_tokens)}` in {cwd}")
    start_time = time.time()
    try:
        r = subprocess.run(cmd_tokens, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, check=check)
        finish_time = time.time()
        elapsed_time = finish_time - start_time
        logger.debug(f"Finished command `{' '.join(cmd_tokens)}` in {elapsed_time}s")
        if elapsed_time > 1.0:
            logger.warning(f"Successful command `{' '.join(cmd_tokens)}` took {elapsed_time}s")
    except subprocess.CalledProcessError as x:
        fail_time = time.time() - start_time
        logger.error(f"Command failed `{' '.join(cmd_tokens)}` after {fail_time}s: stderr={x.stderr}")
        raise


def git_garbage_collect(labbook: LabBook) -> None:
    """Run "git gc" (garbage collect) over the repo. If run frequently enough, this only takes a short time
    even on large repos.

    Note!! This method assumes the subject labbook has already been locked!

    Args:
        labbook: Subject LabBook

    Returns:
        None

    Raises:
        subprocess.CalledProcessError when git gc fails.
        """
    logger.info(f"Running git gc (Garbage Collect) in {str(labbook)}...")
    try:
        call_subprocess(['git', 'gc'], cwd=labbook.root_dir)
    except subprocess.CalledProcessError:
        logger.warning(f"Ignore `git gc` error - {str(labbook)} repo remains unpruned")


def push(labbook: LabBook, remote: str) -> None:
    """Push commits to a remote git repository. Assume current working branch.

    Args:
        labbook: Subject labbook
        remote: Git remote (usually always origin).
    Returns:
        None
    """
    try:
        logger.info(f"Fetching from remote {remote}")
        labbook.git.fetch(remote=remote)

        if not labbook.active_branch in labbook.get_branches()['remote']:
            logger.info(f"Pushing and setting upstream branch {labbook.active_branch}")
            labbook.git.repo.git.push("--set-upstream", remote, labbook.active_branch)
        else:
            logger.info(f"Pushing to {remote}")
            labbook.git.publish_branch(branch_name=labbook.active_branch, remote_name=remote)
    except Exception as e:
        raise GitLabRemoteError(e)


def pull(labbook: LabBook, remote: str) -> None:
    """Pull and update from a remote git repository

    Args:
        labbook: Subject labbook
        remote: Remote Git repository to pull from. Default is "origin"

    Returns:
        None
    """

    try:
        logger.info(f"{str(labbook)} pulling from remote {remote}")
        start = datetime.datetime.now()
        labbook.git.pull(remote=remote)
        end = datetime.datetime.now()
        delta = (end - start).total_seconds()
        method = logger.info if delta < 2.0 else logger.warning
        method(f'Pulled {str(labbook)} from {remote} in {delta} sec')
    except Exception as e:
        raise GitLabRemoteError(e)


def create_remote_gitlab_repo(labbook: LabBook, username: str, access_token: Optional[str] = None) -> None:
    """Create a new repository in GitLab,

    Note: It may make more sense to factor this out later on. """

    default_remote = labbook.labmanager_config.config['git']['default_remote']
    admin_service = None
    for remote in labbook.labmanager_config.config['git']['remotes']:
        if default_remote == remote:
            admin_service = labbook.labmanager_config.config['git']['remotes'][remote]['admin_service']
            break

    if not admin_service:
        raise ValueError('admin_service could not be found')

    try:
        # Add collaborator to remote service
        mgr = GitLabManager(default_remote, admin_service, access_token=access_token or 'invalid')
        mgr.configure_git_credentials(default_remote, username)
        mgr.create_labbook(namespace=labbook.owner['username'], labbook_name=labbook.name)
        labbook.add_remote("origin", f"https://{default_remote}/{username}/{labbook.name}.git")
    except Exception as e:
        raise GitLabRemoteError(e)


def publish_to_remote(labbook: LabBook, username: str, remote: str) -> None:
    # Current branch must be the user's workspace.
    if f'gm.workspace-{username}' != labbook.active_branch:
        raise ValueError('User workspace must be active branch to publish')

    # The gm.workspace branch must exist (if not, then there is a problem in Labbook.new())
    if 'gm.workspace' not in labbook.get_branches()['local']:
        raise ValueError('Branch gm.workspace does not exist in local Labbook branches')

    git_garbage_collect(labbook)
    labbook.git.fetch(remote=remote)

    # Make sure user's workspace is synced (in case they are working on it on other machines)
    if labbook.get_commits_behind_remote(remote_name=remote)[1] > 0:
        raise ValueError(f'Cannot publish since {labbook.active_branch} is not synced')

    # Make sure the master workspace is synced before attempting to publish.
    labbook.git.checkout("gm.workspace")

    if labbook.get_commits_behind_remote(remote_name=remote)[1] > 0:
        raise ValueError(f'Cannot publish since {labbook.active_branch} is not synced')

    # Now, it should be safe to pull the user's workspace into the master workspace.
    #labbook.git.merge(f"gm.workspace-{username}")
    call_subprocess(['git', 'merge', f'gm.workspace-{username}'], cwd=labbook.root_dir)
    labbook.git.add_all(labbook.root_dir)
    labbook.git.commit(f"Merged gm.workspace-{username}")

    call_subprocess(['git', 'push', '--set-upstream', 'origin', 'gm.workspace'], cwd=labbook.root_dir)

    # Return to the user's workspace, merge it with the global workspace (as a precaution)
    labbook.checkout_branch(branch_name=f'gm.workspace-{username}')


def sync_with_remote(labbook: LabBook, username: str, remote: str, force: bool) -> int:
    """Sync workspace and personal workspace with the remote.

    Args:
        labbook: Subject labbook
        username(str): Username of current user (populated by API)
        remote(str): Name of the Git remote
        force: Force overwrite

    Returns:
        int: Number of commits pulled from remote (0 implies no upstream changes pulled in).

    Raises:
        LabbookException on any problems.
    """

    # Note, BVB: For now, this method only supports the initial branching workflow of having
    # "workspace" and "workspace-{user}" branches. In the future, its signature will change to support
    # user feature-branches.

    try:
        if labbook.active_branch != f'gm.workspace-{username}':
            raise ValueError(f"Must be on user workspace (gm.workspace-{username}) to sync")

        if not labbook.has_remote:
            sync_locally(labbook, username)
            return 0

        updates = 0
        logger.info(f"Syncing {str(labbook)} for user {username} to remote {remote}")
        with labbook.lock_labbook():
            labbook._sweep_uncommitted_changes()
            git_garbage_collect(labbook)

            tokens = ['git', 'pull', '--commit', 'origin', 'gm.workspace']
            tokens_force = ['git', 'pull', '--commit', '-s', 'recursive', '-X', 'theirs', 'origin', 'gm.workspace']
            checkpoint = labbook.git.commit_hash
            try:
                call_subprocess(tokens if not force else tokens_force, cwd=labbook.root_dir)
            except subprocess.CalledProcessError as x:
                logger.error(f"{str(labbook)} cannot merge with remote; resetting to revision {checkpoint}...")
                call_subprocess(['git', 'merge', '--abort'], cwd=labbook.root_dir)
                call_subprocess(['git', 'reset', '--hard', checkpoint], cwd=labbook.root_dir)
                raise LabbookMergeException('Merge conflict pulling upstream changes')

            checkpoint2 = labbook.git.commit_hash
            call_subprocess(['git', 'checkout', 'gm.workspace'], cwd=labbook.root_dir)
            call_subprocess(['git', 'merge', f'gm.workspace-{username}'], cwd=labbook.root_dir)
            call_subprocess(['git', 'push', 'origin', 'gm.workspace'], cwd=labbook.root_dir)
            labbook.checkout_branch(f"gm.workspace-{username}")

            updates = 0 if checkpoint == checkpoint2 else 1

        # Return 1 if there have been updates made
        return updates

    except LabbookMergeException as m:
        raise MergeError(m)
    except Exception as e:
        raise WorkflowsException(e)
    finally:
        ## We should (almost) always have the user's personal workspace checked out.
        labbook.checkout_branch(f"gm.workspace-{username}")


def sync_locally(labbook: LabBook, username: Optional[str] = None) -> None:
    """Sync locally only to gm.workspace branch - don't do anything with remote. Creates a user's
     local workspace if necessary.

    Args:
        labbook: Subject labbook instance
        username: Active username

    Returns:
        None

    Raises:
        LabbookException
    """
    try:
        with labbook.lock_labbook():
            labbook._sweep_uncommitted_changes()

            git_garbage_collect(labbook)

            if username and f"gm.workspace-{username}" not in labbook.get_branches()['local']:
                labbook.checkout_branch("gm.workspace")
                labbook.checkout_branch(f"gm.workspace-{username}", new=True)
                labbook.git.merge("gm.workspace")
                labbook.git.commit(f"Created and merged new user workspace gm.workspace-{username}")
            else:
                orig_branch = labbook.active_branch
                labbook.checkout_branch("gm.workspace")
                labbook.git.merge(orig_branch)
                labbook.git.commit(f"Merged from local workspace")
                labbook.checkout_branch(orig_branch)
    except Exception as e:
        logger.error(e)
        raise LabbookException(e)
