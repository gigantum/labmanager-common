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


import pytest
import tempfile
import os
import uuid
import shutil
import yaml

import git

from lmcommon.imagebuilder import ImageBuidler



@pytest.fixture()
def clone_env_repo():
    with tempfile.TemporaryDirectory() as tempdir:
        repo = git.Repo()
        repo.clone_from("https://github.com/gig-dev/environment-components-dev.git", tempdir)
        yield tempdir


class TestImageBuilder(object):
    def test_checkout_successful(self, clone_env_repo):
        assert os.path.exists(
            os.path.join(clone_env_repo, "base_image/gigantum/ubuntu1604-python3/ubuntu1604-python3-v0_1_0.yaml"))
