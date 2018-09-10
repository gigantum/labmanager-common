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
import pickle
from typing import (Any, List, Dict)

from lmcommon.configuration import Configuration


class ComponentRepository(object):
    """Class to interface with local copies of environment component repositories
    """

    def __init__(self, config_file: str=None) -> None:
        """Constructor

        Args:
            config_file(str): Optional config file location if don't want to load from default location
        """
        self.config = Configuration(config_file=config_file)
        self.local_repo_directory = os.path.expanduser(os.path.join(self.config.config["git"]['working_directory'],
                                                       ".labmanager", "environment_repositories"))

        # Dictionary to hold loaded index files in memory
        self.list_index_data: Dict[str, Any] = {}
        self.detail_index_data: Dict[str, Any] = {}

    def _get_list_index_data(self, component_class: str) -> List[str]:
        """Private method to get list index data from either the file or memory

        Args:
            component_class(str): Name of the component class (e.g. base_image)

        Returns:
            list: the data stored in the index file
        """
        if component_class not in self.list_index_data:
            # Load data for the first time
            with open(os.path.join(self.local_repo_directory, f"{component_class}_list_index.pickle"),
                      'rb') as fh:
                self.list_index_data[component_class] = pickle.load(fh)

        return self.list_index_data[component_class]

    def _get_detail_index_data(self, component_class: str) -> Dict[str, Any]:
        """Private method to get detail index data from either the file or memory

        Args:
            component_class(str): Name of the component class (e.g. "base" or "custom")

        Returns:
            dict: the data stored in the index file
        """
        if component_class not in self.detail_index_data:
            # Load data for the first time
            with open(os.path.join(self.local_repo_directory, "{}_index.pickle".format(component_class)),
                      'rb') as fh:
                self.detail_index_data[component_class] = pickle.load(fh)

        return self.detail_index_data[component_class]

    def get_component_list(self, component_class: str) -> List[str]:
        """Method to get a list of all components of a specific class (e.g base_image, development_environment, etc)
        The component class should map to a directory in the component repository

        Returns:
            list
        """
        index_data = self._get_list_index_data(component_class)

        return index_data

    def get_component_versions(self, component_class: str, repository: str, component: str) -> List[str]:
        """Method to get a detailed list of all available versions for a single component

        Args:
            component_class(str): class of the component (e.g. base_image, development_env, etc)
            repository(str): name of the component as provided via the list (<namespace>_<repo name>)
            component(str): name of the component

        Returns:
            list
        """
        # Open index
        index_data = self._get_detail_index_data(component_class)

        if repository not in index_data:
            raise ValueError("Repository `{}` not found.".format(repository))

        if component not in index_data[repository]:
            raise ValueError("Component `{}` not found in repository `{}`.".format(component, repository))

        return list(index_data[repository][component].items())

    def get_component(self, component_class: str, repository: str, component: str, revision: int) -> Dict[str, Any]:
        """Method to get a detailed list of all available versions for a single component

        Args:
            component_class(str): class of the component (e.g. base_image, development_env, etc)
            repository(str): name of the component as provided via the list (<namespace>_<repo name>)
            component(str): name of the component
            revision(str): the version string of the component

        Returns:
            dict
        """
        index_data = self._get_detail_index_data(component_class)

        if repository not in index_data:
            raise ValueError("Repository `{}` not found.".format(repository))

        if component not in index_data[repository]:
            raise ValueError("Component `{}` not found in repository `{}`.".format(component, repository))

        if revision not in index_data[repository][component]:
            raise ValueError("Version `{}` not found in repository `{}`.".format(revision, repository))

        return index_data[repository][component][revision]
