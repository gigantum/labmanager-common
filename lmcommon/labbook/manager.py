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
import glob
import re

import yaml

from lmcommon.gitlib import get_git_interface
from lmcommon.configuration import Configuration


class LabBookManager(object):

    def __init__(self, config_file=None):
        """Constructor

        Args:
            config_file(str): Absolute path to the LabManager config file
        """
        self.configuration = Configuration(config_file)

    def list_labbooks(self, username=None):
        """Method to list available LabBooks

        Args:
            username(str): Username to filter the query on

        Returns:
            (dict(list)): A dictionary of lists of LabBook Names, one entry per user
        """
        if not username:
            # Return all available labbooks
            files_collected = glob.glob(os.path.join(self.configuration.config["git"]["working_directory"],
                                                     "*",
                                                     "*"))
        else:
            # Return only labbooks for the provided user
            files_collected = glob.glob(os.path.join(self.configuration.config["git"]["working_directory"],
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

    def create_labbook(self, username=None, name=None, description=None):
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
            LabBook
        """
        if not username:
            username = "default"

        # Validate name characters
        if not re.match("^(?!-)(?!.*--)[A-Za-z0-9-]+(?<!-)$", name):
            raise ValueError("Invalid `name`. Only A-Z a-z 0-9 and hyphens allowed. No leading or trailing hyphens.")

        if len(name) > 100:
            raise ValueError("Invalid `name`. Max length is 100 characters")

        # Sanitize description
        description = ''.join(c for c in description if c not in '<>?/;"`\'')

        # Verify or Create user subdirectory
        user_dir = os.path.join(self.configuration.config["git"]["working_directory"], username)
        if not os.path.isdir(user_dir):
            os.makedirs(user_dir)

        # Verify name not already in use
        if os.path.isdir(os.path.join(user_dir, name)):
            # Exists already. Raise an exception
            raise ValueError("LabBook already exists: {}".format(name))

        # Create LabBook subdirectory
        labbook_dir = os.path.join(user_dir, name)
        os.makedirs(labbook_dir)

        # Init repository
        git = get_git_interface(self.configuration.config["git"])
        git.set_working_directory(labbook_dir)
        git.initialize()

        # Create Directory Structure
        os.makedirs(os.path.join(labbook_dir, "code"))
        os.makedirs(os.path.join(labbook_dir, "input"))
        os.makedirs(os.path.join(labbook_dir, "output"))
        os.makedirs(os.path.join(labbook_dir, ".gigantum"))
        os.makedirs(os.path.join(labbook_dir, ".gigantum", "env"))
        os.makedirs(os.path.join(labbook_dir, ".gigantum", "notes"))
        os.makedirs(os.path.join(labbook_dir, ".gigantum", "notes", "log"))
        os.makedirs(os.path.join(labbook_dir, ".gigantum", "notes", "index"))

        # Create labbook.yaml file
        labbook_file_data = {"labbook": {"id": uuid.uuid4().hex,
                                         "name": name,
                                         "description": description},
                             "owner": {"username": username}
                             }
        with open(os.path.join(labbook_dir, ".gigantum", "labbook.yaml"), 'wt') as lbfile:
            lbfile.write(yaml.dump(labbook_file_data, default_flow_style=False))

        # Create blank Dockerfile
        # TODO: Add better base dockerfile once environment service defines this
        with open(os.path.join(labbook_dir, ".gigantum", "env", "Dockerfile"), 'wt') as dockerfile:
            dockerfile.write("FROM ubuntu:16.04")

        # Commit
        # TODO: Once users are properly added, create a GitAuthor instance before commit
        git.add(os.path.join(labbook_dir, ".gigantum", "labbook.yaml"))
        git.add(os.path.join(labbook_dir, ".gigantum", "env", "Dockerfile"))
        git.commit("Creating new empty LabBook: {}".format(name))

        return labbook_dir
