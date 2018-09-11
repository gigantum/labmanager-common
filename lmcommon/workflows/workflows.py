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
import time
from typing import Optional

from lmcommon.configuration.utils import call_subprocess
from lmcommon.labbook import LabBook
from lmcommon.logging import LMLogger
from lmcommon.workflows import core

logger = LMLogger.get_logger()


class GitWorkflow(object):

    def __init__(self, labbook: LabBook) -> None:
        self.labbook = labbook

    def garbagecollect(self):
        """ Run a `git gc` on the labbook. """
        with self.labbook.lock_labbook():
            core.git_garbage_collect(self.labbook)

    def publish(self, username: str, access_token: Optional[str] = None, remote: str = "origin",
                public: bool = False) -> None:
        """ Publish this labbook to the remote GitLab instance.

        Args:
            username: Subject username
            access_token: Temp token/password to gain permissions on GitLab instance
            remote: Name of Git remote (always "origin" for now).
            public: Allow public read access

        Returns:
            None
        """

        logger.info(f"Publishing {str(self.labbook)} for user {username} to remote {remote}")
        if self.labbook.has_remote:
            raise ValueError("Cannot publish Labbook when remote already set.")

        if self.labbook.active_branch != f'gm.workspace-{username}':
            raise ValueError(f"Must be on user workspace (gm.workspace-{username}) to sync")

        with self.labbook.lock_labbook():
            try:
                self.labbook.sweep_uncommitted_changes()
                vis = "public" if public is True else "private"
                t0 = time.time()
                core.create_remote_gitlab_repo(labbook=self.labbook, username=username,
                                               access_token=access_token, visibility=vis)
                logger.info(f"Created remote repo for {str(self.labbook)} in {time.time()-t0:.1f}sec")
                t0 = time.time()
                core.publish_to_remote(labbook=self.labbook, username=username, remote=remote)
                logger.info(f"Published {str(self.labbook)} in {time.time()-t0:.1f}sec")
            except Exception as e:
                # Unsure what specific exception add_remote creates, so make a catchall.
                logger.error(f"Publish failed {e}: {str(self.labbook)} may be in corrupted Git state!")
                call_subprocess(['git', 'reset', '--hard'], cwd=self.labbook.root_dir)
                self.labbook.checkout_branch(f"gm.workspace-{username}")
                raise e

    def sync(self, username: str, remote: str = "origin", force: bool = False) -> int:
        """ Sync with remote GitLab repo (i.e., pull any upstream changes and push any new changes). Following
        a sync operation both the local repo and remote should be at the same revision.

        Args:
            username: Subject user
            remote: Name of remote (usually only origin for now)
            force: In the event of conflict, force overwrite local changes

        Returns:
            Integer number of commits pulled down from remote.
        """
        return core.sync_with_remote(labbook=self.labbook, username=username, remote=remote, force=force)

    def _add_remote(self, remote_name: str, url: str):
        self.labbook.add_remote(remote_name=remote_name, url=url)
