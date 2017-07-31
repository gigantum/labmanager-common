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

from lmcommon.dataset import Dataset


@pytest.fixture()
def mock_config_file():
    """A pytest fixture that creates a temporary directory and a config file to match. Deletes directory after test"""
    # Create a temporary dataset directory
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


class TestDataset():
    def test_create_dataset(self, mock_config_file):
        """Test creating an empty dataset"""
        ds = Dataset(mock_config_file[0])

        dataset_dir = ds.new(username="test", name="dataset1", description="my first dataset",
                             owner={"username": "test"})

        assert dataset_dir == os.path.join(mock_config_file[1], "test", "dataset1")
        assert type(ds) == Dataset

        # Validate directory structure
        assert os.path.isdir(os.path.join(dataset_dir, ".gigantum")) is True
        assert os.path.isdir(os.path.join(dataset_dir, ".gigantum", "protocols")) is True

        # Validate dataset data file
        with open(os.path.join(dataset_dir, ".gigantum", "dataset.yaml"), "rt") as data_file:
            data = yaml.load(data_file)

        assert data["dataset"]["name"] == "dataset1"
        assert data["dataset"]["description"] == "my first dataset"
        assert "id" in data["dataset"]
        assert data["owner"]["username"] == "test"

        # Validate the Jenkins file
        assert os.path.isfile(os.path.join(dataset_dir, ".gigantum", "protocols", "Jenkinsfile")) is True


    def test_create_dataset_that_exists(self, mock_config_file):
        """Test trying to create a dataset with a name that already exists locally"""
        ds = Dataset(mock_config_file[0])

        ds.new(username="test", name="dataset1", description="my first dataset")

        with pytest.raises(ValueError):
            ds.new(username="test", name="dataset1", description="my first dataset")
            
    def test_invalid_name(self, mock_config_file):
        """Test trying to create a dataset with an invalid name"""
        ds = Dataset(mock_config_file[0])

        ds.new(username="test", name="DNf84329Ddf-d-d-d-d-dasdsw-SJfdj3820jg", description="my first dataset")

        with pytest.raises(ValueError):
            ds.new(username="test", name="my dataset1", description="my first dataset")

        with pytest.raises(ValueError):
            ds.new(username="test", name="my--dataset1", description="my first dataset")
        
        with pytest.raises(ValueError):
            ds.new(username="test", name="DNf84329DSJfdj3820jg-", description="my first dataset")
        
        with pytest.raises(ValueError):
            ds.new(username="test", name="-DNf84329DSJfdj3820jg", description="my first dataset")

        long_name = "".join(["a" for x in range(0, 101)])
        with pytest.raises(ValueError):
            ds.new(username="test", name=long_name, description="my first dataset")

    def test_list_datasets(self, mock_config_file):
        """Test listing datasets for all users"""
        ds = Dataset(mock_config_file[0])

        dataset_dir1 = ds.new(username="user1", name="dataset1", description="my first dataset")
        dataset_dir2 = ds.new(username="user1", name="dataset2", description="my second dataset")
        dataset_dir3 = ds.new(username="user2", name="dataset3", description="my other dataset")

        assert dataset_dir1 == os.path.join(mock_config_file[1], "user1", "dataset1")
        assert dataset_dir2 == os.path.join(mock_config_file[1], "user1", "dataset2")
        assert dataset_dir3 == os.path.join(mock_config_file[1], "user2", "dataset3")

        datasets = ds.list_local_datasets()

        assert len(datasets) == 2
        assert "user1" in datasets
        assert "user2" in datasets
        assert len(datasets["user1"]) == 2
        assert len(datasets["user2"]) == 1
        assert "dataset1" in datasets["user1"]
        assert "dataset2" in datasets["user1"]
        assert "dataset3" in datasets["user2"]

    def test_list_datasets_for_user(self, mock_config_file):
        """Test list only a single user's datasets"""
        ds = Dataset(mock_config_file[0])

        dataset_dir1 = ds.new(username="user1", name="dataset1", description="my first dataset")
        dataset_dir2 = ds.new(username="user1", name="dataset2", description="my second dataset")
        dataset_dir3 = ds.new(username="user2", name="dataset3", description="my other dataset")

        assert dataset_dir1 == os.path.join(mock_config_file[1], "user1", "dataset1")
        assert dataset_dir2 == os.path.join(mock_config_file[1], "user1", "dataset2")
        assert dataset_dir3 == os.path.join(mock_config_file[1], "user2", "dataset3")

        datasets = ds.list_local_datasets(username="user1")

        assert len(datasets) == 1
        assert "user1" in datasets
        assert len(datasets["user1"]) == 2
        assert "dataset1" in datasets["user1"]
        assert "dataset2" in datasets["user1"]

    def test_load_from_directory(self, mock_config_file):
        """Test loading a dataset from a directory"""
        ds = Dataset(mock_config_file[0])

        dataset_dir = ds.new(username="test", name="dataset1", description="my first dataset",
                             owner={"username": "test"})

        assert dataset_dir == os.path.join(mock_config_file[1], "test", "dataset1")
        assert type(ds) == Dataset

        # Validate directory structure
        assert os.path.isdir(os.path.join(dataset_dir, ".gigantum")) is True
        assert os.path.isdir(os.path.join(dataset_dir, ".gigantum", "protocols")) is True

        # Validate dataset data file
        with open(os.path.join(dataset_dir, ".gigantum", "dataset.yaml"), "rt") as data_file:
            data = yaml.load(data_file)

        assert data["dataset"]["name"] == "dataset1"
        assert data["dataset"]["description"] == "my first dataset"
        assert "id" in data["dataset"]
        assert data["owner"]["username"] == "test"

        # Validate the Jenkins file
        assert os.path.isfile(os.path.join(dataset_dir, ".gigantum", "protocols", "Jenkinsfile")) is True

        ds_loaded = Dataset(mock_config_file[0])
        ds_loaded.from_directory(dataset_dir)

        assert ds_loaded.root_dir == os.path.join(mock_config_file[1], "test", "dataset1")
        assert type(ds) == Dataset

        # Validate dataset data file
        assert ds_loaded.root_dir == ds.root_dir
        assert ds_loaded.id == ds.id
        assert ds_loaded.name == ds.name
        assert ds_loaded.description == ds.description

    def test_load_from_name(self, mock_config_file):
        """Test loading a dataset from a directory"""
        ds = Dataset(mock_config_file[0])

        dataset_dir = ds.new(username="test", name="dataset1", description="my first dataset",
                             owner={"username": "test"})

        assert dataset_dir == os.path.join(mock_config_file[1], "test", "dataset1")
        assert type(ds) == Dataset

        # Validate directory structure
        assert os.path.isdir(os.path.join(dataset_dir, ".gigantum")) is True
        assert os.path.isdir(os.path.join(dataset_dir, ".gigantum", "protocols")) is True

        # Validate dataset data file
        with open(os.path.join(dataset_dir, ".gigantum", "dataset.yaml"), "rt") as data_file:
            data = yaml.load(data_file)

        assert data["dataset"]["name"] == "dataset1"
        assert data["dataset"]["description"] == "my first dataset"
        assert "id" in data["dataset"]
        assert data["owner"]["username"] == "test"

        # Validate the Jenkins file
        assert os.path.isfile(os.path.join(dataset_dir, ".gigantum", "protocols", "Jenkinsfile")) is True

        ds_loaded = Dataset(mock_config_file[0])
        ds_loaded.from_name("test", "dataset1")

        assert ds_loaded.root_dir == os.path.join(mock_config_file[1], "test", "dataset1")
        assert type(ds) == Dataset

        # Validate dataset data file
        assert ds_loaded.root_dir == ds.root_dir
        assert ds_loaded.id == ds.id
        assert ds_loaded.name == ds.name
        assert ds_loaded.description == ds.description

    def test_change_properties(self, mock_config_file):
        """Test loading a dataset from a directory"""
        ds = Dataset(mock_config_file[0])
        ds.new(username="test", name="dataset1", description="my first dataset")

        ds.name = "new-dataset-1"
        ds.description = "an updated description"

        # Reload and see changes
        ds_loaded = Dataset(mock_config_file[0])
        ds_loaded.from_name("test", "new-dataset-1")

        assert ds_loaded.root_dir == os.path.join(mock_config_file[1], "test", "new-dataset-1")
        assert type(ds) == Dataset

        # Validate dataset data file
        assert ds_loaded.id == ds.id
        assert ds_loaded.name == "new-dataset-1"
        assert ds_loaded.description == "an updated description"

    def test_change_invalid_properties(self, mock_config_file):
        """Test loading a dataset from a directory"""
        ds = Dataset(mock_config_file[0])

        ds.new(username="test", name="DNf84329Ddf-d-d-d-d-dasdsw-SJfdj3820jg", description="my first dataset")

        with pytest.raises(ValueError):
            ds.name = "my dataset1"

        with pytest.raises(ValueError):
            ds.name = "my--dataset1"

        with pytest.raises(ValueError):
            ds.name = "DNf84329DSJfdj3820jg-"

        with pytest.raises(ValueError):
            ds.name = "-DNf84329DSJfdj3820jg"

        long_name = "".join(["a" for x in range(0, 101)])
        with pytest.raises(ValueError):
            ds.name = long_name
