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

from lmcommon.gitlib import get_git_interface, GitAuthor
from lmcommon.configuration import Configuration
from lmcommon.logging import LMLogger

GIT_IGNORE_DEFAULT = """.DS_Store"""
logger = LMLogger.logger


class LabBook(object):
    """Class representing a single LabBook"""

    def __init__(self, config_file=None):
        logger.info("Creating labbook from config file {}".format(config_file or '<None>'))

        self.labmanager_config = Configuration(config_file)

        # Create gitlib instance
        self.git = get_git_interface(self.labmanager_config.config["git"])

        # LabBook Properties
        self._root_dir = None  # The root dir is the location of the labbook this instance represents
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
        
        # Update the root directory to the knew directory name
        self._set_root_dir(os.path.join(base_dir, value))

    @property
    def description(self):
        return self._data["labbook"]["description"]

    @description.setter
    def description(self, value):
        self._data["labbook"]["description"] = self._santize_input(value)
        self._save_labbook_data()

    # TODO: Replace with a user class instance once proper user interface implemented
    @property
    def owner(self):
        return self._data["owner"]

    # TODO: Replace with a user class instance once proper user interface implemented
    @property
    def user(self):
        """Property containing information about the current logged in user
            Dictionary of values:
                "name" - First Last name
                "email" - user's email address
                "username" - user's username

        """
        return self._data["user"]

    @user.setter
    def user(self, value):
        """

        Args:
            value:

        Returns:

        """
        self._data["user"] = value

        # Update gitlib to have the right user information
        self.git.update_author(GitAuthor(value["name"], value["email"]))
    # PROPERTIES

    def _set_root_dir(self, new_root_dir):
        """Update the root directory and also reconfigure the git instance

        Returns:
            None
        """
        # Be sure to expand in case a user dir string is used
        self._root_dir = os.path.expanduser(new_root_dir)

        # Update the git working directory
        self.git.set_working_directory(self.root_dir)

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

    # TODO: Get feedback on better way to sanitize
    def _santize_input(self, value):
        """Simple method to sanitize a user provided value with characters that can be bad

        Args:
            value(str): Input string

        Returns:
            str: Output string
        """
        return''.join(c for c in value if c not in '\<>?/;"`\'')

    def new(self, owner, name, username=None, description=None):
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
            owner(dict): Owner information. Can be a user or a team/org.
            name(str): Name of the LabBook
            username(str): Username of the logged in user. Used to store the LabBook in the proper location. If omitted
                           the owner username is used
            description(str): A short description of the LabBook

        Returns:
            str: Path to the LabBook contents
        """
        if not owner:
            raise ValueError("You must provide owner details when creating a LabBook.")

        if not username:
            logger.warning("Using owner username `{}` when making new labbook".format(owner['username']))
            username = owner["username"]

        # Build data file contents
        self._data = {"labbook": {"id": uuid.uuid4().hex,
                                  "name": name,
                                  "description": self._santize_input(description)},
                      "owner": owner
                      }

        # Validate data
        self._validate_labbook_data()

        # Verify or Create user subdirectory
        # Make sure you expand a user dir string
        starting_dir = os.path.expanduser(self.labmanager_config.config["git"]["working_directory"])
        user_dir = os.path.join(starting_dir, username)
        if not os.path.isdir(user_dir):
            os.makedirs(user_dir)

        # Create owner dir - store LabBooks in working dir > logged in user > owner
        owner_dir = os.path.join(user_dir, owner["username"])
        if not os.path.isdir(owner_dir):
            os.makedirs(owner_dir)

            # Create `labbooks` subdir in the owner dir
            owner_dir = os.path.join(owner_dir, "labbooks")
        else:
            owner_dir = os.path.join(owner_dir, "labbooks")

        # Verify name not already in use
        if os.path.isdir(os.path.join(owner_dir, name)):
            # Exists already. Raise an exception
            raise ValueError("LabBook `{}` already exists locally. Choose a new LabBook name".format(name))

        # Create LabBook subdirectory
        new_root_dir = os.path.join(owner_dir, name)

        logger.info("Making labbook directory in {}".format(new_root_dir))

        os.makedirs(new_root_dir)
        self._set_root_dir(new_root_dir)

        # Init repository
        self.git.initialize()

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

        # Create .gitignore default file
        # TODO: Use a base .gitignore file vs. global variable
        with open(os.path.join(self.root_dir, ".gitignore"), 'wt') as gi_file:
            gi_file.write(GIT_IGNORE_DEFAULT)

        # Commit
        # TODO: Once users are properly added, create a GitAuthor instance before commit
        self.git.add(os.path.join(self.root_dir, ".gigantum", "labbook.yaml"))
        self.git.add(os.path.join(self.root_dir, ".gigantum", "env", "Dockerfile"))
        self.git.add(os.path.join(self.root_dir, ".gitignore"))
        self.git.commit("Creating new empty LabBook: {}".format(name))

        return self.root_dir

    def from_directory(self, root_dir):
        """Method to populate a LabBook instance from a directory

        Args:
            root_dir(str): The absolute path to the directory containing the LabBook

        Returns:
            LabBook
        """

        logger.info("Populating LabBook from directory {}".format(root_dir))

        # Update root dir
        self._set_root_dir(root_dir)

        # Load LabBook data file
        with open(os.path.join(self.root_dir, ".gigantum", "labbook.yaml"), "rt") as data_file:
            self._data = yaml.load(data_file)

    def from_name(self, username, owner, labbook_name):
        """Method to populate a LabBook instance based on the user and name of the labbook

        Args:
            username(str): The username of the logged in user
            owner(str): The username/org name of the owner of the LabBook
            labbook_name(str): the name of the LabBook

        Returns:
            LabBook
        """

        if not username:
            raise ValueError("Username cannot be None or empty")

        if not owner:
            raise ValueError("owner cannot be None or empty")

        if not labbook_name:
            raise ValueError("labbook_name cannot be None or empty")

        logger.info("Populating LabBook from name -- username: {}, owner: {}, labbook_name: {}".format(username, owner,
                                                                                                       labbook_name))

        labbook_path = os.path.expanduser(os.path.join(self.labmanager_config.config["git"]["working_directory"],
                                                       username,
                                                       owner,
                                                       "labbooks",
                                                       labbook_name))

        # Make sure directory exists
        if not os.path.isdir(labbook_path):
            raise ValueError("LabBook `{}` not found locally.".format(labbook_name))

        # Update root dir
        self._set_root_dir(labbook_path)

        # Load LabBook data file
        with open(os.path.join(self.root_dir, ".gigantum", "labbook.yaml"), "rt") as data_file:
            self._data = yaml.load(data_file)

    def list_local_labbooks(self, username=None):
        """Method to list available LabBooks

        Args:
            username(str): Username to filter the query on

        Returns:
            dict: A dictionary containing labbooks grouped by local username
        """
        # Make sure you expand a user string
        working_dir = os.path.expanduser(self.labmanager_config.config["git"]["working_directory"])

        if not username:
            # Return all available labbooks
            files_collected = glob.glob(os.path.join(working_dir,
                                                     "*",
                                                     "*",
                                                     "labbooks",
                                                     "*"))
        else:
            # Return only labbooks for the provided user
            files_collected = glob.glob(os.path.join(working_dir,
                                                     username,
                                                     "*",
                                                     "labbooks",
                                                     "*"))
        # Sort to give deterministic response
        files_collected = sorted(files_collected)

        # Generate dictionary to return
        result = {}
        for dir_path in files_collected:
            if os.path.isdir(dir_path):
                _, username, owner, _, labbook = dir_path.rsplit(os.path.sep, 4)
                if username not in result:
                    result[username] = []

                result[username].append({"owner": owner, "name": labbook})

        return result

    def log(self, username=None, max_count=10):
        """Method to list commit history of a Labbook

        Args:
            username(str): Username to filter the query on

        Returns:
            dict
        """
        # TODO: Add additional optional args to the git.log call to support further filtering
        return self.git.log(max_count=max_count, author=username)

    def log_entry(self, commit):
        """Method to get a single log entry by commit

        Args:
            commit(str): commit hash of the entry

        Returns:
            dict
        """
        return self.git.log_entry(commit)
