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

from typing import Optional, Tuple
from lmcommon.labbook import LabBook, LabbookException


class GitWorkflowException(Exception):
    pass


class MergeError(GitWorkflowException):
    pass


class GitWorkflow(object):

    def __init__(self, labbook: LabBook) -> None:
        self.labbook = labbook

    def publish(self, username: str, access_token: Optional[str] = None, remote: str = "origin"):
        self.labbook.publish(username=username, access_token=access_token, remote=remote)

    def sync(self, username: str, remote: str = "origin", force: bool = False):
        try:
            self.labbook.sync(username=username, remote=remote, force=force)
        except LabbookException as e:
            if 'cannot merge' in str(e).lower():
                raise MergeError(str(e).split('\n')[-1])
            raise

    def add_remote(self, remote_name: str, url: str):
        self.labbook.add_remote(remote_name=remote_name, url=url)
