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
import pickle
from collections import OrderedDict

import os

from lmcommon.configuration import Configuration


class ComponentRepository(object):
    """Class to interface with local copies of environment component repositories
    """

    def __init__(self, config_file: str=None):
        """Constructor

        Args:
            config_file(str): Optional config file location if don't want to load from default location
        """
        self.config = Configuration(config_file=config_file)
        self.local_repo_directory = os.path.expanduser(os.path.join(self.config.config["git"]['working_directory'],
                                                       ".labmanager", "environment_repositories"))

    def get_component_list(self, component_class: str) -> list:
        """Method to get a list of all components of a specific class (e.g base_image, development_environment, etc)
        The component class should map to a directory in the component repository

        Returns:
            list
        """
        # Open index
        with open(os.path.join(self.local_repo_directory, "{}_list_index.pickle".format(component_class)), 'rb') as fh:
            index_data = pickle.load(fh)

        return index_data

    def get_component_versions(self, component_class: str, repository: str, namespace: str, component: str) -> list:
        """Method to get a detailed list of all available versions for a single component

        Args:
            component_class(str): class of the component (e.g. base_image, development_env, etc)
            repository(str): name of the component as provided via the list (<namespace>_<repo name>)
            namespace(str): namespace within the component repo
            component(str): name of the component

        Returns:
            list
        """
        # Open index
        with open(os.path.join(self.local_repo_directory, "{}_index.pickle".format(component_class)), 'rb') as fh:
            index_data = pickle.load(fh)

        if repository not in index_data:
            raise ValueError("Repository `{}` not found.".format(repository))

        if namespace not in index_data[repository]:
            raise ValueError("Namespace `{}` not found in repository `{}`.".format(namespace, repository))

        if component not in index_data[repository][namespace]:
            raise ValueError("Component `{}` not found in repository `{}`.".format(component, repository))

        return list(index_data[repository][namespace][component].items())



