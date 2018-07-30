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
import os
import copy

from lmcommon.labbook import LabBook
from lmcommon.activity import ActivityType, ActivityRecord, ActivityDetailType

from lmcommon.labbook.shims import process_sweep_status

from lmcommon.fixtures import mock_config_file


@pytest.fixture
def mock_lb(mock_config_file):
    lb = LabBook(mock_config_file[0])
    lb.new(username="test", name="sweep-test", description="sweepin", owner={"username": "test"})
    yield lb
    
    
def helper_gen_record():
    return ActivityRecord(ActivityType.LABBOOK,
                        message="--overwritten--",
                        show=False,
                        importance=255,
                        linked_commit="",
                        tags=['save'])


def helper_write_file(lb: LabBook, section: str, name: str, content: str):
    filename = os.path.join(lb.root_dir, section, name)
    with open(filename, 'wt') as f:
        f.write(content)


def helper_commit(lb, ar):
    git_status = lb.git.status()
    lb.git.add_all()
    lb.git.commit("Sweep of uncommitted changes")

    ar.linked_commit = lb.git.commit_hash

    return git_status, lb, ar


class TestShims(object):
    def test_process_sweep_status_new_code(self, mock_lb):
        helper_write_file(mock_lb, 'code', 'f1.txt', 'cat')
        git_status, lb, ar = helper_commit(mock_lb, helper_gen_record())

        ar, new_count, modified_count = process_sweep_status(ar, git_status, LabBook.infer_section_from_relative_path)

        assert new_count == 1
        assert modified_count == 0
        assert len(ar.detail_objects) == 1
        assert ar.type == ActivityType.CODE
        assert ar.detail_objects[0][1] == ActivityDetailType.CODE.value

        helper_write_file(mock_lb, 'code', 'f2.txt', 'cat')
        helper_write_file(mock_lb, 'code', 'f3.txt', 'cat')
        helper_write_file(mock_lb, 'code', 'f4.txt', 'cat')
        git_status, lb, ar = helper_commit(mock_lb, helper_gen_record())

        ar, new_count, modified_count = process_sweep_status(ar, git_status, LabBook.infer_section_from_relative_path)

        assert new_count == 3
        assert modified_count == 0
        assert len(ar.detail_objects) == 3
        assert ar.type == ActivityType.CODE
        assert ar.detail_objects[0][1] == ActivityDetailType.CODE.value
        assert ar.detail_objects[1][1] == ActivityDetailType.CODE.value
        assert ar.detail_objects[2][1] == ActivityDetailType.CODE.value
        assert "Created" in ar.detail_objects[0][3].data['text/markdown']

    def test_process_sweep_status_new_input(self, mock_lb):
        helper_write_file(mock_lb, 'input', 'f1.txt', 'cat')
        git_status, lb, ar = helper_commit(mock_lb, helper_gen_record())

        ar, new_count, modified_count = process_sweep_status(ar, git_status, LabBook.infer_section_from_relative_path)

        assert new_count == 1
        assert modified_count == 0
        assert ar.type == ActivityType.INPUT_DATA
        assert len(ar.detail_objects) == 1
        assert ar.detail_objects[0][1] == ActivityDetailType.INPUT_DATA.value

        helper_write_file(mock_lb, 'input', 'f2.txt', 'cat')
        helper_write_file(mock_lb, 'input', 'f3.txt', 'cat')
        helper_write_file(mock_lb, 'input', 'f4.txt', 'cat')
        git_status, lb, ar = helper_commit(mock_lb, helper_gen_record())

        ar, new_count, modified_count = process_sweep_status(ar, git_status, LabBook.infer_section_from_relative_path)

        assert new_count == 3
        assert modified_count == 0
        assert len(ar.detail_objects) == 3
        assert ar.type == ActivityType.INPUT_DATA
        assert ar.detail_objects[0][1] == ActivityDetailType.INPUT_DATA.value
        assert ar.detail_objects[1][1] == ActivityDetailType.INPUT_DATA.value
        assert ar.detail_objects[2][1] == ActivityDetailType.INPUT_DATA.value

    def test_process_sweep_status_new_output(self, mock_lb):
        helper_write_file(mock_lb, 'output', 'f1.txt', 'cat')
        git_status, lb, ar = helper_commit(mock_lb, helper_gen_record())

        ar, new_count, modified_count = process_sweep_status(ar, git_status, LabBook.infer_section_from_relative_path)

        assert new_count == 1
        assert modified_count == 0
        assert len(ar.detail_objects) == 1
        assert ar.type == ActivityType.OUTPUT_DATA
        assert ar.detail_objects[0][1] == ActivityDetailType.OUTPUT_DATA.value

        helper_write_file(mock_lb, 'output', 'f2.txt', 'cat')
        helper_write_file(mock_lb, 'output', 'f3.txt', 'cat')
        helper_write_file(mock_lb, 'output', 'f4.txt', 'cat')
        git_status, lb, ar = helper_commit(mock_lb, helper_gen_record())

        ar, new_count, modified_count = process_sweep_status(ar, git_status, LabBook.infer_section_from_relative_path)

        assert new_count == 3
        assert modified_count == 0
        assert len(ar.detail_objects) == 3
        assert ar.type == ActivityType.OUTPUT_DATA
        assert ar.detail_objects[0][1] == ActivityDetailType.OUTPUT_DATA.value
        assert ar.detail_objects[1][1] == ActivityDetailType.OUTPUT_DATA.value
        assert ar.detail_objects[2][1] == ActivityDetailType.OUTPUT_DATA.value

    def test_process_sweep_status_modified_code(self, mock_lb):
        helper_write_file(mock_lb, 'code', 'f1.txt', 'cat')
        helper_commit(mock_lb, helper_gen_record())
        helper_write_file(mock_lb, 'code', 'f1.txt', 'catdog')
        git_status, lb, ar = helper_commit(mock_lb, helper_gen_record())

        ar, new_count, modified_count = process_sweep_status(ar, git_status, LabBook.infer_section_from_relative_path)

        assert new_count == 0
        assert modified_count == 1
        assert len(ar.detail_objects) == 1
        assert ar.type == ActivityType.CODE
        assert ar.detail_objects[0][1] == ActivityDetailType.CODE.value
        assert "Modified" in ar.detail_objects[0][3].data['text/markdown']

        helper_write_file(mock_lb, 'code', 'f2.txt', 'cat')
        helper_write_file(mock_lb, 'code', 'f3.txt', 'cat')
        helper_write_file(mock_lb, 'code', 'f4.txt', 'cat')
        helper_commit(mock_lb, helper_gen_record())

        helper_write_file(mock_lb, 'code', 'f2.txt', 'pupper')
        helper_write_file(mock_lb, 'code', 'f3.txt', 'pupper')
        helper_write_file(mock_lb, 'code', 'f4.txt', 'pupper')
        git_status, lb, ar = helper_commit(mock_lb, helper_gen_record())

        ar, new_count, modified_count = process_sweep_status(ar, git_status, LabBook.infer_section_from_relative_path)

        assert new_count == 0
        assert len(ar.detail_objects) == 3
        assert ar.type == ActivityType.CODE
        assert ar.detail_objects[0][1] == ActivityDetailType.CODE.value
        assert ar.detail_objects[1][1] == ActivityDetailType.CODE.value
        assert ar.detail_objects[2][1] == ActivityDetailType.CODE.value
        assert "Modified" in ar.detail_objects[0][3].data['text/markdown']
        assert "Modified" in ar.detail_objects[1][3].data['text/markdown']
        assert "Modified" in ar.detail_objects[2][3].data['text/markdown']

    def test_process_sweep_status_modified_input(self, mock_lb):
        helper_write_file(mock_lb, 'input', 'f1.txt', 'cat')
        helper_commit(mock_lb, helper_gen_record())
        helper_write_file(mock_lb, 'input', 'f1.txt', 'catdog')
        git_status, lb, ar = helper_commit(mock_lb, helper_gen_record())

        ar, new_count, modified_count = process_sweep_status(ar, git_status, LabBook.infer_section_from_relative_path)

        assert new_count == 0
        assert modified_count == 1
        assert len(ar.detail_objects) == 1
        assert ar.type == ActivityType.INPUT_DATA
        assert ar.detail_objects[0][1] == ActivityDetailType.INPUT_DATA.value
        assert "Modified" in ar.detail_objects[0][3].data['text/markdown']

        helper_write_file(mock_lb, 'input', 'f2.txt', 'cat')
        helper_write_file(mock_lb, 'input', 'f3.txt', 'cat')
        helper_write_file(mock_lb, 'input', 'f4.txt', 'cat')
        helper_commit(mock_lb, helper_gen_record())

        helper_write_file(mock_lb, 'input', 'f2.txt', 'pupper')
        helper_write_file(mock_lb, 'input', 'f3.txt', 'pupper')
        helper_write_file(mock_lb, 'input', 'f4.txt', 'pupper')
        git_status, lb, ar = helper_commit(mock_lb, helper_gen_record())

        ar, new_count, modified_count = process_sweep_status(ar, git_status, LabBook.infer_section_from_relative_path)

        assert new_count == 0
        assert len(ar.detail_objects) == 3
        assert ar.type == ActivityType.INPUT_DATA
        assert ar.detail_objects[0][1] == ActivityDetailType.INPUT_DATA.value
        assert ar.detail_objects[1][1] == ActivityDetailType.INPUT_DATA.value
        assert ar.detail_objects[2][1] == ActivityDetailType.INPUT_DATA.value
        assert "Modified" in ar.detail_objects[0][3].data['text/markdown']
        assert "Modified" in ar.detail_objects[1][3].data['text/markdown']
        assert "Modified" in ar.detail_objects[2][3].data['text/markdown']

    def test_process_sweep_status_modified_output(self, mock_lb):
        helper_write_file(mock_lb, 'output', 'f1.txt', 'cat')
        helper_commit(mock_lb, helper_gen_record())
        helper_write_file(mock_lb, 'output', 'f1.txt', 'catdog')
        git_status, lb, ar = helper_commit(mock_lb, helper_gen_record())

        ar, new_count, modified_count = process_sweep_status(ar, git_status, LabBook.infer_section_from_relative_path)

        assert new_count == 0
        assert modified_count == 1
        assert len(ar.detail_objects) == 1
        assert ar.type == ActivityType.OUTPUT_DATA
        assert ar.detail_objects[0][1] == ActivityDetailType.OUTPUT_DATA.value
        assert "Modified" in ar.detail_objects[0][3].data['text/markdown']

        helper_write_file(mock_lb, 'output', 'f2.txt', 'cat')
        helper_write_file(mock_lb, 'output', 'f3.txt', 'cat')
        helper_write_file(mock_lb, 'output', 'f4.txt', 'cat')
        helper_commit(mock_lb, helper_gen_record())

        helper_write_file(mock_lb, 'output', 'f2.txt', 'pupper')
        helper_write_file(mock_lb, 'output', 'f3.txt', 'pupper')
        helper_write_file(mock_lb, 'output', 'f4.txt', 'pupper')
        git_status, lb, ar = helper_commit(mock_lb, helper_gen_record())

        ar, new_count, modified_count = process_sweep_status(ar, git_status, LabBook.infer_section_from_relative_path)

        assert new_count == 0
        assert len(ar.detail_objects) == 3
        assert ar.type == ActivityType.OUTPUT_DATA
        assert ar.detail_objects[0][1] == ActivityDetailType.OUTPUT_DATA.value
        assert ar.detail_objects[1][1] == ActivityDetailType.OUTPUT_DATA.value
        assert ar.detail_objects[2][1] == ActivityDetailType.OUTPUT_DATA.value
        assert "Modified" in ar.detail_objects[0][3].data['text/markdown']
        assert "Modified" in ar.detail_objects[1][3].data['text/markdown']
        assert "Modified" in ar.detail_objects[2][3].data['text/markdown']

    def test_process_sweep_status_mixed_new_no_modified(self, mock_lb):
        helper_write_file(mock_lb, 'code', 'f1.txt', 'cat')
        helper_write_file(mock_lb, 'input', 'f2.txt', 'cat')
        helper_write_file(mock_lb, 'output', 'f3.txt', 'cat')
        git_status, lb, ar = helper_commit(mock_lb, helper_gen_record())

        ar, new_count, modified_count = process_sweep_status(ar, git_status, LabBook.infer_section_from_relative_path)

        assert new_count == 3
        assert modified_count == 0
        assert ar.type == ActivityType.LABBOOK
        assert len(ar.detail_objects) == 3
        assert ar.detail_objects[0][1] == ActivityDetailType.INPUT_DATA.value
        assert ar.detail_objects[1][1] == ActivityDetailType.CODE.value
        assert ar.detail_objects[2][1] == ActivityDetailType.OUTPUT_DATA.value
        assert "Created" in ar.detail_objects[0][3].data['text/markdown']
        assert "Created" in ar.detail_objects[1][3].data['text/markdown']
        assert "Created" in ar.detail_objects[2][3].data['text/markdown']

    def test_process_sweep_status_no_new_mixed_modified(self, mock_lb):
        helper_write_file(mock_lb, 'code', 'f1.txt', 'cat')
        helper_write_file(mock_lb, 'input', 'f2.txt', 'cat')
        helper_write_file(mock_lb, 'output', 'f3.txt', 'cat')
        helper_commit(mock_lb, helper_gen_record())
        helper_write_file(mock_lb, 'code', 'f1.txt', 'pupper')
        helper_write_file(mock_lb, 'input', 'f2.txt', 'pupper')
        helper_write_file(mock_lb, 'output', 'f3.txt', 'pupper')
        git_status, lb, ar = helper_commit(mock_lb, helper_gen_record())

        ar, new_count, modified_count = process_sweep_status(ar, git_status, LabBook.infer_section_from_relative_path)

        assert new_count == 0
        assert modified_count == 3
        assert ar.type == ActivityType.LABBOOK
        assert len(ar.detail_objects) == 3
        assert ar.detail_objects[0][1] == ActivityDetailType.INPUT_DATA.value
        assert ar.detail_objects[1][1] == ActivityDetailType.CODE.value
        assert ar.detail_objects[2][1] == ActivityDetailType.OUTPUT_DATA.value
        assert "Modified" in ar.detail_objects[0][3].data['text/markdown']
        assert "Modified" in ar.detail_objects[1][3].data['text/markdown']
        assert "Modified" in ar.detail_objects[2][3].data['text/markdown']

    def test_process_sweep_status_mixed_new_same_modified(self, mock_lb):
        helper_write_file(mock_lb, 'code', 'f1.txt', 'cat')
        helper_write_file(mock_lb, 'code', 'f2.txt', 'cat')
        helper_commit(mock_lb, helper_gen_record())
        helper_write_file(mock_lb, 'code', 'f1.txt', 'pupper')
        helper_write_file(mock_lb, 'code', 'f2.txt', 'pupper')
        helper_write_file(mock_lb, 'code', 'f21.txt', 'dog')
        helper_write_file(mock_lb, 'input', 'f22.txt', 'dog')
        git_status, lb, ar = helper_commit(mock_lb, helper_gen_record())

        ar, new_count, modified_count = process_sweep_status(ar, git_status, LabBook.infer_section_from_relative_path)

        assert new_count == 2
        assert modified_count == 2
        assert ar.type == ActivityType.LABBOOK
        assert len(ar.detail_objects) == 4
        assert ar.detail_objects[0][1] == ActivityDetailType.INPUT_DATA.value
        assert ar.detail_objects[1][1] == ActivityDetailType.CODE.value
        assert ar.detail_objects[2][1] == ActivityDetailType.CODE.value
        assert ar.detail_objects[3][1] == ActivityDetailType.CODE.value
        assert "Created" in ar.detail_objects[0][3].data['text/markdown']
        assert "Created" in ar.detail_objects[1][3].data['text/markdown']
        assert "Modified" in ar.detail_objects[2][3].data['text/markdown']
        assert "Modified" in ar.detail_objects[3][3].data['text/markdown']

    def test_process_sweep_status_same_new_mixed_modified(self, mock_lb):
        helper_write_file(mock_lb, 'code', 'f1.txt', 'cat')
        helper_write_file(mock_lb, 'input', 'f2.txt', 'cat')
        helper_write_file(mock_lb, 'output', 'f3.txt', 'cat')
        helper_commit(mock_lb, helper_gen_record())
        helper_write_file(mock_lb, 'code', 'f1.txt', 'pupper')
        helper_write_file(mock_lb, 'input', 'f2.txt', 'pupper')
        helper_write_file(mock_lb, 'output', 'f3.txt', 'pupper')
        helper_write_file(mock_lb, 'code', 'f21.txt', 'dog')
        helper_write_file(mock_lb, 'code', 'f22.txt', 'dog')
        git_status, lb, ar = helper_commit(mock_lb, helper_gen_record())

        ar, new_count, modified_count = process_sweep_status(ar, git_status, LabBook.infer_section_from_relative_path)

        assert new_count == 2
        assert modified_count == 3
        assert ar.type == ActivityType.LABBOOK
        assert len(ar.detail_objects) == 5
        assert ar.detail_objects[0][1] == ActivityDetailType.INPUT_DATA.value
        assert ar.detail_objects[1][1] == ActivityDetailType.CODE.value
        assert ar.detail_objects[2][1] == ActivityDetailType.CODE.value
        assert ar.detail_objects[3][1] == ActivityDetailType.CODE.value
        assert ar.detail_objects[4][1] == ActivityDetailType.OUTPUT_DATA.value
        assert "Modified" in ar.detail_objects[0][3].data['text/markdown']
        assert "Created" in ar.detail_objects[1][3].data['text/markdown']
        assert "Modified" in ar.detail_objects[2][3].data['text/markdown']
        assert "Created" in ar.detail_objects[3][3].data['text/markdown']

    def test_process_sweep_status_mixed_new_mixed_modified(self, mock_lb):
        helper_write_file(mock_lb, 'code', 'f1.txt', 'cat')
        helper_write_file(mock_lb, 'input', 'f2.txt', 'cat')
        helper_commit(mock_lb, helper_gen_record())
        helper_write_file(mock_lb, 'code', 'f1.txt', 'pupper')
        helper_write_file(mock_lb, 'input', 'f2.txt', 'pupper')
        helper_write_file(mock_lb, 'code', 'f21.txt', 'dog')
        helper_write_file(mock_lb, 'output', 'f22.txt', 'dog')
        git_status, lb, ar = helper_commit(mock_lb, helper_gen_record())

        ar, new_count, modified_count = process_sweep_status(ar, git_status, LabBook.infer_section_from_relative_path)

        assert new_count == 2
        assert modified_count == 2
        assert ar.type == ActivityType.LABBOOK
        assert len(ar.detail_objects) == 4
        assert ar.detail_objects[0][1] == ActivityDetailType.INPUT_DATA.value
        assert ar.detail_objects[1][1] == ActivityDetailType.CODE.value
        assert ar.detail_objects[2][1] == ActivityDetailType.CODE.value
        assert ar.detail_objects[3][1] == ActivityDetailType.OUTPUT_DATA.value
        assert "Modified" in ar.detail_objects[0][3].data['text/markdown']
        assert "Created" in ar.detail_objects[1][3].data['text/markdown']
        assert "Modified" in ar.detail_objects[2][3].data['text/markdown']
        assert "Created" in ar.detail_objects[3][3].data['text/markdown']

    def test_process_sweep_status_same_new_same_modified(self, mock_lb):
        helper_write_file(mock_lb, 'input', 'f1.txt', 'cat')
        helper_write_file(mock_lb, 'input', 'f2.txt', 'cat')
        helper_commit(mock_lb, helper_gen_record())
        helper_write_file(mock_lb, 'input', 'f1.txt', 'pupper')
        helper_write_file(mock_lb, 'input', 'f2.txt', 'pupper')
        helper_write_file(mock_lb, 'code', 'f21.txt', 'dog')
        helper_write_file(mock_lb, 'code', 'f22.txt', 'dog')
        git_status, lb, ar = helper_commit(mock_lb, helper_gen_record())

        ar, new_count, modified_count = process_sweep_status(ar, git_status, LabBook.infer_section_from_relative_path)

        assert new_count == 2
        assert modified_count == 2
        assert ar.type == ActivityType.LABBOOK
        assert len(ar.detail_objects) == 4
        assert ar.detail_objects[0][1] == ActivityDetailType.INPUT_DATA.value
        assert ar.detail_objects[1][1] == ActivityDetailType.INPUT_DATA.value
        assert ar.detail_objects[2][1] == ActivityDetailType.CODE.value
        assert ar.detail_objects[3][1] == ActivityDetailType.CODE.value
        assert "Modified" in ar.detail_objects[0][3].data['text/markdown']
        assert "Modified" in ar.detail_objects[1][3].data['text/markdown']
        assert "Created" in ar.detail_objects[2][3].data['text/markdown']
        assert "Created" in ar.detail_objects[3][3].data['text/markdown']
