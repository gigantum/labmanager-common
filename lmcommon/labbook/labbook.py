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


class LabBook(object):
    """Class representing a single LabBook"""

    def __init__(self, config_file=None):
        self.labmanager_config = Configuration(config_file)

        # LabBook Properties
        self._root_dir = None
        self._data = None

        # LabBook Environment
        self._env = None

    # PROPERTIES
    @property
    def root_dir(self):
        return self._root_dir

    @property
    def data(self):
        return self._data

    @property
    def id(self):
        return self._data["labbook"]["id"]

    @property
    def name(self):
        return self._data["labbook"]["name"]

    @name.setter
    def name(self, value):
        self._data["labbook"]["name"] = value
        self._validate_labbook_data()

        # Update data file
        self._save_labbook_data()

        # Rename directory
        base_dir, _ = self._root_dir.rsplit(os.path.sep, 1)
        os.rename(self._root_dir, os.path.join(base_dir, value))
        self._root_dir = os.path.join(base_dir, value)

    @property
    def description(self):
        return self._data["labbook"]["description"]

    @description.setter
    def description(self, value):
        self._data["labbook"]["description"] = self._santize_input(value)
        self._save_labbook_data()

    # TODO: Replace with a user class instance once proper user interface implemented
    @property
    def username(self):
        return self._data["owner"]["username"]
    # PROPERTIES

    def _save_labbook_data(self):
        """Method to save changes to the LabBook

        Returns:
            None
        """
        with open(os.path.join(self.root_dir, ".gigantum", "labbook.yaml"), 'wt') as lbfile:
            lbfile.write(yaml.dump(self._data, default_flow_style=False))

    def _validate_labbook_data(self):
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

    def new(self, username=None, name=None, description=None):
        """Method to create a new minimal LabBook instance on disk

        /[LabBook name]
            /code
            /input
            /output
            /.gigantum
                labbook.yaml
                /env
                    Dockerfile
                /notes
                    /log
                    /index
            /.git

        Args:
            username:
            name:
            description:

        Returns:
            str: Path to the LabBook contents
        """
        if not username:
            username = "default"

        # Build data file contents
        self._data = {"labbook": {"id": uuid.uuid4().hex,
                                  "name": name,
                                  "description": self._santize_input(description)},
                      "owner": {"username": username}
                      }

        # Validate data
        self._validate_labbook_data()

        # Verify or Create user subdirectory
        # Make sure you expand a user dir string
        starting_dir = os.path.expanduser(self.labmanager_config.config["git"]["working_directory"])
        user_dir = os.path.join(starting_dir, username)
        if not os.path.isdir(user_dir):
            os.makedirs(user_dir)

        # Verify name not already in use
        if os.path.isdir(os.path.join(user_dir, name)):
            # Exists already. Raise an exception
            raise ValueError("LabBook `{}` already exists locally. Choose a new LabBook name".format(name))

        # Create LabBook subdirectory
        self._root_dir = os.path.join(user_dir, name)
        os.makedirs(self.root_dir)

        # Init repository
        git = get_git_interface(self.labmanager_config.config["git"])
        git.set_working_directory(self.root_dir)
        git.initialize()

        # Create Directory Structure
        os.makedirs(os.path.join(self.root_dir, "code"))
        os.makedirs(os.path.join(self.root_dir, "input"))
        os.makedirs(os.path.join(self.root_dir, "output"))
        os.makedirs(os.path.join(self.root_dir, ".gigantum"))
        os.makedirs(os.path.join(self.root_dir, ".gigantum", "env"))
        os.makedirs(os.path.join(self.root_dir, ".gigantum", "notes"))
        os.makedirs(os.path.join(self.root_dir, ".gigantum", "notes", "log"))
        os.makedirs(os.path.join(self.root_dir, ".gigantum", "notes", "index"))

        # Create labbook.yaml file
        self._save_labbook_data()

        # Create blank Dockerfile
        # TODO: Add better base dockerfile once environment service defines this
        with open(os.path.join(self.root_dir, ".gigantum", "env", "Dockerfile"), 'wt') as dockerfile:
            dockerfile.write("FROM ubuntu:16.04")

        # Commit
        # TODO: Once users are properly added, create a GitAuthor instance before commit
        git.add(os.path.join(self.root_dir, ".gigantum", "labbook.yaml"))
        git.add(os.path.join(self.root_dir, ".gigantum", "env", "Dockerfile"))
        git.commit("Creating new empty LabBook: {}".format(name))

        return self.root_dir

    def from_directory(self, root_dir):
        """Method to populate a LabBook instance from a directory

        Args:
            root_dir(str): The absolute path to the directory containing the LabBook

        Returns:
            LabBook
        """
        # Update root dir
        self._root_dir = root_dir

        # Load LabBook data file
        with open(os.path.join(self.root_dir, ".gigantum", "labbook.yaml"), "rt") as data_file:
            self._data = yaml.load(data_file)

    def from_name(self, username, labbook_name):
        """Method to populate a LabBook instance based on the user and name of the labbook

        Args:
            username(str): The username of the owner of the LabBook
            labbook_name(str): the name of the LabBook

        Returns:
            LabBook
        """
        # Update root dir
        self._root_dir = os.path.join(self.labmanager_config.config["git"]["working_directory"],
                                      username,
                                      labbook_name)

        # Be sure to expand in case a user dir string is used
        self._root_dir = os.path.expanduser(self._root_dir)

        # Make sure directory exists
        if not os.path.isdir(self._root_dir):
            raise ValueError("LabBook `{}` not found locally.".format(labbook_name))

        # Load LabBook data file
        with open(os.path.join(self.root_dir, ".gigantum", "labbook.yaml"), "rt") as data_file:
            self._data = yaml.load(data_file)

    def list_local_labbooks(self, username=None):
        """Method to list available LabBooks

        Args:
            username(str): Username to filter the query on

        Returns:
            (dict(list)): A dictionary of lists of LabBook Names, one entry per user
        """
        # Make sure you expand a user string
        working_dir = os.path.expanduser(self.labmanager_config.config["git"]["working_directory"])

        if not username:
            # Return all available labbooks
            files_collected = glob.glob(os.path.join(working_dir,
                                                     "*",
                                                     "*"))
        else:
            # Return only labbooks for the provided user
            files_collected = glob.glob(os.path.join(working_dir,
                                                     username,
                                                     "*"))
        # Generate dictionary to return
        result = {}
        for dir_path in files_collected:
            if os.path.isdir(dir_path):
                _, user, labbook = dir_path.rsplit(os.path.sep, 2)
                if user not in result:
                    result[user] = []

                result[user].append(labbook)

        return result


    # DKTODO review implemented by RB
    def log(self, username=None, max_count=10):
        """Method to list commit history of a Labbook

        Args:
            username(str): Username to filter the query on

        Returns:
        """

        # RBTODO this function should go away and callers should used labbook interface directly?  
        # otherwise we're writing a wrapper for every git calls in labbook.
        #
        # DKTODO probably want to make git -> self.git so you have an interface 
        #     after you from_name
        # Init repository
        git = get_git_interface(self.labmanager_config.config["git"])
        git.set_working_directory(self.root_dir)

        return git.log ( max_count=max_count )


    # RBTODO -- same question about wrappers.  Remove!
    def commit (self, message, author=None, username=None):

        git = get_git_interface(self.labmanager_config.config["git"])
        git.set_working_directory(self.root_dir)

        return git.commit ( message, author=author )


