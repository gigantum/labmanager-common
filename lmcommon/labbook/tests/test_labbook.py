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

from lmcommon.labbook import LabBook


@pytest.fixture()
def mock_config_file():
    """A pytest fixture that creates a temporary directory and a config file to match. Deletes directory after test"""
    # Create a temporary working directory
    temp_dir = os.path.join(tempfile.tempdir, uuid.uuid4().hex)
    os.makedirs(temp_dir)
    
    with tempfile.NamedTemporaryFile(mode="wt") as fp:
        # Write a temporary config file
        fp.write("""core:
  team_mode: false 
git:
  backend: 'filesystem'
  working_directory: '{}'""".format(temp_dir))
        fp.seek(0)

        yield fp.name, temp_dir  # provide the fixture value

    # Remove the temp_dir
    shutil.rmtree(temp_dir)


class TestLabBook(object):
    def test_create_labbook(self, mock_config_file):
        """Test creating an empty labbook"""
        lb = LabBook(mock_config_file[0])

        labbook_dir = lb.new(username="test", name="labbook1", description="my first labbook")

        assert labbook_dir == os.path.join(mock_config_file[1], "test", "labbook1")
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

        lb.new(username="test", name="labbook1", description="my first labbook")

        with pytest.raises(ValueError):
            lb.new(username="test", name="labbook1", description="my first labbook")
            
    def test_invalid_name(self, mock_config_file):
        """Test trying to create a labbook with an invalid name"""
        lb = LabBook(mock_config_file[0])

        lb.new(username="test", name="DNf84329Ddf-d-d-d-d-dasdsw-SJfdj3820jg", description="my first labbook")

        with pytest.raises(ValueError):
            lb.new(username="test", name="my labbook1", description="my first labbook")

        with pytest.raises(ValueError):
            lb.new(username="test", name="my--labbook1", description="my first labbook")
        
        with pytest.raises(ValueError):
            lb.new(username="test", name="DNf84329DSJfdj3820jg-", description="my first labbook")
        
        with pytest.raises(ValueError):
            lb.new(username="test", name="-DNf84329DSJfdj3820jg", description="my first labbook")

        long_name = "".join(["a" for x in range(0, 101)])
        with pytest.raises(ValueError):
            lb.new(username="test", name=long_name, description="my first labbook")

    def test_list_labbooks(self, mock_config_file):
        """Test listing labbooks for all users"""
        lb = LabBook(mock_config_file[0])

        labbook_dir1 = lb.new(username="user1", name="labbook1", description="my first labbook")
        labbook_dir2 = lb.new(username="user1", name="labbook2", description="my second labbook")
        labbook_dir3 = lb.new(username="user2", name="labbook3", description="my other labbook")

        assert labbook_dir1 == os.path.join(mock_config_file[1], "user1", "labbook1")
        assert labbook_dir2 == os.path.join(mock_config_file[1], "user1", "labbook2")
        assert labbook_dir3 == os.path.join(mock_config_file[1], "user2", "labbook3")

        labbooks = lb.list_local_labbooks()

        assert len(labbooks) == 2
        assert "user1" in labbooks
        assert "user2" in labbooks
        assert len(labbooks["user1"]) == 2
        assert len(labbooks["user2"]) == 1
        assert "labbook1" in labbooks["user1"]
        assert "labbook2" in labbooks["user1"]
        assert "labbook3" in labbooks["user2"]

    def test_list_labbooks_for_user(self, mock_config_file):
        """Test list only a single user's labbooks"""
        lb = LabBook(mock_config_file[0])

        labbook_dir1 = lb.new(username="user1", name="labbook1", description="my first labbook")
        labbook_dir2 = lb.new(username="user1", name="labbook2", description="my second labbook")
        labbook_dir3 = lb.new(username="user2", name="labbook3", description="my other labbook")

        assert labbook_dir1 == os.path.join(mock_config_file[1], "user1", "labbook1")
        assert labbook_dir2 == os.path.join(mock_config_file[1], "user1", "labbook2")
        assert labbook_dir3 == os.path.join(mock_config_file[1], "user2", "labbook3")

        labbooks = lb.list_local_labbooks(username="user1")

        assert len(labbooks) == 1
        assert "user1" in labbooks
        assert len(labbooks["user1"]) == 2
        assert "labbook1" in labbooks["user1"]
        assert "labbook2" in labbooks["user1"]

    def test_load_from_directory(self, mock_config_file):
        """Test loading a labbook from a directory"""
        lb = LabBook(mock_config_file[0])

        labbook_dir = lb.new(username="test", name="labbook1", description="my first labbook")

        assert labbook_dir == os.path.join(mock_config_file[1], "test", "labbook1")
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

        assert lb_loaded.root_dir == os.path.join(mock_config_file[1], "test", "labbook1")
        assert type(lb) == LabBook

        # Validate labbook data file
        assert lb_loaded.root_dir == lb.root_dir
        assert lb_loaded.id == lb.id
        assert lb_loaded.name == lb.name
        assert lb_loaded.description == lb.description

    def test_load_from_name(self, mock_config_file):
        """Test loading a labbook from a directory"""
        lb = LabBook(mock_config_file[0])

        labbook_dir = lb.new(username="test", name="labbook1", description="my first labbook")

        assert labbook_dir == os.path.join(mock_config_file[1], "test", "labbook1")
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
        lb_loaded.from_name("test", "labbook1")

        assert lb_loaded.root_dir == os.path.join(mock_config_file[1], "test", "labbook1")
        assert type(lb) == LabBook

        # Validate labbook data file
        assert lb_loaded.root_dir == lb.root_dir
        assert lb_loaded.id == lb.id
        assert lb_loaded.name == lb.name
        assert lb_loaded.description == lb.description

    def test_change_properties(self, mock_config_file):
        """Test loading a labbook from a directory"""
        lb = LabBook(mock_config_file[0])
        lb.new(username="test", name="labbook1", description="my first labbook")

        lb.name = "new-labbook-1"
        lb.description = "an updated description"

        # Reload and see changes
        lb_loaded = LabBook(mock_config_file[0])
        lb_loaded.from_name("test", "new-labbook-1")

        assert lb_loaded.root_dir == os.path.join(mock_config_file[1], "test", "new-labbook-1")
        assert type(lb) == LabBook

        # Validate labbook data file
        assert lb_loaded.id == lb.id
        assert lb_loaded.name == "new-labbook-1"
        assert lb_loaded.description == "an updated description"

    def test_change_invalid_properties(self, mock_config_file):
        """Test loading a labbook from a directory"""
        lb = LabBook(mock_config_file[0])

        lb.new(username="test", name="DNf84329Ddf-d-d-d-d-dasdsw-SJfdj3820jg", description="my first labbook")

        with pytest.raises(ValueError):
            lb.name = "my labbook1"

        with pytest.raises(ValueError):
            lb.name = "my--labbook1"

        with pytest.raises(ValueError):
            lb.name = "DNf84329DSJfdj3820jg-"

        with pytest.raises(ValueError):
            lb.name = "-DNf84329DSJfdj3820jg"

        long_name = "".join(["a" for x in range(0, 101)])
        with pytest.raises(ValueError):
            lb.name = long_name
