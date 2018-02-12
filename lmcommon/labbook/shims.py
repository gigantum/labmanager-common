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

import os
from typing import Optional

from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()


def to_workspace_branch(labbook, username: Optional[str] = None) -> str:
    """Shim to upgrade old labbook (schema v0.1) to new labbook branches.

    This change only involves getting rid of master and using the new gm.workspace branch model.

    Input:
        labbook: Labbook that must be upgraded.
        username: username for creating name of active branch.
    Returns:
        str: Name of new labbook active branch.
    Raises:
        ValueError if labbook's current branch is not master.
    """

    if labbook.active_branch != 'master':
        raise ValueError('Shim expects LabBook {str(labbook)} active branch as master')

    with labbook.lock_labbook():
        logger.warning(f"Upgrading {str(labbook)} to new gm.workspace branch model")
        labbook._sweep_uncommitted_changes()
        labbook.checkout_branch('gm.workspace', new=True)

        if username:
            labbook.checkout_branch(f'gm.workspace-{username}', new=True)

    return labbook.active_branch

def in_untracked(labbook_root: str, section: str) -> bool:
    """ Query whether the given section for a labbook root dir is tracked in Git.

    THIS IS A DUPLICATE TO AVOID A CIRCULAR DEPENDENCY.
    This will get removed once the file operations are factored out of labbook.py

    Args:
         labbook_root: Root directory of labbook
         section: Section to check if tracked or not

    Returns:
        True if the given section is untracked (as workaround for Git performance).
    """
    gitignore_path = os.path.join(labbook_root, '.gitignore')
    if not os.path.exists(gitignore_path):
        return False
    gitignore_lines = [l.strip() for l in open(gitignore_path).readlines()]
    target_lines = [f'{section}/*', f'!{section}/.gitkeep']
    if all([a in gitignore_lines for a in target_lines]):
        return True
    else:
        return False