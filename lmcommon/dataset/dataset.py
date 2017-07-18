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
import uuid
import os
import re
import glob
import yaml

from lmcommon.gitlib import get_git_interface
from lmcommon.configuration import Configuration

# TODO RB resolve dataset_ working_directory issue


GIT_IGNORE_DEFAULT = """.DS_Store"""


class Dataset:
    """Class representing a Gigantum Dataset"""

    def __init__(self, config_file=None):
        self.labmanager_config = Configuration(config_file)

        # Create gitlib instance
        self.git = get_git_interface(self.labmanager_config.config["git"])

        # Dataset Properties
        self._root_dir = None
        self._data = None

    # PROPERTIES
    @property
    def root_dir(self):
        return self._root_dir

    @property
    def data(self):
        return self._data

    @property
    def id(self):
        return self._data["dataset"]["id"]

    @property
    def name(self):
        return self._data["dataset"]["name"]

    @name.setter
    def name(self, value):
        self._data["dataset"]["name"] = value
        self._validate_dataset_data()

        # Update data file
        self._save_dataset_data()

        # Rename directory
        base_dir, _ = self._root_dir.rsplit(os.path.sep, 1)
        os.rename(self._root_dir, os.path.join(base_dir, value))
        
        # Update the root directory to the new directory name
        self._set_root_dir(os.path.join(base_dir, value))

    @property
    def description(self):
        return self._data["dataset"]["description"]

    @description.setter
    def description(self, value):
        self._data["dataset"]["description"] = self._santize_input(value)
        self._save_dataset_data()

    # TODO: Replace with a user class instance once proper user interface implemented
    @property
    def owner(self):
        return self._data["owner"]
    # PROPERTIES

    def _set_root_dir(self, new_root_dir):
        """Update the root directory and also reconfigure the git instance

        Returns:
            None
        """
        # Be sure to expand in case a user dir string is used
        self._root_dir = os.path.expanduser(new_root_dir)

        # Update the git dataset directory
        self.git.set_working_directory(self.root_dir)

    def _save_dataset_data(self):
        """Method to save changes to the LabBook

        Returns:
            None
        """
        with open(os.path.join(self.root_dir, ".gigantum", "dataset.yaml"), 'wt') as dsfile:
            dsfile.write(yaml.dump(self._data, default_flow_style=False))

    def _validate_dataset_data(self):
        """Method to validate the LabBook data file contents

        Returns:
            None
        """
        # Validate name characters
        if not re.match("^(?!-)(?!.*--)[A-Za-z0-9-]+(?<!-)$", self.name):
            raise ValueError("Invalid `name`. Only A-Z a-z 0-9 and hyphens allowed. No leading or trailing hyphens.")

        if len(self.name) > 100:
            raise ValueError("Invalid `name`. Max length is 100 characters")

    def _santize_input(self, value):
        """Simple method to santize a user provided value with characters that can be bad

        Args:
            value(str): Input string

        Returns:
            str: Output string
        """
        return''.join(c for c in value if c not in '<>?/;"`\'')

    def new(self, username=None, owner=None, name=None, description=None):
        """Method to create a new minimal LabBook instance on disk

        /[Dataset name]
            /.gigantum
                dataset.yaml
                /protocols
                    Jenkinsfile
            /.git

        Args:
            path(str): Relative path to the directory where the Dataset should be created from the dataset dir
            owner(dict): Owner information
            name(str): Name of the Dataset
            description(str): A short description of the Dataset

        Returns:
            str: Path to the Dataset contents
        """
        if not username:
            username = "default"

        if not owner:
            owner = {"username": "default"}

        # Build data file contents
        self._data = {"dataset": {"id": uuid.uuid4().hex,
                                  "name": name,
                                  "description": self._santize_input(description)},
                      "owner": owner
                      }

        # Validate data
        self._validate_dataset_data()

        # Verify or Create user subdirectory
        # Make sure you expand a user dir string
        starting_dir = os.path.expanduser(self.labmanager_config.config["git"]["working_directory"])
        user_dir = os.path.join(starting_dir, username)
        if not os.path.isdir(user_dir):
            os.makedirs(user_dir)

        # Verify name not already in use
        if os.path.isdir(os.path.join(user_dir, name)):
            # Exists already. Raise an exception
            raise ValueError("Dataset with name `{}` already exists locally. Choose a new Dataset name".format(name))

        # Create Dataset subdirectory
        new_root_dir = os.path.join(user_dir, name)
        os.makedirs(new_root_dir)
        self._set_root_dir(new_root_dir)

        # Init repository
        self.git.initialize()

        # Create Directory Structure
        os.makedirs(os.path.join(self.root_dir, ".gigantum"))
        os.makedirs(os.path.join(self.root_dir, ".gigantum", "protocols"))

        # Create dataset.yaml file
        self._save_dataset_data()

        # Create .gitignore default file
        with open(os.path.join(self.root_dir, ".gitignore"), 'wt') as gi_file:
            gi_file.write(GIT_IGNORE_DEFAULT)

        # Create blank Jenkinsfile
        with open(os.path.join(self.root_dir, ".gigantum", "protocols", "Jenkinsfile"), 'wt') as dockerfile:
            dockerfile.write("[}")


        # Commit
        # TODO: Once users are properly added, create a GitAuthor instance before commit
        self.git.add(os.path.join(self.root_dir, ".gigantum", "dataset.yaml"))
        self.git.add(os.path.join(self.root_dir, ".gigantum", "protocols", "Jenkinsfile"))
        self.git.add(os.path.join(self.root_dir, ".gitignore"))
        self.git.commit("Creating new empty Dataset: {}".format(name))

        return self.root_dir

    def from_directory(self, root_dir):
        """Method to populate a Dataset instance from a directory

        Args:
            root_dir(str): The absolute path to the directory containing the LabBook

        Returns:
            Dataset
        """
        # Update root dir
        self._set_root_dir(root_dir)

        # Load Dataset data file
        with open(os.path.join(self.root_dir, ".gigantum", "dataset.yaml"), "rt") as data_file:
            self._data = yaml.load(data_file)

    def from_name(self, username, dataset_name):
        """Method to populate a Dataset instance based on the user and name of the dataset

        Args:
            username(str): The username of the owner of the Dataset
            dataset_name(str): the name of the Dataset

        Returns:
            Dataset
        """
        dataset_path = os.path.expanduser(os.path.join(self.labmanager_config.config["git"]["working_directory"],
                                                       username,
                                                       dataset_name))

        # Make sure directory exists
        if not os.path.isdir(dataset_path):
            raise ValueError("Dataset `{}` not found locally.".format(dataset_name))

        # Update root dir
        self._set_root_dir(dataset_path)

        # Load Dataset data file
        with open(os.path.join(self.root_dir, ".gigantum", "dataset.yaml"), "rt") as data_file:
            self._data = yaml.load(data_file)

    def list_local_datasets(self, username=None):
        """Method to list available Datasets

        Args:
            username(str): Username to filter the query on

        Returns:
            (dict(list)): A dictionary of lists of Dataset Names, one entry per user
        """
        # Make sure you expand a user string
        dataset_dir = os.path.expanduser(self.labmanager_config.config["git"]["working_directory"])

        if not username:
            # Return all available datasets
            files_collected = glob.glob(os.path.join(dataset_dir,
                                                     "*",
                                                     "*"))
        else:
            # Return only datasets for the provided user
            files_collected = glob.glob(os.path.join(dataset_dir,
                                                     username,
                                                     "*"))
        # Generate dictionary to return
        result = {}
        for dir_path in files_collected:
            if os.path.isdir(dir_path):
                _, user, dataset = dir_path.rsplit(os.path.sep, 2)
                if user not in result:
                    result[user] = []

                result[user].append(dataset)

        return result

    def log(self, username=None, max_count=10):
        """Method to list commit history of a Dataset

        Args:
            username(str): Username to filter the query on

        Returns:
            dict
        """
        # TODO: Add additional optional args to the git.log call to support futher filtering
        return self.git.log(max_count=max_count, author=username)

    def log_entry(self, commit):
        """Method to get a single log entry by commit

        Args:
            commit(str): commit hash of the entry

        Returns:
            dict
        """
        return self.git.log_entry(commit)

    def commit(self, message, author=None):
        # TODO: Revisit and possibly remove explict commit interface towards unified notes abstraction
        return self.git.commit(message, author=author)


