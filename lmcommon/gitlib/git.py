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

import abc
import importlib

# Dictionary of supported implementations.
# Key is the value to put in the config_dict["backend"].
# Value is a list with the first entry being the module and the second the class
SUPPORTED_GIT_INTERFACES = {'filesystem': ["lmcommon.gitlib.git_fs", "GitFilesystem"]}


def get_git_interface(config_dict):
        """Factory method that instantiates a GitInterface implementation based on provided configuration information

        Note: `backend` is a required key in config_dict that specifies the gitlib backend implementation to use.

            Supported Implementations:
                - "filesystem" - Provides an interface that works on any repo on the filesystem

        Args:
            config_dict(dict): Dictionary of configuration information
        """

        if "backend" not in config_dict:
            raise ValueError("You must specify the `backend` parameter to instantiate a GitInterface implementation")

        if config_dict["backend"] not in SUPPORTED_GIT_INTERFACES:
            raise ValueError("Unsupported `backend` parameter {}. Valid backends: {}".format(config_dict["backend"],
                                                                                             ",".join(SUPPORTED_GIT_INTERFACES.keys())))
        # If you are here OK to import class
        backend_class = getattr(importlib.import_module(SUPPORTED_GIT_INTERFACES[config_dict["backend"]][0]),
                                                        SUPPORTED_GIT_INTERFACES[config_dict["backend"]][1])

        # Instantiate with the config dict and return to the user
        return backend_class(config_dict)


