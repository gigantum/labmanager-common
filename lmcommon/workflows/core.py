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

import git
import subprocess
import datetime
import time
from typing import Optional

from lmcommon.gitlib.gitlab import GitLabRepositoryManager
from lmcommon.labbook import LabBook, LabbookException, LabbookMergeException
from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()

class WorkflowsException(Exception):
    pass


class MergeError(WorkflowsException):
    pass


class GitLabRemoteError(WorkflowsException):
    pass


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
    start_time = time.time()
    try:
        r = subprocess.run(['git', 'gc'], stderr=subprocess.PIPE, stdout=subprocess.PIPE,
                           check=True, cwd=labbook.root_dir)
        finish_time = time.time()
        logger.info(f"Finished git gc in {str(labbook)} after {finish_time - start_time}s")
    except subprocess.CalledProcessError as x:
        fail_time = time.time()
        logger.error(f"Failed git gc after {fail_time - start_time}s with code {x.returncode}: {x.stderr}")
        raise


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

    Note: It may make more sense to factor this out later on. TODO. """

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
        mgr = GitLabRepositoryManager(default_remote, admin_service, access_token=access_token or 'invalid',
                                      username=username, owner=labbook.owner['username'], labbook_name=labbook.name)
        mgr.configure_git_credentials(default_remote, username)
        mgr.create()
        labbook.add_remote("origin", f"https://{default_remote}/{username}/{labbook.name}.git")
    except Exception as e:
        raise GitLabRemoteError(e)


def publish_to_remote(labbook: LabBook, username: str, remote: str) -> None:
    # Current branch must be the user's workspace.
    if f'gm.workspace-{username}' != labbook.active_branch:
        raise ValueError('User workspace must be active branch to publish')

    # The gm.workspace branch must exist (if not, then there is a problem in Labbook.new())
    if not 'gm.workspace' in labbook.get_branches()['local']:
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
    labbook.git.merge(f"gm.workspace-{username}")
    labbook.git.add_all(labbook.root_dir)
    labbook.git.commit(f"Merged gm.workspace-{username}")

    # Push the master workspace to the remote, creating if necessary
    if not f"{remote}/{labbook.active_branch}" in labbook.get_branches()['remote']:
        logger.info(f"Pushing and setting upstream branch {labbook.active_branch} to {remote}")
        labbook.git.repo.git.push("--set-upstream", remote, labbook.active_branch)
    else:
        logger.info(f"Pushing {labbook.active_branch} to {remote}")
        labbook.git.publish_branch(branch_name=labbook.active_branch, remote_name=remote)

    # Return to the user's workspace, merge it with the global workspace (as a precaution)
    labbook.checkout_branch(branch_name=f'gm.workspace-{username}')
    labbook.git.merge("gm.workspace")
    labbook.git.add_all(labbook.root_dir)
    labbook.git.commit(f"Merged gm.workspace-{username}")

    # Now push the user's workspace to the remote repo (again, as a precaution)
    if not labbook.active_branch in labbook.get_branches()['remote']:
        logger.info(f"Pushing and setting upstream branch {labbook.active_branch} to {remote}")
        labbook.git.repo.git.push("--set-upstream", remote, labbook.active_branch)
    else:
        logger.info(f"Pushing {labbook.active_branch} to {remote}")
        labbook.git.publish_branch(branch_name=labbook.active_branch, remote_name=remote)


#_validate_git
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
        if not labbook.has_remote:
            sync_locally(labbook, username)
            return 0

        logger.info(f"Syncing {str(labbook)} for user {username} to remote {remote}")
        labbook.git.fetch(remote=remote)
        with labbook.lock_labbook():
            labbook._sweep_uncommitted_changes()

            git_garbage_collect(labbook)

            ## Checkout the workspace and retrieve any upstream updtes
            labbook.checkout_branch("gm.workspace")
            remote_updates_cnt = labbook.get_commits_behind_remote()[1]
            pull(labbook=labbook, remote=remote)

            ## Pull those changes into the personal workspace
            labbook.checkout_branch(f"gm.workspace-{username}")
            if force:
                logger.warning("Using force to overwrite local changes")
                r = subprocess.check_output(f'git merge -s recursive -X theirs {remote}/gm.workspace',
                                            cwd=labbook.root_dir, shell=True)
                logger.info(f'Got result of merge: {r}')
            else:
                try:
                    labbook.git.merge("gm.workspace")
                except git.exc.GitCommandError as merge_error:
                    logger.error(f"Merge conflict syncing {str(labbook)} - Use `force` to overwrite.")
                    raise LabbookMergeException(merge_error)
            labbook.git.add_all(labbook.root_dir)
            labbook.git.commit("Sync -- Merged from gm.workspace")
            push(labbook=labbook, remote=remote)

            ## Get the local workspace and user's local workspace synced.
            labbook.checkout_branch("gm.workspace")
            labbook.git.merge(f"gm.workspace-{username}")
            labbook.git.add_all(labbook.root_dir)
            labbook.git.commit(f"Sync -- Pulled in {username}'s changes")

            ## Sync it with the remote again. Everything should be up-to-date at this point.
            push(labbook=labbook, remote=remote)
            labbook.checkout_branch(f"gm.workspace-{username}")

            return remote_updates_cnt
    except LabbookMergeException as m:
        raise MergeError(m)
    except Exception as e:
        raise WorkflowsException(e)
    finally:
        ## We should (almost) always have the user's personal workspace checked out.
        labbook.checkout_branch(f"gm.workspace-{username}")


#@_validate_git
def sync_locally(labbook: LabBook, username: Optional[str] = None) -> None:
    """Sync locally only to gm.workspace branch - don't do anything with remote. Creates a user's
     local workspace if necessary.

    Args:
        username(str): Active username

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
        logger.exception(e)
        raise LabbookException(e)
