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

import pprint
import pytest
import os

from lmcommon.fixtures import mock_labbook
from lmcommon.files import FileOperations, FileOperationsException


class TestFileOps(object):
    def test_set_new_lb_section_for_large_files(self, mock_labbook):
        x, y, lb = mock_labbook

        assert FileOperations.is_set_untracked(labbook=lb, section='input') is False

        FileOperations.set_untracked(labbook=lb, section='input')

        assert FileOperations.is_set_untracked(labbook=lb, section='input') is True
        assert FileOperations.is_set_untracked(labbook=lb, section='code') is False

        # 1 - Ensure there are no untracked changes after the set operation
        s = lb.git.status()
        for key in s.keys():
            assert not s[key]

        # 2 - Add a file to the input directory using the old-fashioned add file op.
        with open('/tmp/unittestfile', 'w') as f:
            f.write('------------------------\n')
        r = lb.insert_file(section="input", src_file=f.name, dst_dir='')
        assert os.path.isfile(os.path.join(lb.root_dir, 'input', 'unittestfile'))

        # 3 - Make sure the new file exists but is not tracked (i.e., the git commit is the same)
        s = lb.git.status()
        for key in s.keys():
            assert not s[key]

    def test_make_sure_cannot_set_when_files_already_exist_in_section(self, mock_labbook):
        x, y, lb = mock_labbook

        # 2 - Add a file to the input directory using the old-fashioned add file op.
        with open('/tmp/unittestfile', 'w') as f:
            f.write('xxxxxxxxxxxxxxxč')
        r = lb.insert_file(section="input", src_file=f.name, dst_dir='')
        assert os.path.isfile(os.path.join(lb.root_dir, 'input', 'unittestfile'))

        with pytest.raises(FileOperationsException):
            FileOperations.set_untracked(labbook=lb, section='input')

        assert FileOperations.is_set_untracked(labbook=lb, section='input') is False

    def test_make_sure_cannot_set_untracked_twice(self, mock_labbook):
        x, y, lb = mock_labbook

        hash_0 = lb.git.commit_hash
        FileOperations.set_untracked(labbook=lb, section='input')

        # 1 - Ensure there are no untracked changes after the set operation
        s = lb.git.status()

        for key in s.keys():
            assert not s[key]

        # 2 - Add a file to the input directory using the old-fashioned add file op.
        hash_1 = lb.git.commit_hash
        with open('/tmp/unittestfile', 'w') as f:
            f.write('------------------------\n')
        r = lb.insert_file(section="input", src_file=f.name, dst_dir='')
        hash_2 = lb.git.commit_hash
        assert os.path.isfile(os.path.join(lb.root_dir, 'input', 'unittestfile'))

        # Cannot set this field twice.
        with pytest.raises(FileOperationsException):
            FileOperations.set_untracked(labbook=lb, section='input')
        hash_3 = lb.git.commit_hash

        assert hash_0 != hash_1
        assert hash_1 == hash_2
        assert hash_2 == hash_3
        assert FileOperations.is_set_untracked(labbook=lb, section='input') is True

    def test_with_the_whole_suite_of_file_operations(self, mock_labbook):
        x, y, lb = mock_labbook

        hash_0 = lb.git.commit_hash
        FileOperations.set_untracked(labbook=lb, section='input')
        hash_1 = lb.git.commit_hash
        assert hash_0 != hash_1

        with open('/tmp/unittestfile', 'w') as f:
            f.write('àbčdęfghįjkłmñöpqrštūvwxÿż0123456789')
        r = lb.insert_file(section="input", src_file=f.name, dst_dir='')
        hash_2 = lb.git.commit_hash

        deleted = lb.delete_file(section='input', relative_path='unittestfile')
        hash_3 = lb.git.commit_hash
        assert deleted is True
        assert not os.path.exists(os.path.join(lb.root_dir, 'input', 'unittestfile'))
        assert hash_2 == hash_3

        lb.makedir('input/sample-untracked-dir/nested-dir')
        hash_4 = lb.git.commit_hash
        assert hash_3 == hash_4
        with open('/tmp/unittestfile', 'w') as f:
            f.write('aaaaaæ')
        lb.insert_file(section='input', src_file=f.name, dst_dir='sample-untracked-dir/nested-dir')
        hash_5 = lb.git.commit_hash
        assert hash_4 == hash_5

        lb.move_file(section='input', src_rel_path='sample-untracked-dir/nested-dir/unittestfile', dst_rel_path='unittestfile')
        assert not os.path.exists(os.path.join(lb.root_dir, 'input', 'sample-untracked-dir/nested-dir/unittestfile'))
        assert os.path.exists(os.path.join(lb.root_dir, 'input', 'unittestfile'))
        hash_6 = lb.git.commit_hash
        assert hash_5 == hash_6

        lb.delete_file(section='input', relative_path='sample-untracked-dir/nested-dir', directory=True)
        hash_7 = lb.git.commit_hash
        assert hash_6 == hash_7

