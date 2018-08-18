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
import git
import subprocess
from typing import Optional, List

from lmcommon.logging import LMLogger
from lmcommon.labbook import LabBook
from lmcommon.workflows.core import call_subprocess

logger = LMLogger.get_logger()


class BranchException(Exception):
    pass


class BranchWorkflowViolation(BranchException):
    pass


class InvalidBranchName(BranchException):
    pass


class BranchManager(object):
    def __init__(self, labbook: LabBook, username: str) -> None:
        self.labbook = labbook
        self.username = username

    @classmethod
    def is_branch_name_valid(cls, new_branch_name: str) -> bool:
        if len(new_branch_name) > 80:
            return False
        return all([e.isalnum() and e == e.lower() for e in new_branch_name.split('-')])

    @property
    def active_branch(self) -> str:
        """Return the name of the current branch."""
        return self.labbook.active_branch

    @property
    def workspace_branch(self) -> str:
        """Return the user's primary branch name"""
        b = f'gm.workspace-{self.username}'
        if b not in self.branches:
            raise BranchException(f'Cannot find user workspace branch {b}')
        return b

    @property
    def branches(self) -> List[str]:
        """List all gigantum-managed feature branches available for checkout. """
        return [b for b in self.labbook.get_branches()['local'] if f'workspace-{self.username}' in b]

    @property
    def mergeable_branches(self) -> List[str]:
        if self.active_branch == self.workspace_branch:
            # Anythign with a workspace and a dot (indicating it is a feature/rollback branch)
            return [b for b in self.branches if f'{self.workspace_branch}.' in b]
        else:
            # If on a feature branch, can only return
            return [self.workspace_branch]

    def create_branch(self, title: str, description: Optional[str] = None, revision: Optional[str] = None) -> str:
        """Create and checkout (work on) a new managed branch."""
        if not self.is_branch_name_valid(title):
            raise InvalidBranchName('New branch name `{title}` invalid pattern')

        if self.active_branch != f'gm.workspace-{self.username}':
            raise BranchWorkflowViolation('Must be on main user workspace branch to create new branch')

        full_branch_name = f'gm.workspace-{self.username}.{title}'
        if full_branch_name in self.branches:
            raise InvalidBranchName('Branch with title {title} already exists')

        with self.labbook.lock_labbook():
            self.labbook.sweep_uncommitted_changes()
            if revision:
                # The following call prints "commit" if {revision} exists in git history.
                result = subprocess.check_output(f'git cat-file -t {revision} || echo "invalid"',
                    cwd=self.labbook.root_dir, shell=True)
                if result.decode().strip() != 'commit':
                    logger.error(result.decode().strip())
                    raise InvalidBranchName(f'Revision {revision} does not exist in {str(self.labbook)};'
                                            f'cannot create branch {title}')
                # Should be in a detached-head, and then make branch from there.
                logger.info(f"Creating rollback branch from revision {revision} in {str(self.labbook)}")
                r = subprocess.check_output(f'git checkout {revision}', cwd=self.labbook.root_dir, shell=True)
                logger.info(r)
            self.labbook.checkout_branch(branch_name=full_branch_name, new=True)
            logger.info(f'Activated new branch {self.active_branch} in {str(self.labbook)}')

        return full_branch_name

    def remove_branch(self, target_branch: str) -> None:
        """Delete a local feature branch that is NOT the active branch.

        Args:
            target_branch: Full name of feature branch to delete

        Returns:
            None
        """
        if target_branch not in self.branches:
            raise InvalidBranchName(f'Cannot delete `{target_branch}`; does not exist')

        if target_branch == self.workspace_branch:
            raise BranchWorkflowViolation(f'Cannot delete workspace branch `{target_branch}` in {str(self.labbook)}')

        if target_branch == self.active_branch:
            raise BranchWorkflowViolation(f'Cannot delete current active branch `{target_branch}`')

        with self.labbook.lock_labbook():
            logger.info(f'Removing from {str(self.labbook)} feature branch `{target_branch}`')
            # Note use "force=True" to prevent warning on merge.
            self.labbook.git.delete_branch(target_branch, force=True)

        if target_branch in self.branches:
            raise BranchWorkflowViolation(f'Removal of branch `{target_branch}` in {str(self.labbook)} failed.')

    def workon_branch(self, branch_name: str):
        """Checkouts a branch as the working revision. """

        if branch_name not in self.branches:
            raise InvalidBranchName(f'Target branch to work on `{branch_name}` does not exist')

        with self.labbook.lock_labbook():
            self.labbook.sweep_uncommitted_changes()
            self.labbook.checkout_branch(branch_name=branch_name)
            logger.info(f'Activated new branch {self.active_branch} in {str(self.labbook)}')

    def merge_from(self, other_branch: str, force: bool = False):
        """Pulls/merges `other_branch` into current branch. """

        if not other_branch in self.branches:
            raise InvalidBranchName(f'Other branch {other_branch} not found')

        if not other_branch in self.mergeable_branches:
            raise InvalidBranchName(f'Other branch {other_branch} not mergeable into {self.active_branch}')

        logger.info(f"In {str(self.labbook)} merging branch `{other_branch}` into `{self.active_branch}`...")
        with self.labbook.lock_labbook():
            try:
                self.labbook.sweep_uncommitted_changes()
                if force:
                    logger.warning("Using force to overwrite local changes")
                    call_subprocess(['git', 'merge', '-s', 'recursive', '-X', 'theirs', other_branch],
                                    cwd=self.labbook.root_dir)
                else:
                    try:
                        call_subprocess(['git', 'merge', other_branch], cwd=self.labbook.root_dir)
                    except (git.exc.GitCommandError, subprocess.CalledProcessError) as merge_error:
                        logger.error(f"Merge conflict syncing {str(self.labbook)} - Use `force` to overwrite.")
                        # TODO - This should be cleaned up (The UI attempts to match on the token "Cannot merge")
                        raise BranchException(f"Cannot merge - {merge_error}")
                self.labbook.git.commit(f'Merged from branch `{other_branch}`')
                logger.info(f"{str(self.labbook)} finished merge")
            except Exception as e:
                call_subprocess(['git', 'reset', '--hard'], cwd=self.labbook.root_dir)
                raise e
