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

import os

from lmcommon.labbook import LabBook
from lmcommon.files.utils import in_untracked


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
        # Note: os.walk does NOT follow symlinks, but does follow hidden dirs/files.
        total_bytes = 0
        for dirpath, dirnames, filenames in os.walk(labbook.root_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_bytes += os.path.getsize(fp)
        return total_bytes

    @classmethod
    def is_set_untracked(cls, labbook: LabBook, section: str) -> bool:
        """ Return True if the given labbook section is set to be untracked (to work around git performance issues
        when files are large).

        Args:
            labbook: Subject labbook
            section: Section one of code, input, or output.

        Returns:
            bool indicating whether the labbook's section is set as untracked
        """
        return in_untracked(labbook.root_dir, section)

    @classmethod
    def set_untracked(cls, labbook: LabBook, section: str) -> LabBook:
        """ Configure a labbook subdirectory to be untracked so large files don't cause Git performance degradation.
        Under the hood this just makes the directory untracked by Git, such that there are no large git indexes
        for the files. Note that this must be set before uploading files to the given `section`.

        Args:
            labbook: Subject labbook
            section: Section to set untracked - one of code, input, or output.

        Returns:
            None

        Raises:
            FileOperationsException if (1) section already contains files or (2) other problem.
        """
        section_path = os.path.join(labbook.root_dir, section.replace('/', ''))
        if not os.path.exists(section_path):
            raise FileOperationsException(f'Section {section} not found in {str(labbook)}')

        filelist = os.listdir(section_path)
        if not(len(filelist) == 1 and filelist[0] == '.gitkeep'):
            raise FileOperationsException(f'Files already exist in {str(labbook)} section {section}')

        append_lines = [f'# Ignore files for section {section} - fix to improve Git performance with large files',
                        f'{section}/*', f'!{section}/.gitkeep']

        if cls.is_set_untracked(labbook, section):
            raise FileOperationsException(f'Section {section} already untracked in {str(labbook)}')

        with labbook.lock_labbook():
            with open(os.path.join(labbook.root_dir, '.gitignore'), 'a') as gi_file:
                gi_file.write('\n'.join([''] + append_lines + ['']))

            labbook.git.add(os.path.join(labbook.root_dir, '.gitignore'))
            labbook.git.commit(f"Set section {section} as untracked as fix for Git performance")

        return labbook