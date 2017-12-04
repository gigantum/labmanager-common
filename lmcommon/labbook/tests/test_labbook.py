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
import shutil
import yaml

import git

from lmcommon.labbook import LabBook, LabbookException
from lmcommon.fixtures import mock_config_file, mock_labbook, remote_labbook_repo


@pytest.fixture()
def sample_src_file():
    with tempfile.NamedTemporaryFile(mode="w") as sample_f:
        # Fill sample file with some deterministic crap
        sample_f.write("n4%nm4%M435A EF87kn*C" * 40)
        sample_f.seek(0)
        yield sample_f.name



class TestLabBook(object):

    def test_create_labbook(self, mock_config_file):
        """Test creating an empty labbook"""
        lb = LabBook(mock_config_file[0])

        labbook_dir = lb.new(username="test", name="labbook1", description="my first labbook",
                             owner={"username": "test"})

        assert labbook_dir == os.path.join(mock_config_file[1], "test", "test", "labbooks", "labbook1")
        assert type(lb) == LabBook

        # Validate directory structure
        assert os.path.isdir(os.path.join(labbook_dir, "code")) is True
        assert os.path.isdir(os.path.join(labbook_dir, "input")) is True
        assert os.path.isdir(os.path.join(labbook_dir, "output")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "env")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "notes")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "notes", "log")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "notes", "index")) is True

        # Validate labbook data file
        with open(os.path.join(labbook_dir, ".gigantum", "labbook.yaml"), "rt") as data_file:
            data = yaml.load(data_file)

        assert data["labbook"]["name"] == "labbook1"
        assert data["labbook"]["description"] == "my first labbook"
        assert "id" in data["labbook"]
        assert data["owner"]["username"] == "test"

        # Validate baseline dockerfile
        with open(os.path.join(labbook_dir, ".gigantum", "env", "Dockerfile"), "rt") as docker_file:
            data = docker_file.readlines()

        assert data[0] == "FROM ubuntu:16.04"

    def test_create_labbook_no_username(self, mock_config_file):
        """Test creating an empty labbook"""
        lb = LabBook(mock_config_file[0])

        labbook_dir = lb.new(name="labbook1", description="my first labbook",
                             owner={"username": "test"})

        assert labbook_dir == os.path.join(mock_config_file[1], "test", "test", "labbooks", "labbook1")
        assert type(lb) == LabBook

        # Validate directory structure
        assert os.path.isdir(os.path.join(labbook_dir, "code")) is True
        assert os.path.isdir(os.path.join(labbook_dir, "input")) is True
        assert os.path.isdir(os.path.join(labbook_dir, "output")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "env")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "notes")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "notes", "log")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "notes", "index")) is True

        # Validate labbook data file
        with open(os.path.join(labbook_dir, ".gigantum", "labbook.yaml"), "rt") as data_file:
            data = yaml.load(data_file)

        assert data["labbook"]["name"] == "labbook1"
        assert data["labbook"]["description"] == "my first labbook"
        assert "id" in data["labbook"]
        assert data["owner"]["username"] == "test"

        # Validate baseline dockerfile
        with open(os.path.join(labbook_dir, ".gigantum", "env", "Dockerfile"), "rt") as docker_file:
            data = docker_file.readlines()

        assert data[0] == "FROM ubuntu:16.04"

    def test_create_labbook_that_exists(self, mock_config_file):
        """Test trying to create a labbook with a name that already exists locally"""
        lb = LabBook(mock_config_file[0])

        lb.new(owner={"username": "test"}, name="labbook1", description="my first labbook")

        with pytest.raises(ValueError):
            lb.new(owner={"username": "test"}, name="labbook1", description="my first labbook")

    def test_checkout_id_property(self, mock_config_file):
        """Test trying to create a labbook with a name that already exists locally"""
        lb = LabBook(mock_config_file[0])

        lb.new(owner={"username": "test"}, name="labbook1", description="my first labbook")

        checkout_file = os.path.join(lb.root_dir, '.gigantum', '.checkout')
        assert os.path.exists(checkout_file) is False

        checkout_id = lb.checkout_id

        assert os.path.exists(checkout_file) is True

        parts = checkout_id.split("-")
        assert len(parts) == 5
        assert parts[0] == "test"
        assert parts[1] == "test"
        assert parts[2] == "labbook1"
        assert parts[3] == "master"
        assert len(parts[4]) == 10

        # Check repo is clean
        status = lb.git.status()
        for key in status:
            assert len(status[key]) == 0

        # Remove checkout file
        os.remove(checkout_file)

        # Repo should STILL be clean as it is not tracked
        status = lb.git.status()
        for key in status:
            assert len(status[key]) == 0

    def test_checkout_id_property_multiple_access(self, mock_config_file):
        """Test getting a checkout id multiple times"""
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="labbook1", description="my first labbook")

        checkout_file = os.path.join(lb.root_dir, '.gigantum', '.checkout')
        assert os.path.exists(checkout_file) is False
        checkout_id_1 = lb.checkout_id
        assert os.path.exists(checkout_file) is True

        assert checkout_id_1 == lb.checkout_id

        # Remove checkout id
        os.remove(checkout_file)
        lb._checkout_id = None

        # New ID should be created
        assert checkout_id_1 != lb.checkout_id

    def test_rename_labbook(self, mock_config_file):
        """Test renaming a LabBook"""
        lb = LabBook(mock_config_file[0])
        lb.new(username="test", name="labbook1", description="my first labbook", owner={"username": "test"})

        assert lb.root_dir == os.path.join(mock_config_file[1], "test", "test", "labbooks", "labbook1")
        assert type(lb) == LabBook

        # Rename
        original_dir = lb.root_dir
        lb.rename('renamed-labbook-1')

        # Validate copy
        assert lb.root_dir == os.path.join(mock_config_file[1], "test", "test", "labbooks", "renamed-labbook-1")
        assert os.path.exists(lb.root_dir) is True
        assert os.path.isdir(lb.root_dir) is True

        # Validate directory structure
        assert os.path.isdir(os.path.join(lb.root_dir, "code")) is True
        assert os.path.isdir(os.path.join(lb.root_dir, "input")) is True
        assert os.path.isdir(os.path.join(lb.root_dir, "output")) is True
        assert os.path.isdir(os.path.join(lb.root_dir, ".gigantum")) is True
        assert os.path.isdir(os.path.join(lb.root_dir, ".gigantum", "env")) is True
        assert os.path.isdir(os.path.join(lb.root_dir, ".gigantum", "notes")) is True
        assert os.path.isdir(os.path.join(lb.root_dir, ".gigantum", "notes", "log")) is True
        assert os.path.isdir(os.path.join(lb.root_dir, ".gigantum", "notes", "index")) is True

        # Validate labbook data file
        with open(os.path.join(lb.root_dir, ".gigantum", "labbook.yaml"), "rt") as data_file:
            data = yaml.load(data_file)

        assert data["labbook"]["name"] == "renamed-labbook-1"
        assert data["labbook"]["description"] == "my first labbook"
        assert "id" in data["labbook"]
        assert data["owner"]["username"] == "test"

        # Validate old dir is gone
        assert os.path.exists(original_dir) is False
        assert os.path.isdir(original_dir) is False

    def test_rename_existing_labbook(self, mock_config_file):
        """Test renaming a LabBook to an existing labbook"""
        lb = LabBook(mock_config_file[0])
        lb.new(username="test", name="labbook1", description="my first labbook", owner={"username": "test"})
        lb.new(username="test", name="labbook2", description="my first labbook", owner={"username": "test"})

        # Fail to Rename
        assert lb.name == 'labbook2'
        with pytest.raises(ValueError):
            lb.rename('labbook1')

    def test_list_labbooks(self, mock_config_file):
        """Test listing labbooks for all users"""
        lb1, lb2, lb3, lb4 = LabBook(mock_config_file[0]), LabBook(mock_config_file[0]),\
                             LabBook(mock_config_file[0]), LabBook(mock_config_file[0])

        labbook_dir1 = lb1.new(owner={"username": "user1"}, name="labbook1", description="my first labbook")
        labbook_dir2 = lb2.new(owner={"username": "user1"}, name="labbook2", description="my second labbook")
        labbook_dir3 = lb3.new(owner={"username": "user2"}, name="labbook3", description="my other labbook")
        labbook_dir4 = lb4.new(owner={"username": "user2"}, username="user1", name="labbook4",
                              description="another users labbook")

        assert labbook_dir1 == os.path.join(mock_config_file[1], "user1", "user1", "labbooks", "labbook1")
        assert labbook_dir2 == os.path.join(mock_config_file[1], "user1", "user1", "labbooks", "labbook2")
        assert labbook_dir3 == os.path.join(mock_config_file[1], "user2", "user2", "labbooks", "labbook3")
        assert labbook_dir4 == os.path.join(mock_config_file[1], "user1", "user2", "labbooks", "labbook4")

        labbooks = lb1.list_local_labbooks()

        assert len(labbooks) == 2
        assert "user1" in labbooks
        assert "user2" in labbooks
        assert len(labbooks["user1"]) == 3
        assert len(labbooks["user2"]) == 1
        assert labbooks["user1"][0] == {"name": "labbook1", "owner": "user1"}
        assert labbooks["user1"][1] == {"name": "labbook2", "owner": "user1"}
        assert labbooks["user1"][2] == {"name": "labbook4", "owner": "user2"}
        assert labbooks["user2"][0] == {"name": "labbook3", "owner": "user2"}

    def test_list_labbooks_for_user(self, mock_config_file):
        """Test list only a single user's labbooks"""
        lb1, lb2, lb3 = LabBook(mock_config_file[0]), LabBook(mock_config_file[0]), LabBook(mock_config_file[0])

        labbook_dir1 = lb1.new(owner={"username": "user1"}, name="labbook1", description="my first labbook")
        labbook_dir2 = lb2.new(owner={"username": "user1"}, name="labbook2", description="my second labbook")
        labbook_dir3 = lb3.new(owner={"username": "user2"}, name="labbook3", description="my other labbook")

        assert labbook_dir1 == os.path.join(mock_config_file[1], "user1", "user1", "labbooks", "labbook1")
        assert labbook_dir2 == os.path.join(mock_config_file[1], "user1", "user1", "labbooks", "labbook2")
        assert labbook_dir3 == os.path.join(mock_config_file[1], "user2", "user2", "labbooks", "labbook3")

        labbooks = lb1.list_local_labbooks(username="user1")

        assert len(labbooks) == 1
        assert "user1" in labbooks
        assert len(labbooks["user1"]) == 2
        assert labbooks["user1"][0] == {"name": "labbook1", "owner": "user1"}
        assert labbooks["user1"][1] == {"name": "labbook2", "owner": "user1"}

    def test_load_from_directory(self, mock_config_file):
        """Test loading a labbook from a directory"""
        lb = LabBook(mock_config_file[0])

        labbook_dir = lb.new(username="test", name="labbook1", description="my first labbook",
                             owner={"username": "test"})

        assert labbook_dir == os.path.join(mock_config_file[1], "test", "test", "labbooks", "labbook1")
        assert type(lb) == LabBook

        # Validate directory structure
        assert os.path.isdir(os.path.join(labbook_dir, "code")) is True
        assert os.path.isdir(os.path.join(labbook_dir, "input")) is True
        assert os.path.isdir(os.path.join(labbook_dir, "output")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "env")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "notes")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "notes", "log")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "notes", "index")) is True

        # Validate labbook data file
        with open(os.path.join(labbook_dir, ".gigantum", "labbook.yaml"), "rt") as data_file:
            data = yaml.load(data_file)

        assert data["labbook"]["name"] == "labbook1"
        assert data["labbook"]["description"] == "my first labbook"
        assert "id" in data["labbook"]
        assert data["owner"]["username"] == "test"

        lb_loaded = LabBook(mock_config_file[0])
        lb_loaded.from_directory(labbook_dir)

        assert lb_loaded.root_dir == os.path.join(mock_config_file[1], "test", "test", "labbooks", "labbook1")
        assert type(lb) == LabBook

        # Validate labbook data file
        assert lb_loaded.root_dir == lb.root_dir
        assert lb_loaded.id == lb.id
        assert lb_loaded.name == lb.name
        assert lb_loaded.description == lb.description

    def test_load_from_name(self, mock_config_file):
        """Test loading a labbook from a directory"""
        lb = LabBook(mock_config_file[0])

        labbook_dir = lb.new(username="test", name="labbook1", description="my first labbook",
                             owner={"username": "test"})

        assert labbook_dir == os.path.join(mock_config_file[1], "test", "test", "labbooks", "labbook1")
        assert type(lb) == LabBook

        # Validate directory structure
        assert os.path.isdir(os.path.join(labbook_dir, "code")) is True
        assert os.path.isdir(os.path.join(labbook_dir, "input")) is True
        assert os.path.isdir(os.path.join(labbook_dir, "output")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "env")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "notes")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "notes", "log")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "notes", "index")) is True

        # Validate labbook data file
        with open(os.path.join(labbook_dir, ".gigantum", "labbook.yaml"), "rt") as data_file:
            data = yaml.load(data_file)

        assert data["labbook"]["name"] == "labbook1"
        assert data["labbook"]["description"] == "my first labbook"
        assert "id" in data["labbook"]
        assert data["owner"]["username"] == "test"

        lb_loaded = LabBook(mock_config_file[0])
        lb_loaded.from_name("test", "test", "labbook1")

        assert lb_loaded.root_dir == os.path.join(mock_config_file[1], "test", "test", "labbooks", "labbook1")
        assert type(lb) == LabBook

        # Validate labbook data file
        assert lb_loaded.root_dir == lb.root_dir
        assert lb_loaded.id == lb.id
        assert lb_loaded.name == lb.name
        assert lb_loaded.description == lb.description
        assert lb_loaded.key == 'test|test|labbook1'

    def test_change_properties(self, mock_config_file):
        """Test loading a labbook from a directory"""
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="labbook1", description="my first labbook")

        lb.name = "new-labbook-1"
        lb.description = "an updated description"

        # Reload and see changes
        lb_loaded = LabBook(mock_config_file[0])
        lb_loaded.from_name("test", "test", "new-labbook-1")

        assert lb_loaded.root_dir == os.path.join(mock_config_file[1], "test", "test", "labbooks", "new-labbook-1")
        assert type(lb) == LabBook

        # Validate labbook data file
        assert lb_loaded.id == lb.id
        assert lb_loaded.name == "new-labbook-1"
        assert lb_loaded.description == "an updated description"

    def test_validate_new_labbook_name(self, mock_config_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="name-validate-test", description="validate tests.")

        bad_labbook_names = [
            None, "", "-", "--", "--a", '_', "-a", "a-", "$#Q", "Catbook4me", "--MeowMe", "-meow-4-me-",
            "r--jacob-vogelstein", "Bad!", "----a----", "4---a--5---a", "cats-" * 200, "Catbook_",
            "4underscores_not_allowed", "my--labbook1",
            "-DNf84329DSJfdj3820jg"
        ]

        allowed_labbook_names = [
            "r-jacob-vogelstein", "chewy-dog", "chewy-dog-99", "9-sdfysc-2-42-aadsda-a43", 'a' * 99, '2-22-222-3333',
            '9' * 50
        ]

        for bad in bad_labbook_names:
            with pytest.raises(ValueError):
                lb.name = bad

        for good in allowed_labbook_names:
            lb.name = good

    def test_insert_file_success_1(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-1", description="validate tests.")
        new_file_data = lb.insert_file("code", sample_src_file, "")
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

        new_file_data = lb.insert_file("code", test_file, "", base_filename='testfile.txt')

        assert os.path.exists(os.path.join(lb.root_dir, 'code', 'testfile.txt'))
        assert new_file_data['key'] == 'testfile.txt'
        assert new_file_data['is_dir'] is False

    def test_insert_file_success_2(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-4", description="validate tests.")
        lb.makedir("output/testdir")
        new_file_data = lb.insert_file("output", sample_src_file, "testdir")
        base_name = os.path.basename(sample_src_file)
        assert os.path.exists(os.path.join(lb.root_dir, 'output', 'testdir', base_name))
        assert new_file_data['key'] == f'testdir/{base_name}'
        assert new_file_data['is_dir'] is False

    def test_insert_file_fail_1(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-fail", description="validate tests.")
        with pytest.raises(ValueError):
            lb.insert_file("code", sample_src_file, "/totally/invalid/dir")

    def test_remove_file_success(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-1", description="validate tests.")
        new_file_data = lb.insert_file("code", sample_src_file, "")
        base_name = os.path.basename(sample_src_file)

        assert os.path.exists(os.path.join(lb.root_dir, 'code', base_name))
        lb.delete_file('code', base_name)
        assert not os.path.exists(os.path.join(lb.root_dir, 'code', base_name))

    def test_remove_file_fail(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-1", description="validate tests.")
        lb.insert_file("code", sample_src_file, "")

        new_file_path = os.path.join('blah', 'invalid.txt')
        with pytest.raises(ValueError):
            lb.delete_file('code', new_file_path)

    def test_remove_dir(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-remove-dir-1", description="validate tests.")
        lb.makedir("output/testdir")
        new_file_path = lb.insert_file("output", sample_src_file, "testdir")
        base_name = os.path.basename(sample_src_file)

        assert os.path.exists(os.path.join(lb.root_dir, 'output', 'testdir', base_name))

        with pytest.raises(ValueError):
            lb.delete_file("output", "testdir", directory=False)

        # Delete the directory
        lb.delete_file("output", "testdir", directory=True)
        assert not os.path.exists(os.path.join(lb.root_dir, 'output', 'testdir', base_name))
        assert not os.path.exists(os.path.join(lb.root_dir, 'output', 'testdir'))

    def test_move_file_as_rename_in_same_dir(self, mock_config_file, sample_src_file):
        # Create lb
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-1", description="validate tests.")

        # insert file
        new_file_data = lb.insert_file("code", sample_src_file, '')
        base_name = os.path.basename(sample_src_file)
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
        new_file_data = lb.insert_file("code", sample_src_file, "")
        base_name = os.path.basename(sample_src_file)
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
        new_file_data = lb.insert_file("code", sample_src_file, "")
        base_name = os.path.basename(sample_src_file)
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

        lb.makedir("code/test", create_note=True)

        assert os.path.exists(os.path.join(lb.root_dir, 'code', 'test')) is True
        assert lb.is_repo_clean is True

        lb.makedir("code/test2", create_note=False)
        assert os.path.exists(os.path.join(lb.root_dir, 'code', 'test2')) is True
        assert lb.is_repo_clean is False

    def test_walkdir(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-1", description="validate tests.")
        dirs = ["code/cat_dir", "code/dog_dir", "code/mouse_dir/", "code/mouse_dir/new_dir", "code/.hidden_dir"]
        for d in dirs:
            lb.makedir(d)
        lb.insert_file('code', sample_src_file, '.hidden_dir/')
        lb.insert_file('code', sample_src_file, '')
        lb.insert_file('code', sample_src_file, 'dog_dir')
        lb.insert_file('code', sample_src_file, 'mouse_dir/new_dir/')

        dir_walks_hidden = lb.walkdir('code', show_hidden=True)
        assert any([os.path.basename(sample_src_file) in d['key'] for d in dir_walks_hidden])
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
        assert dir_walks[2]['key'] == 'mouse_dir/'
        assert dir_walks[2]['is_dir'] is True
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

    def test_make_path_relative(self):
        vectors = [
            # In format of input: expected output
            (None, None),
            ('', ''),
            ('/', ''),
            ('//', ''),
            ('/////cats', 'cats'),
            ('//cats///', 'cats///'),
            ('cats', 'cats'),
            ('/cats/', 'cats/'),
            ('complex/.path/.like/this', 'complex/.path/.like/this'),
            ('//complex/.path/.like/this', 'complex/.path/.like/this')
        ]
        for sample_input, expected_output in vectors:
            assert LabBook._make_path_relative(sample_input) == expected_output

    def test_labbook_key(self, mock_config_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-lb-key", description="validate tests.")
        assert lb.key == 'test|test|test-lb-key'

        lb1key = lb.key
        lb2 = LabBook(mock_config_file[0])
        lb2.from_key(lb1key)

    def test_walkdir_with_favorites(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-1", description="validate tests.")
        dirs = ["code/cat_dir", "code/dog_dir"]
        for d in dirs:
            lb.makedir(d)
        lb.insert_file('code', sample_src_file, '')
        lb.insert_file('code', sample_src_file, 'dog_dir')
        lb.insert_file('code', sample_src_file, 'cat_dir')

        sample_filename = os.path.basename(sample_src_file)

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


