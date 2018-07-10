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
import pprint

from lmcommon.labbook import LabBook
from lmcommon.files import FileOperations as FO
from lmcommon.fixtures import mock_config_file, mock_labbook, remote_labbook_repo, sample_src_file


class TestLabbookFileOperations(object):
    def test_insert_file_success_1(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-1", description="validate tests.")
        new_file_data = FO.insert_file(lb, "code", sample_src_file)
        base_name = os.path.basename(sample_src_file)
        assert os.path.exists(os.path.join(lb.root_dir, 'code', base_name))
        assert new_file_data['key'] == f'{base_name}'
        assert new_file_data['is_dir'] is False
        assert new_file_data['is_favorite'] is False

    def test_insert_file_upload_id(self, mock_config_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-100", description="validate tests.")

        test_file = os.path.join(tempfile.gettempdir(), "asdfasdf-testfile.txt")
        with open(test_file, 'wt') as sample_f:
            # Fill sample file with some deterministic crap
            sample_f.write("n4%nm4%M435A EF87kn*C" * 40)

        # This is basically checking for rename
        new_file_data = FO.insert_file(lb, "code", test_file, "testfile.txt")

        assert os.path.exists(os.path.join(lb.root_dir, 'code', 'testfile.txt'))
        assert new_file_data['key'] == 'testfile.txt'
        assert new_file_data['is_dir'] is False

    def test_insert_file_success_2(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-4", description="validate tests.")
        lb.makedir("output/testdir")
        new_file_data = FO.insert_file(lb, "output", sample_src_file, "testdir")
        base_name = os.path.basename(new_file_data['key'])
        assert os.path.exists(os.path.join(lb.root_dir, 'output', 'testdir', base_name))
        assert new_file_data['key'] == f'testdir/{base_name}'
        assert new_file_data['is_dir'] is False

    def test_insert_and_make_intermediary_directories(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="unittest-intermediary-dir", description="validate tests.")
        bn = os.path.basename(sample_src_file)
        FO.insert_file(lb, "code", sample_src_file, "/super/random/dir/inside")
        p = os.path.join(lb.root_dir, 'code', "super/random/dir/inside")
        print(p)
        assert os.path.exists(p)

    def test_insert_file_fail_due_to_gitignore(self, mock_config_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-gitignored-file", description="validate tests.")

        git_hash_1 = lb.git.commit_hash
        lines = [l.strip() for l in open(os.path.join(lb.root_dir, '.gitignore')).readlines()]
        pprint.pprint(lines)
        assert any(['.DS_Store' in l for l in lines])

        # Note: .DS_Store is in the gitignore directory.
        test_file = os.path.join(tempfile.gettempdir(), ".DS_Store")
        with open(test_file, 'wt') as sample_f:
            # Fill sample file with some deterministic crap
            sample_f.write("This file should not be allowed to be inserted into labbook. " * 40)

        git_hash_2 = lb.git.commit_hash
        with pytest.raises(Exception):
            r = lb.insert_file('input', src_file=sample_f.name, dst_dir='')

        # Make sure no commits were made
        assert git_hash_1 == git_hash_2
        # Make sure the inserted file that doesn't match wasn't added.
        assert '.DS_Store' not in os.listdir(os.path.join(lb.root_dir, 'input'))

    def test_remove_file_success(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-1", description="validate tests.")
        new_file_data = FO.insert_file(lb, "code", sample_src_file)
        base_name = os.path.basename(new_file_data['key'])

        assert os.path.exists(os.path.join(lb.root_dir, 'code', base_name))
        lb.delete_file('code', base_name)
        assert not os.path.exists(os.path.join(lb.root_dir, 'code', base_name))

    def test_remove_file_fail(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-1", description="validate tests.")
        FO.insert_file(lb, "code", sample_src_file)
        new_file_path = os.path.join('blah', 'invalid.txt')
        with pytest.raises(ValueError):
            lb.delete_file('code', new_file_path)

    def test_remove_dir(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-remove-dir-1", description="validate tests.")
        lb.makedir("output/testdir")
        new_file_path = FO.insert_file(lb, "output", sample_src_file, "testdir")
        base_name = os.path.basename(new_file_path['key'])

        assert os.path.exists(os.path.join(lb.root_dir, 'output', 'testdir', base_name))
        # Note! Now that remove() uses force=True, no special action is needed for directories.
        # Delete the directory
        lb.delete_file("output", "testdir", directory=True)
        assert not os.path.exists(os.path.join(lb.root_dir, 'output', 'testdir', base_name))
        assert not os.path.exists(os.path.join(lb.root_dir, 'output', 'testdir'))

    def test_move_file_as_rename_in_same_dir(self, mock_config_file, sample_src_file):
        # Create lb
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-1", description="validate tests.")

        # insert file
        new_file_data = FO.insert_file(lb, "code", sample_src_file, '')
        base_name = os.path.basename(new_file_data['key'])
        assert os.path.exists(os.path.join(lb.root_dir, 'code', base_name))
        assert new_file_data['key'] == base_name

        # move to rename
        moved_rel_path = os.path.join(f'{base_name}.MOVED')
        lb.move_file('code', new_file_data['key'], moved_rel_path)
        assert not os.path.exists(os.path.join(lb.root_dir, 'code', base_name))
        assert os.path.exists(os.path.join(lb.root_dir, 'code', f'{base_name}.MOVED'))
        assert os.path.isfile(os.path.join(lb.root_dir, 'code', f'{base_name}.MOVED'))

    def test_move_file_subdirectory(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-1", description="validate tests.")
        new_file_data = FO.insert_file(lb, "code", sample_src_file)
        base_name = os.path.basename(new_file_data['key'])
        assert os.path.exists(os.path.join(lb.root_dir, 'code', base_name))

        # make new subdir
        os.makedirs(os.path.join(lb.root_dir, 'code', 'subdir'))

        moved_abs_data = lb.move_file('code',
                                      base_name,
                                      os.path.join('subdir', base_name))

        assert moved_abs_data['key'] == os.path.join('subdir', base_name)
        assert moved_abs_data['is_dir'] is False

        assert os.path.exists(os.path.join(lb.root_dir, 'code', 'subdir'))
        assert os.path.isdir(os.path.join(lb.root_dir, 'code', 'subdir'))
        assert os.path.exists(os.path.join(lb.root_dir, 'code', 'subdir', base_name))
        assert os.path.isfile(os.path.join(lb.root_dir, 'code', 'subdir', base_name))
        assert not os.path.exists(os.path.join(lb.root_dir, 'code', base_name))

    def test_move_loaded_directory(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-1", description="validate tests.")
        new_file_data = FO.insert_file(lb, "code", sample_src_file)
        base_name = os.path.basename(new_file_data['key'])
        assert os.path.exists(os.path.join(lb.root_dir, 'code', base_name))

        # make new subdir with a file in it
        os.makedirs(os.path.join(lb.root_dir, 'code', 'subdir'))
        lb.move_file("code", base_name, os.path.join('subdir', base_name))

        # Move entire directory
        lb.move_file("code", 'subdir', 'subdir_moved')

        assert not os.path.exists(os.path.join(lb.root_dir, 'code', 'subdir'))
        assert os.path.exists(os.path.join(lb.root_dir, 'code', 'subdir_moved'))
        assert os.path.isdir(os.path.join(lb.root_dir, 'code', 'subdir_moved'))
        assert os.path.exists(os.path.join(lb.root_dir, 'code', 'subdir_moved', base_name))
        assert os.path.isfile(os.path.join(lb.root_dir, 'code', 'subdir_moved', base_name))

    def test_makedir_simple(self, mock_config_file):
        # Note that "score" refers to the count of .gitkeep files.
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-1", description="validate tests.")
        long_dir = "code/non/existant/dir/should/now/be/made"
        dirs = ["code/cat_dir", "code/dog_dir", "code/mouse_dir/", "code/mouse_dir/new_dir", long_dir]
        for d in dirs:
            lb.makedir(d)
            assert os.path.isdir(os.path.join(lb.root_dir, d))
            assert os.path.isfile(os.path.join(lb.root_dir, d, '.gitkeep'))
        score = 0
        for root, dirs, files in os.walk(os.path.join(lb.root_dir, 'code', 'non')):
            for f in files:
                if f == '.gitkeep':
                    score += 1
        # Ensure that count of .gitkeep files equals the number of subdirs, excluding the code dir.
        assert score == len(LabBook._make_path_relative(long_dir).split(os.sep)) - 1

    def test_makedir_record(self, mock_config_file):
        # Note that "score" refers to the count of .gitkeep files.
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-mkdir-1", description="validate tests.")

        assert os.path.exists(os.path.join(lb.root_dir, 'code', 'test')) is False

        lb.makedir("code/test", create_activity_record=True)

        assert os.path.exists(os.path.join(lb.root_dir, 'code', 'test')) is True
        assert lb.is_repo_clean is True

        lb.makedir("code/test2", create_activity_record=False)
        assert os.path.exists(os.path.join(lb.root_dir, 'code', 'test2')) is True
        assert lb.is_repo_clean is False

    def test_walkdir(self, mock_config_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-1", description="validate tests.")
        dirs = ["code/cat_dir", "code/dog_dir", "code/mouse_dir/", "code/mouse_dir/new_dir", "code/.hidden_dir"]
        for d in dirs:
            lb.makedir(d)

        for d in ['.hidden_dir/', '', 'dog_dir', 'mouse_dir/new_dir/']:
            open('/tmp/myfile.c', 'w').write('data')
            FO.insert_file(lb, 'code', '/tmp/myfile.c', d)

        dir_walks_hidden = lb.walkdir('code', show_hidden=True)
        assert any([os.path.basename('/tmp/myfile.c') in d['key'] for d in dir_walks_hidden])
        assert not any(['.git' in d['key'].split(os.path.sep) for d in dir_walks_hidden])
        assert not any(['.gigantum' in d['key'] for d in dir_walks_hidden])
        assert all([d['key'][0] != '/' for d in dir_walks_hidden])

        # Spot check some entries
        assert len(dir_walks_hidden) == 15
        assert dir_walks_hidden[0]['key'] == '.hidden_dir/'
        assert dir_walks_hidden[0]['is_dir'] is True
        assert dir_walks_hidden[3]['key'] == 'mouse_dir/'
        assert dir_walks_hidden[3]['is_dir'] is True
        assert dir_walks_hidden[6]['key'] == '.hidden_dir/.gitkeep'
        assert dir_walks_hidden[6]['is_dir'] is False
        assert dir_walks_hidden[13]['key'] == 'mouse_dir/new_dir/.gitkeep'
        assert dir_walks_hidden[13]['is_dir'] is False

        # Since the file is in a hidden directory, it should not be found.
        dir_walks = lb.walkdir('code')
        # Spot check some entries
        assert len(dir_walks) == 7
        assert dir_walks[0]['key'] == 'cat_dir/'
        assert dir_walks[0]['is_dir'] is True
        assert dir_walks[1]['key'] == 'dog_dir/'
        assert dir_walks[1]['is_dir'] is True
        assert dir_walks[2]['key'] == 'mouse_dir/'
        assert dir_walks[2]['is_dir'] is True
        assert dir_walks[3]['is_dir'] is False
        assert dir_walks[4]['is_dir'] is False
        assert dir_walks[5]['is_dir'] is True
        assert dir_walks[5]['key'] == 'mouse_dir/new_dir/'
        assert dir_walks[6]['is_dir'] is False

    def test_listdir(self, mock_config_file, sample_src_file):
        def write_test_file(base, name):
            with open(os.path.join(base, name), 'wt') as f:
                f.write("Blah blah")

        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-listdir", description="validate tests.")
        dirs = ["code/new_dir", ".hidden_dir"]
        for d in dirs:
            lb.makedir(d)
        write_test_file(lb.root_dir, 'test1.txt')
        write_test_file(lb.root_dir, 'test2.txt')
        write_test_file(lb.root_dir, '.hidden.txt')
        write_test_file(lb.root_dir, 'code/test_subdir1.txt')
        write_test_file(lb.root_dir, 'code/test_subdir2.txt')
        write_test_file(lb.root_dir, 'code/new_dir/tester.txt')

        # List just the code dir
        data = lb.listdir("code", base_path='')
        assert len(data) == 3
        assert data[0]['key'] == 'new_dir/'
        assert data[1]['key'] == 'test_subdir1.txt'
        assert data[2]['key'] == 'test_subdir2.txt'

        data = lb.listdir("input", base_path='')
        assert len(data) == 0

        # List just the code/subdir dir
        data = lb.listdir("code", base_path='new_dir')
        assert len(data) == 1
        assert data[0]['key'] == 'new_dir/tester.txt'

    def test_listdir_expect_error(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-listdir", description="validate tests.")

        with pytest.raises(ValueError):
            lb.listdir("code", base_path='blah')

    def test_walkdir_with_favorites(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-1", description="validate tests.")
        dirs = ["code/cat_dir", "code/dog_dir"]
        for d in dirs:
            lb.makedir(d)

        sfile = '/tmp/testwalkdirwithfavorites.file'
        for d in ['', 'dog_dir', 'cat_dir']:
            open(sfile, 'w').write('xxx')
            FO.insert_file(lb, 'code', sfile, d)

        sample_filename = os.path.basename(sfile)

        # Since the file is in a hidden directory, it should not be found.
        dir_walks = lb.walkdir('code')
        # Spot check some entries
        assert len(dir_walks) == 5
        assert dir_walks[0]['key'] == 'cat_dir/'
        assert dir_walks[0]['is_dir'] is True
        assert dir_walks[0]['is_favorite'] is False
        assert dir_walks[1]['key'] == 'dog_dir/'
        assert dir_walks[1]['is_dir'] is True
        assert dir_walks[1]['is_favorite'] is False
        assert dir_walks[2]['is_favorite'] is False
        assert dir_walks[2]['is_dir'] is False
        assert dir_walks[3]['is_favorite'] is False
        assert dir_walks[3]['is_dir'] is False
        assert dir_walks[4]['is_favorite'] is False
        assert dir_walks[4]['is_dir'] is False

        lb.create_favorite("code", sample_filename, description="Fav 1")
        lb.create_favorite("code", f"dog_dir/{sample_filename}", description="Fav 2")
        lb.create_favorite("code", f"cat_dir/", description="Fav 3", is_dir=True)

        dir_walks = lb.walkdir('code')
        # Spot check some entries
        assert len(dir_walks) == 5
        assert dir_walks[0]['key'] == 'cat_dir/'
        assert dir_walks[0]['is_dir'] is True
        assert dir_walks[0]['is_favorite'] is True
        assert dir_walks[1]['key'] == 'dog_dir/'
        assert dir_walks[1]['is_dir'] is True
        assert dir_walks[1]['is_favorite'] is False
        assert dir_walks[2]['is_favorite'] is True
        assert dir_walks[2]['is_dir'] is False
        assert dir_walks[3]['is_favorite'] is False
        assert dir_walks[3]['is_dir'] is False
        assert dir_walks[4]['is_favorite'] is True
        assert dir_walks[4]['is_dir'] is False