class GitRepoInterface(metaclass=abc.ABCMeta):

    def __init__(self, config_dict):
        """Constructor

        config_dict should contain any custom params needed for the backend. For example, the working directory
        for a local backend or a service URL for a web service based backend.

        Args:
            config_dict(dict): Configuration details for the interface
        """
        self.config = config_dict
        self.current_branch = None

    @abc.abstractmethod
    def get_current_branch_name(self):
        """Method to get the current branch name

        Returns:
            str
        """
        raise NotImplemented

    # CREATE METHODS
    @abc.abstractmethod
    def initialize(self):
        """Initialize a new repo

        Returns:
            None
        """
        raise NotImplemented

    @abc.abstractmethod
    def clone(self, source):
        """Clone a repo

        Args:
            source (str): Git ssh or https string to clone

        Returns:
            None
        """
        raise NotImplemented

    # CREATE METHODS

    # LOCAL CHANGE METHODS
    @abc.abstractmethod
    def status(self):
        """Get the status of a repo

        Should return a dictionary of lists of tuples of the following format:

            {
                "staged_new": [(filename, status), ...],
                "unstaged": [(filename, status), ...],
                "untracked": [filename, ...]
            }

            status is the status of the file (new, modified, deleted)

        Returns:
            dict(list)
        """
        raise NotImplemented

    @abc.abstractmethod
    def add(self, filename):
        """Add a file to a commit

        Args:
            filename(str): Filename to add. Should support `.` to add all files

        Returns:
            None
        """
        raise NotImplemented

    @abc.abstractmethod
    def remove(self, filename, force=False, keep_file=True):
        """Remove a file from tracking

        Args:
            filename(str): Filename to add. Should support `.` to add all files
            force(bool): Force removal
            keep_file(bool): If true, don't delete the file (e.g. use the --cached flag)

        Returns:
            None
        """
        raise NotImplemented

    @abc.abstractmethod
    def diff_file(self, filename, commit=None):
        """Method to return the diff for a file, optionally compared to a specific commit

        Args:
            filename(str): relative file path
            commit (str): Optional commit. If omitted, the current HEAD will be used

        Returns:
            str
        """
        raise NotImplemented

    @abc.abstractmethod
    def diff_commits(self, src_commit, target_commit, filename=None):
        """Method to return the diff between two commits, optionally for a specific file

        Args:
            src_commit(str): The source commit
            target_commit (str): The target commit
            filename (str): An optional file to diff

        Returns:
            str
        """
        raise NotImplemented

    @abc.abstractmethod
    def commit(self, message, all=False, author=None, amend=False):
        """Method to perform a commit operation

        Args:
            message(str): Commit message
            all(bool): If True, commit all changes in tracked files
            author(str): If set, replace the author with the provided string
            amend(bool): If True, ammend the previous commit (typically used to fix a commit message)

        Returns:

        """
        raise NotImplemented
    # LOCAL CHANGE METHODS

    # HISTORY METHODS
    @abc.abstractmethod
    def log(self, filename=None):
        """Method to get the commit history, optionally for a single file

        Returns an ordered list of dictionaries, one entry per commit. Dictionary format:

            {
                "commit": <commit>,
                "author": <author>,
                "datetime": <datetime>,
                "message: <commit message>
            }


        Args:
            filename(str): Optional filename to filter on

        Returns:
            list(dict)
        """
        raise NotImplemented

    @abc.abstractmethod
    def blame(self, filename):
        """Method to get the revision and author for each line of a file

        Returns an ordered list of dictionaries, one entry per change. Dictionary format:

            {
                "commit": <commit>,
                "previous_commit": <previous commit>,
                "author": <author>,
                "author_email": <author email if available>,
                "datetime": <datetime>,
                "message: <commit message>
            }


        Args:
            filename(str): Filename to query

        Returns:
            list(dict)
        """
        raise NotImplemented
    # HISTORY METHODS

    # BRANCH METHODS
    @abc.abstractmethod
    def create_branch(self, name):
        """Method to create a new branch from the current HEAD

        Args:
            name(str): Name of the branch

        Returns:
            None
        """
        raise NotImplemented

    @abc.abstractmethod
    def list_branches(self):
        """Method to list branches. Should return a dictionary of the format:

            {
                "local": [(<name>, <short_hash>, <message>), ...]
                "remote": [(<name>, <short_hash>, <message>), ...]
            }

            The first "local" entry is always the HEAD

        Returns:
            dict(list(tuple))
        """
        raise NotImplemented

    @abc.abstractmethod
    def delete_branch(self, name, remote=False, force=False):
        """Method to delete a branch

        Args:
            name(str): Name of the branch to delete
            remote(bool): If True, delete a remote branch
            force(bool): If True, force delete

        Returns:
            None
        """
        raise NotImplemented

    @abc.abstractmethod
    def rename_branch(self, old_name, new_name):
        """Method to rename a branch

        Args:
            old_name(str): The old branch name
            new_name(str): The new branch name

        Returns:
            None
        """
        raise NotImplemented

    @abc.abstractmethod
    def checkout(self, branch):
        """Method to switch to a different branch

        Args:
            branch(str): Name of the branch to switch to

        Returns:
            None
        """
        raise NotImplemented
    # BRANCH METHODS

    # TAG METHODS
    @abc.abstractmethod
    def create_tag(self, name):
        """Method to create a tag

        Args:
            name(str): Name of the tag

        Returns:
            None
        """
        raise NotImplemented
    # TAG METHODS

    # REMOTE METHODS
    @abc.abstractmethod
    def list_remotes(self):
        """Method to list remote information

        Returns a list of dictionaries with the format:

            {
                "name": <remote name>,
                "url": <remote location>,
            }

        Returns:
            list(dict)
        """
        raise NotImplemented

    @abc.abstractmethod
    def add_remote(self, name, url):
        """Method to add a new remote

        Args:
            name(str): Name of the remote
            url(str): URL to the remote

        Returns:
            None
        """

        raise NotImplemented

    @abc.abstractmethod
    def fetch(self):
        """Method to download objects and refs from a remote

        Returns:
            None
        """
        raise NotImplemented

    @abc.abstractmethod
    def pull(self):
        """Method fetch and integrate a remote

        Returns:
            None
        """
        raise NotImplemented

    @abc.abstractmethod
    def push(self, remote_name, tags=False):
        """Method update remote refs along with associated objects

        Args:
            remote_name(str): Name of the remote repository
            tags(bool): If true, push tags

        Returns:

        """
        raise NotImplemented
    # REMOTE METHODS

    # MERGE METHODS
    @abc.abstractmethod
    def merge(self, branch_name):
        """Method to join a branch history with the current branch

        Args:
            branch_name(str): Name of the branch to merge into the current branch

        Returns:
            None
        """
        raise NotImplemented

    @abc.abstractmethod
    def abort_merge(self):
        """Method to abort a merge operation

        Returns:
            None
        """
        raise NotImplemented
    # MERGE METHODS

    # UNDO METHODS
    @abc.abstractmethod
    def discard_changes(self, filename=None):
        """Discard all changes, or changes in a single file.

        Args:
            filename(str): Optional filename. If omitted, all changes are discarded

        Returns:
            None
        """
        raise NotImplemented

    @abc.abstractmethod
    def revert(self, commit):
        """Revert changes into a new commit by replaying with appropriate changes

        Args:
            commit(str): Commit to revert to

        Returns:
            None
        """
        raise NotImplemented

    @abc.abstractmethod
    def reset_head(self, commit, hard=False, keep=False):
        """Reset current head to a specified state

        Args:
            commit(str): Commit to reset head to
            hard(bool): If True, Resets so any changes to tracked files in the working tree since <commit> are discarded
            keep(bool): If True, Resets and updates files in the working tree that are different between <commit> and
                        HEAD. If a file that is different between <commit> and HEAD has local changes, reset is aborted.

        Returns:
            None
        """
        raise NotImplemented
    # UNDO METHODS

    # SUBMODULE METHODS
    @abc.abstractmethod
    def add_submodule(self, repository, relative_path):
        """Method to add a submodule at the provided relative path to the repo root

        Args:
            repository(str): URL to the remote repository
            relative_path(str): Relative path from the repo root where the submodule should go

        Returns:
            None
        """
        raise NotImplemented

    @abc.abstractmethod
    def list_submodules(self):
        """Method to list submodules

            Should return a list of tuples with the format:

                [(name, commit), ...]

        Returns:
            list(tuple)
        """
        raise NotImplemented

    @abc.abstractmethod
    def init_submodules(self):
        """Method to init submodules

        Returns:
            None
        """
        raise NotImplemented

    @abc.abstractmethod
    def deinit_submodules(self, submodule_path, force=False, delete=False):
        """Method to deinit submodules

        submodule_path:
            submodule_path(str): Path to the submodule to deinit
            force(bool): If True, force deinit operation
            delete(bool): If True, make sure submodule directory has been removed from repository

        Returns:
            None
        """
        raise NotImplemented
