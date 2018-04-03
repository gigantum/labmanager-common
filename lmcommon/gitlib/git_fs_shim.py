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
from lmcommon.gitlib.git_fs import GitFilesystem
from lmcommon.logging import LMLogger
import subprocess
from typing import Optional
from git import Repo
import os

logger = LMLogger.get_logger()


class GitFilesystemShimmed(GitFilesystem):

    def add(self, filename):
        """Add a file to a commit

        Args:
            filename(str): Filename to add.

        Returns:
            None
        """
        logger.info("Adding file {} to Git repository in {}".format(filename, self.working_directory))
        self.repo.git.add([filename])

    #def clone(self, source, directory: Optional[str] = None):
    #    """Clone a repo
#
    #    Args:
    #        source (str): Git ssh or https string to clone
    #        directory(str): Directory to clone into (optional argument)
#
    #    Returns:
    #        None
    #    """
    #    if self.repo:
    #        raise ValueError("Cannot init an existing git repository. Choose a different working directory")
#
    #    logger.info("Cloning Git repository from {} into {}".format(source, directory or self.working_directory))
#
    #    # Clone repo
    #    subprocess.run(f"git lfs clone {source} {directory or self.working_directory}",
    #                   shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#
    #    # Create gitpython object
    #    self.repo = Repo(directory or self.working_directory)
#