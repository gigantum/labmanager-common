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

import os
import yaml
from pkg_resources import resource_filename

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

t        for repo_url in repo_urls:
            repo_dir_name = self._repo_url_to_name(repo_url)
            repo_dir = os.path.join(self.local_repo_directory, repo_dir_name)

            # Check if repo exists locally
            if not os.path.exists(repo_dir):
                # Need to clone
                self._clone_repo(repo_url, repo_dir)

            else:
                # Need to update
                self._update_repo(repo_dir)

    def index_repositories(self):
        raise NotImplemented
