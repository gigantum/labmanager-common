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

from lmcommon.labbook import LabBook, LabBookManager


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
    def test_load_labbook_from_directory(self, mock_config_file):
        """Test creating an empty labbook"""
        lbm = LabBookManager(mock_config_file[0])

        labbook_dir = lbm.create_labbook(username="test", name="labbook1", description="my first labbook")

        assert labbook_dir == os.path.join(mock_config_file[1], "test", "labbook1")

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
        lbm = LabBookManager(mock_config_file[0])

        lbm.create_labbook(username="test", name="labbook1", description="my first labbook")

        with pytest.raises(ValueError):
            lbm.create_labbook(username="test", name="labbook1", description="my first labbook")

    def test_invalid_name(self, mock_config_file):
        """Test trying to create a labbook with an invalid name"""
        lbm = LabBookManager(mock_config_file[0])

        lbm.create_labbook(username="test", name="DNf84329Ddf-d-d-d-d-dasdsw-SJfdj3820jg",
                           description="my first labbook")

        with pytest.raises(ValueError):
            lbm.create_labbook(username="test", name="my labbook1", description="my first labbook")

        with pytest.raises(ValueError):
            lbm.create_labbook(username="test", name="my--labbook1", description="my first labbook")

        with pytest.raises(ValueError):
            lbm.create_labbook(username="test", name="DNf84329DSJfdj3820jg-", description="my first labbook")

        with pytest.raises(ValueError):
            lbm.create_labbook(username="test", name="-DNf84329DSJfdj3820jg", description="my first labbook")

        long_name = "".join(["a" for x in range(0, 101)])
        with pytest.raises(ValueError):
            lbm.create_labbook(username="test", name=long_name, description="my first labbook")