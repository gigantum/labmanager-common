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
from typing import Any, Callable, Dict, Optional, Tuple

from lmcommon.logging import LMLogger
from lmcommon.activity import ActivityAction, ActivityRecord, ActivityDetailRecord, ActivityType

logger = LMLogger.get_logger()


def process_sweep_status(result_obj: ActivityRecord, status: Dict[str, Any],
                         section_infer_method: Callable) -> Tuple[ActivityRecord, int, int]:
    sections = []
    ncnt = 0
    for filename in status['untracked']:
        # skip any file in .git or .gigantum dirs
        if ".git" in filename or ".gigantum" in filename:
            continue
        activity_type, activity_detail_type, section = section_infer_method(filename)
        adr = ActivityDetailRecord(activity_detail_type, show=False, importance=max(255 - ncnt, 0),
                                   action=ActivityAction.CREATE)
        sections.append(section)
        if section == "LabBook Root":
            msg = f"Created new file `{filename}` in the LabBook Root."
            msg = f"{msg}Note, it is best practice to use the Code, Input, and Output sections exclusively."
        else:
            msg = f"Created new {section} file `{filename}`"
        adr.add_value('text/markdown', msg)
        result_obj.add_detail_object(adr)
        ncnt += 1

    # If all modifications were of same section
    if ncnt > 0 and len(set(sections)) == 1:
        if sections[0] == 'code':
            result_obj.type = ActivityType.CODE
        elif sections[0] == 'input':
            result_obj.type = ActivityType.INPUT_DATA
        elif sections[0] == 'output':
            result_obj.type = ActivityType.OUTPUT_DATA

    mcnt = 0
    msections = []
    for filename, change in status['unstaged']:
        # skip any file in .git or .gigantum dirs
        if ".git" in filename or ".gigantum" in filename:
            continue

        activity_type, activity_detail_type, section = section_infer_method(filename)
        msections.append(section)

        if change == "deleted":
            action = ActivityAction.DELETE
        elif change == "added":
            action = ActivityAction.CREATE
        elif change == "modified":
            action = ActivityAction.EDIT
        elif change == "renamed":
            action = ActivityAction.EDIT
        else:
            action = ActivityAction.NOACTION

        adr = ActivityDetailRecord(activity_detail_type, show=False, importance=max(255 - mcnt, 0), action=action)
        adr.add_value('text/markdown', f"{change[0].upper() + change[1:]} {section} file `{filename}`")
        result_obj.add_detail_object(adr)
        mcnt += 1

    # If modifications were of different type than before, just make type as LABBOOK catchall.

    if result_obj.type == ActivityType.LABBOOK:
        if mcnt > 0 and len(set(msections)) == 1:
            if msections[0] == 'code':
                result_obj.type = ActivityType.CODE
            elif msections[0] == 'input':
                result_obj.type = ActivityType.INPUT_DATA
            elif msections[0] == 'output':
                result_obj.type = ActivityType.OUTPUT_DATA
    elif not(mcnt > 0 and len(set(msections)) == 1 and msections[0] == sections[0]):
        # Mismatch, just use catchall LABBOOK
        result_obj.type = ActivityType.LABBOOK


    # Return additionally new file cnt (ncnt) and modifified (mcnt)
    return result_obj, ncnt, mcnt


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
        labbook.sweep_uncommitted_changes()
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