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

import os
import yaml

from lmcommon.configuration import Configuration


class EnvironmentRepositoryManager(object):
    """Class to manage local copies of Environment Component Repositories
    """

    def __init__(self, config_file: str=None):
        """Constructor

        Args:
            config_file(str): Optional config file location if don't want to load from default location
        """
        self.config = Configuration(config_file=config_file)
        self.local_repo_directory = os.path.expanduser(os.path.join(self.config.config["git"]['working_directory'],
                                                       ".labmanager", "environment_repositories"))
        self.git = get_git_interface(self.config.config['git'])

    def _repo_url_to_name(self, url: str) -> str:
        """Method to generate a directory name from the repo URL for local storage

        Args:
            url(str): repository URL

        Returns:
            str
        """
        url, _ = url.rsplit(".git",1)
        _, namespace, repo = url.rsplit("/", 2)
        return "{}_{}".format(namespace, repo)

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

    def update_repositories(self) -> None:
        """Method to update all repositories in the LabManager configuration file

        If the repositories do not exist, they are cloned

        Returns:
            None
        """
        # Get repo Urls
        repo_urls = self.config.config["environment"]["repo_url"]

        for repo_url in repo_urls:
            repo_dir_name = self._repo_url_to_name(repo_url)
            repo_dir = os.path.join(self.local_repo_directory, repo_dir_name)

            # Check if repo exists locally
            if not os.path.exists(repo_dir):
                # Need to clone
                self._clone_repo(repo_url, repo_dir)

            else:
                # Need to update
                self._update_repo(repo_dir)

    def index_base_images(self, repo_name: str) -> OrderedDict:
        """Method to index base image sub dir of a repo

        Args:
            repo_name(str): The name of the repo cloned locally

        Returns:
            OrderedDict
        """
        # Get full path to repo
        repo_dir = os.path.join(self.local_repo_directory, repo_name)
        base_image_repo_dir = os.path.join(repo_dir, 'base_image')

        # Get all base image YAML files
        yaml_files = glob.glob(os.path.join(base_image_repo_dir,
                                            "*",
                                            "*",
                                            "*"))

        data = OrderedDict()
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

                yaml_data["namespace"] = namespace

                if namespace not in data[repo_name]:
                    data[repo_name][namespace] = OrderedDict()

                if component_name not in data[repo_name][namespace]:
                    data[repo_name][namespace][component_name] = OrderedDict()

                data[repo_name][namespace][component_name]["{}.{}.{}".format(yaml_data['info']['version_major'],
                                                                             yaml_data['info']['version_minor'],
                                                                             yaml_data['info']['version_build']
                                                                             )] = yaml_data

        # TODO: Sort recursively to provide both deterministic result and versions in order with newest first

        return data

    def index_repositories(self):
        """Method to index repos using a naive approach

        Stores index data in a pickled dictionaries in <working_directory>/.labmanager/environment_repositories/.index/

        Returns:
            None
        """
        # Get all local repos
        repo_urls = self.config.config["environment"]["repo_url"]
        repo_names = [self._repo_url_to_name(x) for x in repo_urls]

        base_image_all_repo_data = OrderedDict()
        for repo_name in repo_names:
            # Index Base Images
            base_image_all_repo_data.update(self.index_base_images(repo_name))

            # TODO: Index other categories

        # Write file
        with open(os.path.join(self.local_repo_directory, "base_image_index.pickle"), 'wb') as fh:
            pickle.dump(base_image_all_repo_data, fh)

        # TODO: Write other categories to disk
