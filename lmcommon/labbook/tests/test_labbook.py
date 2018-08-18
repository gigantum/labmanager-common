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
import getpass
import os
import yaml
import time

from lmcommon.files import FileOperations
from lmcommon.labbook import LabBook, LabbookException
from lmcommon.gitlib.git import GitAuthor
from lmcommon.fixtures import mock_config_file, mock_labbook, remote_labbook_repo, sample_src_file


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
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "activity")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "activity", "log")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "activity", "index")) is True
        assert os.path.isfile(os.path.join(labbook_dir, ".gigantum", "buildinfo")) is True

        # Validate labbook data file
        with open(os.path.join(labbook_dir, ".gigantum", "labbook.yaml"), "rt") as data_file:
            data = yaml.load(data_file)

        assert data["labbook"]["name"] == "labbook1"
        assert data["labbook"]["description"] == "my first labbook"
        assert "id" in data["labbook"]
        assert data["owner"]["username"] == "test"

        if getpass.getuser() == 'circleci':
            assert lb.build_details is None
        else:
            assert lb.build_details is not None
        assert lb.creation_date is not None

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
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "activity")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "activity", "log")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "activity", "index")) is True

        # Validate labbook data file
        with open(os.path.join(labbook_dir, ".gigantum", "labbook.yaml"), "rt") as data_file:
            data = yaml.load(data_file)

        assert data["labbook"]["name"] == "labbook1"
        assert data["labbook"]["description"] == "my first labbook"
        assert "id" in data["labbook"]
        assert data["owner"]["username"] == "test"

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
        assert len(parts) == 6
        assert parts[0] == "test"
        assert parts[1] == "test"
        assert parts[2] == "labbook1"
        assert parts[3] == "gm.workspace"
        assert len(parts[5]) == 10

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

    def test_list_labbooks_az(self, mock_config_file):
        """Test list az labbooks"""
        lb1, lb2, lb3, lb4 = LabBook(mock_config_file[0]), LabBook(mock_config_file[0]),\
                             LabBook(mock_config_file[0]), LabBook(mock_config_file[0])

        labbook_dir1 = lb1.new(username="user1", owner={"username": "user1"},
                               name="labbook0", description="my first labbook")
        labbook_dir2 = lb2.new(username="user1", owner={"username": "user1"},
                               name="labbook12", description="my second labbook")
        labbook_dir3 = lb3.new(username="user1", owner={"username": "user2"},
                               name="labbook3", description="my other labbook")
        labbook_dir4 = lb4.new(username="user2", owner={"username": "user1"},
                               name="labbook4", description="my other labbook")

        labbooks = lb1.list_local_labbooks(username="user1")

        assert len(labbooks) == 3
        assert labbooks[0]['name'] == 'labbook0'
        assert labbooks[1]['name'] == 'labbook3'
        assert labbooks[2]['name'] == 'labbook12'

    def test_list_labbooks_az_reversed(self, mock_config_file):
        """Test list az labbooks, reversed"""
        lb1, lb2, lb3, lb4 = LabBook(mock_config_file[0]), LabBook(mock_config_file[0]),\
                             LabBook(mock_config_file[0]), LabBook(mock_config_file[0])

        labbook_dir1 = lb1.new(username="user1", owner={"username": "user1"},
                               name="labbook1", description="my first labbook")
        labbook_dir2 = lb2.new(username="user1", owner={"username": "user1"},
                               name="labbook2", description="my second labbook")
        labbook_dir3 = lb3.new(username="user1", owner={"username": "user2"},
                               name="labbook3", description="my other labbook")

        labbook_dir4 = lb4.new(username="user2", owner={"username": "user1"},
                               name="labbook4", description="my other labbook")

        assert labbook_dir1 == os.path.join(mock_config_file[1], "user1", "user1", "labbooks", "labbook1")
        assert labbook_dir2 == os.path.join(mock_config_file[1], "user1", "user1", "labbooks", "labbook2")
        assert labbook_dir3 == os.path.join(mock_config_file[1], "user1", "user2", "labbooks", "labbook3")
        assert labbook_dir4 == os.path.join(mock_config_file[1], "user2", "user1", "labbooks", "labbook4")

        with pytest.raises(ValueError):
            lb1.list_local_labbooks(username="user1", sort_mode='asdf')

        labbooks = lb1.list_local_labbooks(username="user1", reverse=True, sort_mode='name')

        assert len(labbooks) == 3
        assert labbooks[0]['name'] == 'labbook3'
        assert labbooks[1]['name'] == 'labbook2'
        assert labbooks[2]['name'] == 'labbook1'

    def test_list_labbooks_create_date(self, mock_config_file):
        """Test list create dated sorted labbooks"""
        lb1, lb2, lb3 = LabBook(mock_config_file[0]), LabBook(mock_config_file[0]), LabBook(mock_config_file[0])

        lb1.new(username="user1", owner={"username": "user1"},
                name="labbook3", description="my first labbook")
        lb2.new(username="user1", owner={"username": "user1"},
                name="asdf", description="my second labbook")
        lb3.new(username="user1", owner={"username": "user2"},
                name="labbook1", description="my other labbook")

        labbooks = lb1.list_local_labbooks(username="user1", sort_mode="created_on")

        assert len(labbooks) == 3
        assert labbooks[0]['name'] == 'labbook3'
        assert labbooks[1]['name'] == 'asdf'
        assert labbooks[2]['name'] == 'labbook1'

    def test_list_labbooks_create_date_no_metadata(self, mock_config_file):
        """Test list create dated sorted labbooks"""
        lb1, lb2, lb3 = LabBook(mock_config_file[0]), LabBook(mock_config_file[0]), LabBook(mock_config_file[0])

        lb1.new(username="user1", owner={"username": "user1"},
                name="labbook3", description="my first labbook")
        time.sleep(1.1)
        lb2.new(username="user1", owner={"username": "user1"},
                name="asdf", description="my second labbook")
        time.sleep(1.1)
        lb3.new(username="user1", owner={"username": "user2"},
                name="labbook1", description="my other labbook")
        time.sleep(1.1)

        labbooks = lb1.list_local_labbooks(username="user1", sort_mode="created_on")

        assert len(labbooks) == 3
        assert labbooks[0]['name'] == 'labbook3'
        assert labbooks[1]['name'] == 'asdf'
        assert labbooks[2]['name'] == 'labbook1'

        os.remove(os.path.join(lb1.root_dir, '.gigantum', 'buildinfo'))
        os.remove(os.path.join(lb3.root_dir, '.gigantum', 'buildinfo'))

        labbooks = lb1.list_local_labbooks(username="user1", sort_mode="created_on")

        assert len(labbooks) == 3
        assert labbooks[0]['name'] == 'labbook3'
        assert labbooks[1]['name'] == 'asdf'
        assert labbooks[2]['name'] == 'labbook1'

        os.remove(os.path.join(lb2.root_dir, '.gigantum', 'labbook.yaml'))
        labbooks = lb1.list_local_labbooks(username="user1", sort_mode='modified_on')
        assert len(labbooks) == 2

    def test_list_labbooks_create_date_reversed(self, mock_config_file):
        """Test list create dated sorted labbooks reversed"""
        lb1, lb2, lb3, lb4 = LabBook(mock_config_file[0]), LabBook(mock_config_file[0]),\
                             LabBook(mock_config_file[0]), LabBook(mock_config_file[0])

        lb1.new(username="user1", owner={"username": "user1"},
                name="labbook3", description="my first labbook")
        lb2.new(username="user1", owner={"username": "user1"},
                name="asdf", description="my second labbook")
        lb3.new(username="user1", owner={"username": "user2"},
                name="labbook1", description="my other labbook")
        lb4.new(username="user1", owner={"username": "user1"},
                name="labbook4", description="my other labbook")

        labbooks = lb1.list_local_labbooks(username="user1", sort_mode="created_on", reverse=True)

        assert len(labbooks) == 4
        assert labbooks[0]['name'] == 'labbook4'
        assert labbooks[1]['name'] == 'labbook1'
        assert labbooks[2]['name'] == 'asdf'
        assert labbooks[3]['name'] == 'labbook3'

    def test_list_labbooks_modified_date(self, mock_config_file):
        """Test list modified dated sorted labbooks"""
        lb1, lb2, lb3, lb4 = LabBook(mock_config_file[0]), LabBook(mock_config_file[0]),\
                             LabBook(mock_config_file[0]), LabBook(mock_config_file[0])

        lb1.new(username="user1", owner={"username": "user1"},
                name="labbook3", description="my first labbook")
        time.sleep(1.2)
        lb2.new(username="user1", owner={"username": "user1"},
                name="asdf", description="my second labbook")
        time.sleep(1.2)
        lb3.new(username="user1", owner={"username": "user2"},
                name="labbook1", description="my other labbook")
        time.sleep(1.2)
        lb4.new(username="user1", owner={"username": "user1"},
                name="hhghg", description="my other labbook")
        
        labbooks = lb1.list_local_labbooks(username="user1", sort_mode="modified_on")

        assert len(labbooks) == 4
        assert labbooks[0]['name'] == 'labbook3'
        assert labbooks[1]['name'] == 'asdf'
        assert labbooks[2]['name'] == 'labbook1'
        assert labbooks[3]['name'] == 'hhghg'

        # modify a repo
        time.sleep(1.2)
        with open(os.path.join(lb2.root_dir, "code", "test.txt"), 'wt') as tf:
            tf.write("asdfasdf")

        lb2.git.add_all()
        lb2.git.commit("Changing the repo")

        labbooks = lb1.list_local_labbooks(username="user1", sort_mode="modified_on")

        assert len(labbooks) == 4
        assert labbooks[0]['name'] == 'labbook3'
        assert labbooks[1]['name'] == 'labbook1'
        assert labbooks[2]['name'] == 'hhghg'
        assert labbooks[3]['name'] == 'asdf'

    def test_list_labbooks_modified_date_reversed(self, mock_config_file):
        """Test list modified dated sorted labbooks"""
        lb1, lb2, lb3, lb4 = LabBook(mock_config_file[0]), LabBook(mock_config_file[0]),\
                             LabBook(mock_config_file[0]), LabBook(mock_config_file[0])

        lb1.new(username="user1", owner={"username": "user1"},
                name="labbook3", description="my first labbook")
        time.sleep(1.2)
        lb2.new(username="user1", owner={"username": "user1"},
                name="asdf", description="my second labbook")
        time.sleep(1.2)
        lb3.new(username="user1", owner={"username": "user2"},
                name="labbook1", description="my other labbook")
        time.sleep(1.2)
        lb4.new(username="user1", owner={"username": "user1"},
                name="hhghg", description="my other labbook")

        labbooks = lb1.list_local_labbooks(username="user1", sort_mode="modified_on", reverse=True)

        assert len(labbooks) == 4
        assert labbooks[0]['name'] == 'hhghg'
        assert labbooks[1]['name'] == 'labbook1'
        assert labbooks[2]['name'] == 'asdf'
        assert labbooks[3]['name'] == 'labbook3'

        # modify a repo
        time.sleep(1.2)
        with open(os.path.join(lb2.root_dir, "code", "test.txt"), 'wt') as tf:
            tf.write("asdfasdf")

        lb2.git.add_all()
        lb2.git.commit("Changing the repo")

        labbooks = lb1.list_local_labbooks(username="user1", sort_mode="modified_on", reverse=True)

        assert len(labbooks) == 4
        assert labbooks[0]['name'] == 'asdf'
        assert labbooks[1]['name'] == 'hhghg'
        assert labbooks[2]['name'] == 'labbook1'
        assert labbooks[3]['name'] == 'labbook3'

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
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "activity")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "activity", "log")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "activity", "index")) is True

        # Validate labbook data file
        with open(os.path.join(labbook_dir, ".gigantum", "labbook.yaml"), "rt") as data_file:
            data = yaml.load(data_file)

        assert data["labbook"]["name"] == "labbook1"
        assert data["labbook"]["description"] == "my first labbook"
        assert "id" in data["labbook"]
        assert data["owner"]["username"] == "test"

        lb_loaded = LabBook(mock_config_file[0])
        lb_loaded.from_directory(labbook_dir)
        assert lb.active_branch == 'gm.workspace-test'

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
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "activity")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "activity", "log")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "activity", "index")) is True

        # Validate labbook data file
        with open(os.path.join(labbook_dir, ".gigantum", "labbook.yaml"), "rt") as data_file:
            data = yaml.load(data_file)

        assert data["labbook"]["name"] == "labbook1"
        assert data["labbook"]["description"] == "my first labbook"
        assert "id" in data["labbook"]
        assert data["owner"]["username"] == "test"

        lb_loaded = LabBook(mock_config_file[0])
        lb_loaded.from_name("test", "test", "labbook1")
        assert lb_loaded.active_branch == 'gm.workspace-test'

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
        assert lb_loaded.active_branch == 'gm.workspace-test'

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
        assert lb.active_branch == 'gm.workspace-test'

    def test_sweep_uncommitted_changes(self, mock_config_file):
        """ Test sweep covers Added, Removed, and """
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-1", description="validate tests.")

        with open(os.path.join(lb.root_dir, 'input', 'sillyfile'), 'wb') as newf:
            newf.write(os.urandom(2 ** 24))

        assert 'input/sillyfile' in lb.git.status()['untracked']
        lb.sweep_uncommitted_changes()
        s = lb.git.status()
        assert all([len(s[key]) == 0 for key in s.keys()])

        with open(os.path.join(lb.root_dir, 'input', 'sillyfile'), 'wb') as newf:
            newf.write(os.urandom(2 ** 16))
        assert 'input/sillyfile' in [n[0] for n in lb.git.status()['unstaged']]
        lb.sweep_uncommitted_changes()
        s = lb.git.status()
        assert all([len(s[key]) == 0 for key in s.keys()])
        os.remove(os.path.join(lb.root_dir, 'input', 'sillyfile'))
        assert 'input/sillyfile' in [n[0] for n in lb.git.status()['unstaged']]

        lb.sweep_uncommitted_changes()
        s = lb.git.status()
        assert all([len(s[key]) == 0 for key in s.keys()])

        assert any(['1 new file(s)' in l['message'] for l in lb.git.log()])


    def test_walkdir_with_favorites(self, mock_config_file, sample_src_file):
        lb = LabBook(mock_config_file[0])
        lb.new(owner={"username": "test"}, name="test-insert-files-1", description="validate tests.")
        dirs = ["code/cat_dir", "code/dog_dir"]
        for d in dirs:
            FileOperations.makedir(lb, d)

        open('/tmp/dogfile', 'w').write('ddd')
        open('/tmp/catfile', 'w').write('ccc')
        FileOperations.insert_file(lb, 'code', sample_src_file)
        FileOperations.insert_file(lb, 'code', '/tmp/dogfile', 'dog_dir')
        FileOperations.insert_file(lb, 'code', '/tmp/catfile', 'cat_dir')

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
        lb.create_favorite("code", f"dog_dir/dogfile", description="Fav 2")
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

    def test_create_labbook_with_author(self, mock_config_file):
        """Test creating an empty labbook with the author set"""
        lb = LabBook(mock_config_file[0], author=GitAuthor(name="username", email="user1@test.com"))

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
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "activity")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "activity", "log")) is True
        assert os.path.isdir(os.path.join(labbook_dir, ".gigantum", "activity", "index")) is True

        # Validate labbook data file
        with open(os.path.join(labbook_dir, ".gigantum", "labbook.yaml"), "rt") as data_file:
            data = yaml.load(data_file)

        assert data["labbook"]["name"] == "labbook1"
        assert data["labbook"]["description"] == "my first labbook"
        assert "id" in data["labbook"]
        assert data["owner"]["username"] == "test"

        log_data = lb.git.log()
        assert log_data[0]['author']['name'] == "username"
        assert log_data[0]['author']['email'] == "user1@test.com"
        assert log_data[0]['committer']['name'] == "Gigantum AutoCommit"
        assert log_data[0]['committer']['email'] == "noreply@gigantum.io"

    def test_read_write_readme(self, mock_config_file):
        """Test creating a reading and writing a readme file to the labbook"""
        lb = LabBook(mock_config_file[0], author=GitAuthor(name="test", email="test@test.com"))

        labbook_dir = lb.new(username="test", name="labbook1", description="my first labbook",
                             owner={"username": "test"})

        assert lb.get_readme() is None
        assert os.path.exists(os.path.join(lb.root_dir, 'README.md')) is False

        lb.write_readme("## Summary\nThis is my readme")

        assert os.path.exists(os.path.join(lb.root_dir, 'README.md')) is True

        assert lb.get_readme() == "## Summary\nThis is my readme"

    def test_readme_size_limit(self, mock_config_file):
        """Test creating a reading and writing a readme file to the labbook"""
        lb = LabBook(mock_config_file[0], author=GitAuthor(name="test", email="test@test.com"))

        labbook_dir = lb.new(username="test", name="labbook1", description="my first labbook",
                             owner={"username": "test"})

        assert lb.get_readme() is None
        assert os.path.exists(os.path.join(lb.root_dir, 'README.md')) is False

        with pytest.raises(ValueError):
            lb.write_readme("A" * (6 * 1000000))

        assert lb.get_readme() is None
        assert os.path.exists(os.path.join(lb.root_dir, 'README.md')) is False

    def test_readme_wierd_strings(self, mock_config_file):
        """Test creating a reading and writing a readme file to the labbook with complex strings"""
        lb = LabBook(mock_config_file[0], author=GitAuthor(name="test", email="test@test.com"))

        labbook_dir = lb.new(username="test", name="labbook1", description="my first labbook",
                             owner={"username": "test"})

        assert lb.get_readme() is None
        assert os.path.exists(os.path.join(lb.root_dir, 'README.md')) is False

        rand_str = os.urandom(1000000)
        with pytest.raises(TypeError):
            lb.write_readme(rand_str)

        assert lb.get_readme() is None
        assert os.path.exists(os.path.join(lb.root_dir, 'README.md')) is False

        with pytest.raises(TypeError):
            lb.write_readme(None)

        assert lb.get_readme() is None
        assert os.path.exists(os.path.join(lb.root_dir, 'README.md')) is False

        lb.write_readme("")

        assert lb.get_readme() == ""
        assert os.path.exists(os.path.join(lb.root_dir, 'README.md')) is True
