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
import os
import yaml


class LabBook(object):
    """Class representing a single LabBook"""

    def __init__(self):
        # LabBook Properties
        self._root_dir = None
        self._data = None

        # LabBook Environment
        self._env = None

    # PROPERTIES
    @property
    def root_dir(self):
        return self._root_dir

    @root_dir.setter
    def root_dir(self, value):
        self._root_dir = value

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, value):
        self._data = value

    @property
    def id(self):
        return self._data["labbook"]["id"]

    @id.setter
    def id(self, value):
        self._data["labbook"]["id"] = value

    @property
    def name(self):
        return self._data["labbook"]["name"]

    @name.setter
    def name(self, value):
        self._data["labbook"]["name"] = value

    @property
    def description(self):
        return self._data["labbook"]["description"]

    @description.setter
    def description(self, value):
        self._data["labbook"]["description"] = value

    # TODO: Replace with a user class instance once proper user interface implemented
    @property
    def username(self):
        return self._data["owner"]["username"]

    @username.setter
    def username(self, value):
        self._data["owner"]["username"] = value
    # PROPERTIES

    def _save_changes(self):
        """Method to save changes to the LabBook

        Returns:
            None
        """
        with open(os.path.join(self.root_dir, ".gigantum", "labbook.yaml"), 'wt') as lbfile:
            lbfile.write(yaml.dump(self._data, default_flow_style=False))

    def from_directory(self, root_dir):
        """Method to populate a LabBook instance from a directory

        Args:
            root_dir(str): The absolute path to the directory containing the LabBook

        Returns:
            LabBook
        """
        # Update root dir
        self.root_dir = root_dir

        # Load LabBook data file
        with open(os.path.join(self.root_dir, ".gigantum", "labbook.yaml"), "rt") as data_file:
            self.data = yaml.load(data_file)
