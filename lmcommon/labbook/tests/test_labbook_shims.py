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
import mock
import os
import shutil
import yaml
import pprint
import git

from lmcommon.labbook import LabBook, LabbookException
from lmcommon.dispatcher.jobs import import_labboook_from_zip
from lmcommon.fixtures import (mock_config_file, mock_labbook, remote_labbook_repo,
                               _MOCK_create_remote_repo)


LBK_ARCHIVE_PATH = '/home/circleci/project/lmcommon/labbook/tests/test-export_2017000000.lbk' \
    if os.environ.get('CIRCLECI') else 'test-export_2017000000.lbk'

LBK_FS_PATH = '/home/circleci/gigantum/test/test/labbooks/test-export' \
    if os.environ.get('CIRCLECI') else '/mnt/gigantum/test/test/labbooks/test-export'


class TestLabbookShims(object):
    def test_lbk_exists(self):
        # Just make sure that the archive exists in the local dir.
        assert os.path.isfile(LBK_ARCHIVE_PATH)

    def test_import_from_archive(self, mock_config_file):
        """"""
        shutil.rmtree(LBK_FS_PATH, ignore_errors=True)
        p = import_labboook_from_zip(archive_path=LBK_ARCHIVE_PATH, username='test',
                                     owner='test')
        l = LabBook(mock_config_file[0])
        l.from_directory(p)
        assert l.active_branch == 'gm.workspace-test'

    @mock.patch('lmcommon.labbook.LabBook._create_remote_repo', new=_MOCK_create_remote_repo)
    def test_shim_on_publish(self, mock_config_file):
        """"""
        shutil.rmtree(LBK_FS_PATH, ignore_errors=True)
        p = import_labboook_from_zip(archive_path=LBK_ARCHIVE_PATH, username='test',
                                     owner='test')
        l = LabBook(mock_config_file[0])
        l.from_directory(p)
        assert l.active_branch == 'gm.workspace-test'

        l.git.checkout('master')
        l.git.merge('gm.workspace-test')
        l.git.add_all()
        l.git.commit('m')
        l.git.delete_branch('gm.workspace')
        l.git.delete_branch('gm.workspace-test')
        assert l.active_branch == 'master'
        l.publish(username='test')

        # Validate that the workspace branch is created
        assert l.active_branch == 'gm.workspace-test'
