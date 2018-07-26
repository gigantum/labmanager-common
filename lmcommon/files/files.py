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

from typing import Any, Dict, Optional
import shutil
import os

from lmcommon.labbook import LabBook
from lmcommon.labbook import shims
from lmcommon.logging import LMLogger
from lmcommon.activity import (ActivityDetailRecord, ActivityRecord,
                               ActivityStore, ActivityAction)
from lmcommon.configuration.utils import call_subprocess
from lmcommon.files.utils import in_untracked

logger = LMLogger.get_logger()


def _make_path_relative(path_str: str) -> str:
    while len(path_str or '') >= 1 and path_str[0] == os.path.sep:
        path_str = path_str[1:]
    return path_str


class FileOperationsException(Exception):
    pass


class FileOperations(object):

    @classmethod
    def content_size(cls, labbook: LabBook) -> int:
        """ Return the size on disk (in bytes) of the given LabBook.

        Args:
            labbook: Subject labbook

        Returns:
            int size of LabBook on disk
        """
        # Note: os.walk does NOT follow symlinks, but does follow hidden files
        total_bytes = 0
        for dirpath, dirnames, filenames in os.walk(labbook.root_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_bytes += os.path.getsize(fp)
        return total_bytes

    @classmethod
    def is_set_untracked(cls, labbook: LabBook, section: str) -> bool:
        """ Return True if the given labbook section is set to be untracked
        (to work around git performance issues when files are large).

        Args:
            labbook: Subject labbook
            section: Section one of code, input, or output.

        Returns:
            bool indicating whether the labbook's section is set as untracked
        """
        return in_untracked(labbook.root_dir, section)

    @classmethod
    def set_untracked(cls, labbook: LabBook, section: str) -> LabBook:
        """ Configure a labbook subdirectory to be untracked so large files
        don't cause Git performance degradation. Under the hood this just
        makes the directory untracked by Git, such that there are no large git
        indexes for the files. Note that this must be set before uploading
        files to the given `section`.

        Args:
            labbook: Subject labbook
            section: Section to set untracked - one of code, input, or output.

        Returns:
            None

        Raises:
            FileOperationsException if ...
              (1) section already contains files, or
              (2) other problem.
        """
        section_path = os.path.join(labbook.root_dir, section.replace('/', ''))
        if not os.path.exists(section_path):
            raise FileOperationsException(f'Section {section} not found '
                                          f'in {str(labbook)}')

        filelist = os.listdir(section_path)
        if not(len(filelist) == 1 and filelist[0] == '.gitkeep'):
            raise FileOperationsException(f'Files already exist in '
                                          f'{str(labbook)} section {section}')

        append_lines = [f'# Ignore files for section {section} - '
                        f'fix to improve Git performance with large files',
                        f'{section}/*', f'!{section}/.gitkeep']

        if cls.is_set_untracked(labbook, section):
            raise FileOperationsException(f'Section {section} already '
                                          f'untracked in {str(labbook)}')

        with labbook.lock_labbook():
            with open(os.path.join(labbook.root_dir, '.gitignore'), 'a') as gi_file:
                gi_file.write('\n'.join([''] + append_lines + ['']))

            labbook.git.add(os.path.join(labbook.root_dir, '.gitignore'))
            labbook.git.commit(f"Set section {section} as untracked as fix "
                               f"for Git performance")

        return labbook

    @classmethod
    def put_file(cls, labbook: LabBook, section: str, src_file: str,
                 dst_path: str, txid: Optional[str] = None) -> Dict[str, Any]:
        """Move the file at `src_file` to `dst_dir`. Filename removes
        upload ID if present. This operation does NOT commit or create an
        activity record.

        Args:
            labbook: Subject LabBook
            section: Section name (code, input, output)
            src_file: Full path of file to insert into
            dst_path: Path within section to insert `src_file`
            txid: Optional transaction id

        Returns:
           Full path to inserted file.
        """
        if not os.path.abspath(src_file):
            raise ValueError(f"Source file `{src_file}` not an absolute path")

        if not os.path.isfile(src_file):
            raise ValueError(f"Source file does not exist at `{src_file}`")

        r = call_subprocess(['git', 'check-ignore', os.path.basename(dst_path)],
                            cwd=labbook.root_dir, check=False)
        if dst_path and r and os.path.basename(dst_path) in r:
            logger.warning(f"File {dst_path} matches gitignore; "
                           f"not put into {str(labbook)}")
            raise FileOperationsException(f"`{dst_path}` matches "
                                          f"ignored pattern")

        labbook._validate_section(section)
        mdst_dir = _make_path_relative(dst_path)
        full_dst = os.path.join(labbook.root_dir, section, mdst_dir)
        full_dst = full_dst.replace('..', '')
        full_dst = full_dst.replace('~', '')

        # Force overwrite if file already exists
        if os.path.isfile(os.path.join(full_dst, os.path.basename(src_file))):
            os.remove(os.path.join(full_dst, os.path.basename(src_file)))

        if not os.path.isdir(os.path.dirname(full_dst)):
            os.makedirs(os.path.dirname(full_dst), exist_ok=True)

        fdst = shutil.move(src_file, full_dst)
        relpath = fdst.replace(os.path.join(labbook.root_dir, section), '')
        return labbook.get_file_info(section, relpath)

    @classmethod
    def insert_file(cls, labbook: LabBook, section: str, src_file: str,
                    dst_path: str = '') -> Dict[str, Any]:
        """ Move the file at `src_file` into the `dst_dir`, overwriting
        if a file already exists there. This calls `put_file()` under-
        the-hood, but will create an activity record.

        Args:
            labbook: Subject labbook
            section: Section name (code, input, output)
            src_file: Full path of file to insert into
            dst_path: Relative path within labbook where `src_file`
                      should be copied to

        Returns:
            dict: The inserted file's info
        """

        finfo = FileOperations.put_file(labbook=labbook, section=section,
                                        src_file=src_file, dst_path=dst_path)

        rel_path = os.path.join(section, finfo['key'])
        if shims.in_untracked(labbook.root_dir, section):
            logger.warning(f"Inserted file {rel_path} ({finfo['size']} bytes)"
                           f" to untracked section {section}. This will not"
                           f" be tracked by commits or activity records.")
            return finfo

        with labbook.lock_labbook():
            # If we are setting this section to be untracked
            activity_type, activity_detail_type, section_str = \
                labbook.get_activity_type_from_section(section)

            commit_msg = f"Added new {section_str} file {rel_path}"
            try:
                labbook.git.add(rel_path)
                commit = labbook.git.commit(commit_msg)
            except Exception as x:
                logger.error(x)
                os.remove(dst_path)
                raise FileOperationsException(x)

            # Create Activity record and detail
            _, ext = os.path.splitext(rel_path) or 'file'
            adr = ActivityDetailRecord(activity_detail_type, show=False,
                                       importance=0,
                                       action=ActivityAction.CREATE)
            adr.add_value('text/plain', commit_msg)
            ar = ActivityRecord(activity_type, message=commit_msg, show=True,
                                importance=255, linked_commit=commit.hexsha,
                                tags=[ext])
            ar.add_detail_object(adr)
            ars = ActivityStore(labbook)
            ars.create_activity_record(ar)

        return finfo

    @classmethod
    def complete_batch(cls, labbook: LabBook, txid: str,
                       cancel: bool = False, rollback: bool = False) -> None:
        """
        Indicate a batch upload is finished and sweep all new files.

        Args:
            labbook: Subject labbook
            txid: Transaction id (correlator)
            cancel: Indicate transaction finished but due to cancellation
            rollback: Undo all local changes if cancelled (default False)

        Returns:
            None
        """

        with labbook.lock_labbook():
            if cancel and rollback:
                logger.warning(f"Cancelled tx {txid}, doing git reset")
                call_subprocess(['git', 'reset', '--hard'],
                                cwd=labbook.root_dir)
            else:
                logger.info(f"Done batch upload {txid}, cancelled={cancel}")
                if cancel:
                    logger.warning("Sweeping aborted batch upload.")
                m = "Cancelled upload `{txid}`. " if cancel else ''
                labbook.sweep_uncommitted_changes(upload=True,
                                                  extra_msg=m,
                                                  show=True)
