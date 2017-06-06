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

        Returns:
            (GitRepoInterface)
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


class GitAuthor(object):
    """Simple Class to store user information for author/committer"""

    def __init__(self, name, email):
        """

        Args:
            name(str): User's first and last name
            email(str): User's email address
        """
        self.name = name
        self.email = email

    def __str__(self):
        return "{} - {}".format(self.name, self.email)


class GitRepoInterface(metaclass=abc.ABCMeta):

    def __init__(self, config_dict, author=None, committer=None):
        """Constructor

        config_dict should contain any custom params needed for the backend. For example, the working directory
        for a local backend or a service URL for a web service based backend.

        Args:
            config_dict(dict): Configuration details for the interface
            author(GitAuthor): User info for the author, if omitted, assume the "system"
            committer(GitAuthor): User info for the committer. If omitted, set to the author
        """
        self.config = config_dict
        self.current_branch = None
        self.author = None
        self.committer = None

        self.update_author(author=author, committer=committer)

    def update_author(self, author, committer=None):
        """Method to get the current branch name

        Args:
            author(GitAuthor): User info for the author, if omitted, assume the "system"
            committer(GitAuthor): User info for the committer. If omitted, set to the author

        Returns:
            None
        """
        if author:
            if type(author) != GitAuthor:
                raise ValueError("Must provide a GitAuthor instance to specify the author")
            self.author = author
        else:
            self.author = GitAuthor("Gigantum AutoCommit", "noreply@gigantum.io")

        if committer:
            if type(committer) != GitAuthor:
                raise ValueError("Must provide a GitAuthor instance to specify the committer")
            self.committer = committer
        else:
            self.committer = self.author

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
            filename(str): Filename to add.

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
    def diff_unstaged(self, filename=None, ignore_white_space=True):
        """Method to return the diff for unstaged files, optionally for a specific file

        Returns a dictionary of the format:

            {
                "<filename>": [(<line_string>, <change_string>), ...],
                ...
            }

        Args:
            filename(str): Optional filename to filter diff. If omitted all files will be diffed
            ignore_white_space (bool): If True, ignore whitespace during diff. True if omitted

        Returns:
            dict
        """
        raise NotImplemented

    @abc.abstractmethod
    def diff_staged(self, filename=None, ignore_white_space=True):
        """Method to return the diff for staged files, optionally for a specific file

        Returns a dictionary of the format:

            {
                "<filename>": [(<line_string>, <change_string>), ...],
                ...
            }

        Args:
            filename(str): Optional filename to filter diff. If omitted all files will be diffed
            ignore_white_space (bool): If True, ignore whitespace during diff. True if omitted

        Returns:
            dict
        """
        raise NotImplemented

    @abc.abstractmethod
    def diff_commits(self, commit_a='HEAD~1', commit_b='HEAD', ignore_white_space=True):
        """Method to return the diff between two commits

        Returns a dictionary of the format:

            {
                "<filename>": [(<line_string>, <change_string>), ...],
                ...
            }

        Args:
            commit_a(str): Commit hash for the first commit
            commit_b(str): Commit hash for the second commit
            ignore_white_space (bool): If True, ignore whitespace during diff. True if omitted

        Returns:
            dict
        """
        raise NotImplemented

    @abc.abstractmethod
    def commit(self, message, author=None, committer=None):
        """Method to perform a commit operation

        Commit operation should use self.author and self.committer. If author/committer provided
        the implementation should update self.author and self.committer

        Args:
            message(str): Commit message
            author(GitAuthor): User info for the author, if omitted, assume the "system"
            committer(GitAuthor): User info for the committer. If omitted, set to the author

        Returns:
            None
        """
        raise NotImplemented
    # LOCAL CHANGE METHODS

    # HISTORY METHODS
    @abc.abstractmethod
    def log(self, max_count=10, filename=None, skip=None, since=None, author=None):
        """Method to get the commit history, optionally for a single file, with pagination support

        Returns an ordered list of dictionaries, one entry per commit. Dictionary format:

            {
                "commit": <commit hash (str)>,
                "author": {"name": <name (str)>, "email": <email (str)>},
                "committer": {"name": <name (str)>, "email": <email (str)>},
                "committed_on": <commit datetime (datetime.datetime)>,
                "message: <commit message (str)>
            }

        Args:
            filename(str): Optional filename to filter on
            max_count(int): Optional number of commit records to return
            skip(int): Optional number of commit records to skip (supports building pagination)
            since(datetime.datetime): Optional *date* to limit on
            author(str): Optional filter based on author name

        Returns:
            (list(dict))
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
