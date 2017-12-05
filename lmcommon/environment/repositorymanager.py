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
from lmcommon.gitlib import get_git_interface
import glob
from collections import OrderedDict
import pickle
import operator
import requests
from lmcommon.logging import LMLogger

import os
import yaml

from typing import (Any, List, Dict)

from lmcommon.configuration import Configuration

logger = LMLogger.get_logger()


def repo_url_to_name(url: str) -> str:
    """Method to generate a directory name from the repo URL for local storage

    Args:
        url(str): repository URL

    Returns:
        str
    """
    url, _ = url.rsplit(".git", 1)
    _, namespace, repo = url.rsplit("/", 2)
    return "{}_{}".format(namespace, repo)


class RepositoryManager(object):
    """Class to manage local copies of Environment Component Repositories
    """

    def __init__(self, config_file: str=None) -> None:
        """Constructor

        Args:
            config_file(str): Optional config file location if don't want to load from default location
        """
        self.config = Configuration(config_file=config_file)
        self.local_repo_directory = os.path.expanduser(os.path.join(self.config.config["git"]['working_directory'],
                                                       ".labmanager", "environment_repositories"))
        self.git = get_git_interface(self.config.config['git'])

    def _clone_repo(self, url: str, location: str) -> None:
        """Private method to clone a repository

        Args:
            url(str): the git repo url for the repository
            location(str): the directory to clone into

        Returns:
            None
        """
        # Create the directory to clone into
        os.makedirs(location)

        # Set the gitlib to point to that directory
        self.git.set_working_directory(location)

        # Clone the repo
        self.git.clone(url)

    @staticmethod
    def _internet_is_available() -> bool:
        """Private method to check if the user can get to GitHub, since that is where the component repos are

        Returns:
            None
        """
        # Create the directory to clone into
        try:
            requests.head('https://github.com', timeout=1)
        except requests.exceptions.ConnectionError:
            return False

        return True

    def _update_repo(self, location: str) -> None:
        """Private method to update a repository

        Args:
            location(str): the directory containing the repository

        Returns:
            None
        """
        # Set the gitlib to point to that directory
        self.git.set_working_directory(location)

        # Clone the repo
        self.git.fetch()
        self.git.pull()

    def update_repositories(self) -> bool:
        """Method to update all repositories in the LabManager configuration file

        If the repositories do not exist, they are cloned

        Returns:
            bool: flag indicting if repos updated successfully
        """
        if self._internet_is_available():
            # Get repo Urls
            repo_urls = self.config.config["environment"]["repo_url"]

            for repo_url in repo_urls:
                repo_dir_name = repo_url_to_name(repo_url)
                repo_dir = os.path.join(self.local_repo_directory, repo_dir_name)

                # Check if repo exists locally
                if not os.path.exists(repo_dir):
                    # Need to clone
                    self._clone_repo(repo_url, repo_dir)

                else:
                    # Need to update
                    self._update_repo(repo_dir)
            return True
        else:
            return False

    def index_component_repository(self, repo_name: str, component: str) -> OrderedDict:
        """Method to 'index' a base_image directory in a single environment component repository

        Currently, the `index` is simply an ordered dictionary of all of the base image components in the repo
        The dictionary contains the contents of the YAML files for every version of the component and is strucutured:

            {
              "<repo_name>": {
                                "info": { repo info stored in repo config.yaml }
                                "<namespace>": {
                                                  "<base_image_name>": {
                                                                          "<Major.Minor>": { YAML contents }, ...
                                                                       }, ...
                                               }, ...
                              }
            }
            
        Args:
            repo_name(str): The name of the repo cloned locally

        Returns:
            OrderedDict
        """
        # Get full path to repo
        repo_dir = os.path.join(self.local_repo_directory, repo_name)
        component_repo_dir = os.path.join(repo_dir, component)

        # Get all base image YAML files
        yaml_files = glob.glob(os.path.join(component_repo_dir,
                                            "*",
                                            "*",
                                            "*"))

        data: OrderedDict[str, Any] = OrderedDict()
        data[repo_name] = OrderedDict()

        # Set repository info
        with open(os.path.join(repo_dir, '.gigantum', 'config.yaml'), 'rt') as cf:
            repo_info = yaml.load(cf)
            data[repo_name]['info'] = repo_info

        # Read YAML files and write data to dictionary
        for yf in yaml_files:
            with open(yf, 'rt') as yf_file:
                yaml_data = yaml.load(yf_file)
                _, namespace, component_name, _ = yf.rsplit(os.path.sep, 3)

                # Save the COMPONENT namespace and repository to aid in accessing components via API
                # Will pack this info into the `component` field for use in mutations to access the component
                yaml_data["###namespace###"] = namespace
                yaml_data["###repository###"] = repo_name

                if namespace not in data[repo_name]:
                    data[repo_name][namespace] = OrderedDict()

                if component_name not in data[repo_name][namespace]:
                    data[repo_name][namespace][component_name] = OrderedDict()

                data[repo_name][namespace][component_name]["{}.{}".format(yaml_data['info']['version_major'],
                                                                          yaml_data['info']['version_minor']
                                                                          )] = yaml_data

        # Sort all levels of the index dictionary to provide both deterministic result
        # For versions, reverse the order with newest (highest version number) first
        data = OrderedDict(sorted(data.items(), key=operator.itemgetter(0)))
        for repo in list(data.keys()):
            data[repo] = OrderedDict(sorted(data[repo].items(), key=operator.itemgetter(0)))
            for namespace in list(data[repo].keys()):
                if namespace == 'info':
                    continue
                data[repo][namespace] = OrderedDict(sorted(data[repo][namespace].items(), key=operator.itemgetter(0)))
                for component in list(data[repo][namespace].keys()):
                    if component == 'info':
                        continue
                    data[repo][namespace][component] = OrderedDict(sorted(data[repo][namespace][component].items(),
                                                                   key=operator.itemgetter(0), reverse=True))
        return data

    def build_component_list_index(self, index_data: OrderedDict) -> List:
        """Method to convert the structured index of all versions into a flat list with only the latest version

        Returns:
            list
        """
        component_list = []
        repos = list(index_data.keys())
        for repo in repos:
            namespaces = list(index_data[repo].keys())
            for namespace in namespaces:
                if namespace == 'info':
                    # ignore the repository info section
                    continue

                components = list(index_data[repo][namespace].keys())

                for component in components:
                    component_list.append(list(index_data[repo][namespace][component].items())[0][1])

        return component_list

    def index_repositories(self) -> None:
        """Method to index repos using a naive approach

        Stores index data in a pickled dictionaries in <working_directory>/.labmanager/environment_repositories/.index/

        Returns:
            None
        """
        # Get all local repos
        repo_urls = self.config.config["environment"]["repo_url"]
        repo_names = [repo_url_to_name(x) for x in repo_urls]

        base_image_all_repo_data: OrderedDict = OrderedDict()
        dev_env_all_repo_data: OrderedDict = OrderedDict()
        custom_all_repo_data: OrderedDict = OrderedDict()
        for repo_name in repo_names:
            # Index Base Images
            base_image_all_repo_data.update(self.index_component_repository(repo_name, 'base_image'))

            # Index Dev Envs
            dev_env_all_repo_data.update(self.index_component_repository(repo_name, 'dev_env'))

            # Index Custom Deps
            custom_all_repo_data.update(self.index_component_repository(repo_name, 'custom'))

        # Generate list index
        base_image_list_repo_data = self.build_component_list_index(base_image_all_repo_data)
        dev_env_list_repo_data = self.build_component_list_index(dev_env_all_repo_data)
        custom_list_repo_data = self.build_component_list_index(custom_all_repo_data)

        # Write files
        with open(os.path.join(self.local_repo_directory, "base_image_index.pickle"), 'wb') as fh:
            pickle.dump(base_image_all_repo_data, fh)
        with open(os.path.join(self.local_repo_directory, "base_image_list_index.pickle"), 'wb') as fh:
            pickle.dump(base_image_list_repo_data, fh)

        with open(os.path.join(self.local_repo_directory, "dev_env_index.pickle"), 'wb') as fh:
            pickle.dump(dev_env_all_repo_data, fh)
        with open(os.path.join(self.local_repo_directory, "dev_env_list_index.pickle"), 'wb') as fh:
            pickle.dump(dev_env_list_repo_data, fh)

        with open(os.path.join(self.local_repo_directory, "custom_index.pickle"), 'wb') as fh:
            pickle.dump(custom_all_repo_data, fh)
        with open(os.path.join(self.local_repo_directory, "custom_list_index.pickle"), 'wb') as fh:
            pickle.dump(custom_list_repo_data, fh)
