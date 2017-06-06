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
from .git import GitRepoInterface
from git import Repo
from git import InvalidGitRepositoryError
import os
import re


class GitFilesystem(GitRepoInterface):

    def __init__(self, config_dict, author=None, committer=None):
        """Constructor

        config_dict should contain any custom params needed for the backend. For example, the working directory
        for a local backend or a service URL for a web service based backend.

        Required configuration parameters in config_dict:

            {
                "backend": "filesystem"
                "working_directory": <working directory for the repository>
            }

        Args:
            config_dict(dict): Configuration details for the interface
            author(GitAuthor): User info for the author, if omitted, assume the "system"
            committer(GitAuthor): User info for the committer. If omitted, set to the author

        Attributes:
            config(dict): Configuration details
            current_branch(str): The name of the current branch
            repo(Repo): A GitPython Repo instance loaded at the
        """
        # Call super constructor
        GitRepoInterface.__init__(self, config_dict, author=author, committer=committer)

        # Check to see if the working dir is already a repository
        try:
            self.repo = Repo(self.config["working_directory"])
        except InvalidGitRepositoryError:
            # Empty Dir
            self.repo = None

    def get_current_branch_name(self):
        """Method to get the current branch name

        Returns:
            str
        """
        return self.repo.active_branch.name

    # CREATE METHODS
    def initialize(self, bare=False):
        """Initialize a new repo

        Args:
            bare(bool): If True, use the --bare option

        Returns:
            None
        """
        if self.repo:
            raise ValueError("Cannot init an existing git repository. Choose a different working directory")

        self.repo = Repo.init(self.config["working_directory"], bare=bare)

    def clone(self, source):
        """Clone a repo

        Args:
            source (str): Git ssh or https string to clone

        Returns:
            None
        """
        if self.repo:
            raise ValueError("Cannot init an existing git repository. Choose a different working directory")

        self.repo = Repo.clone_from(source, self.config["working_directory"])
    # CREATE METHODS

    # LOCAL CHANGE METHODS
    def status(self):
        """Get the status of a repo

        Should return a dictionary of lists of tuples of the following format:

            {
                "staged": [(filename, status), ...],
                "unstaged": [(filename, status), ...],
                "untracked": [filename, ...]
            }

            status is the status of the file (new, modified, deleted)

        Returns:
            dict
        """
        result = {"untracked": self.repo.untracked_files}

        # staged
        staged = []
        for f in self.repo.index.diff("HEAD"):
            if f.change_type == "D":
                # delete and new are flipped here, due to how comparison is done
                staged.append((f.b_path, "added"))
            elif f.change_type == "A":
                staged.append((f.b_path, "deleted"))
            elif f.change_type == "M":
                staged.append((f.b_path, "modified"))
            elif f.change_type == "R":
                staged.append((f.b_path, "renamed"))
            else:
                raise ValueError("Unsupported change type: {}".format(f.change_type))

        # unstaged
        unstaged = []
        for f in self.repo.index.diff(None):
            if f.change_type == "D":
                # delete and new are flipped here, due to how comparison is done
                unstaged.append((f.b_path, "deleted"))
            elif f.change_type == "A":
                unstaged.append((f.b_path, "added"))
            elif f.change_type == "M":
                unstaged.append((f.b_path, "modified"))
            elif f.change_type == "R":
                unstaged.append((f.b_path, "renamed"))
            else:
                raise ValueError("Unsupported change type: {}".format(f.change_type))

        result["staged"] = staged
        result["unstaged"] = unstaged

        return result

    def add(self, filename):
        """Add a file to a commit

        Args:
            filename(str): Filename to add. Should support `.` to add all files

        Returns:
            None
        """
        self.repo.index.add([filename])

    def remove(self, filename, force=False, keep_file=True):
        """Remove a file from tracking

        Args:
            filename(str): Filename to remove.
            force(bool): Force removal
            keep_file(bool): If true, don't delete the file (e.g. use the --cached flag)

        Returns:
            None
        """
        self.repo.index.remove([filename])

        if not keep_file:
            os.remove(filename)

        # TODO: DMK look into if force option is needed

    # todo diff branches
    @staticmethod
    def _parse_diff_strings(value):
        """Method to parse diff strings into chunks

        Args:
            value(str): Diff string from the diff command

        Returns:
            list((str, str)): a list of (line string, diff str)
        """
        value = str(value, 'utf-8')

        split_str = re.split('(@{2}\s-?\+?\d+,?\s?\d+\s-?\+?\d+,?\s?\d+\s@{2})', value)
        if len(split_str) == 1:
            split_value = value.split("@@")
            line_info = ["@@{}@@".format(split_value[1])]
            change_info = [split_value[2]]
        else:
            split_str = split_str[1:]
            line_info = split_str[::2]
            change_info = split_str[1::2]

        return [(x, y) for x, y in zip(line_info, change_info)]

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
        changes = self.repo.index.diff(None, paths=filename, create_patch=True,
                                       ignore_blank_lines=ignore_white_space,
                                       ignore_space_at_eol=ignore_white_space,
                                       diff_filter='cr')
        result = {}
        for change in changes:
            detail = self._parse_diff_strings(change.diff)
            if not change.b_path:
                result[change.a_path] = detail
            else:
                result[change.b_path] = detail

        return result

    def diff_staged(self, filename=None, ignore_white_space=True):
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
        changes = self.repo.index.diff("HEAD", paths=filename, create_patch=True,
                                       ignore_blank_lines=ignore_white_space,
                                       ignore_space_at_eol=ignore_white_space,
                                       diff_filter='cr', R=True)
        result = {}
        for change in changes:
            detail = self._parse_diff_strings(change.diff)
            if not change.b_path:
                result[change.a_path] = detail
            else:
                result[change.b_path] = detail

        return result

    def diff_commits(self, commit_a='HEAD~1', commit_b='HEAD', ignore_white_space=True):
        """Method to return the diff between two commits

        If params are omitted, it compares the current HEAD tree with the previous commit tree

        Returns a dictionary of the format:

            {
                "<filename>": [(<line_string>, <change_string>), ...],
                ...
            }

        Args:
            commit_a(str): Commit hash for the first commit, defaults to the previous commit
            commit_b(str): Commit hash for the second commit, defaults to the current HEAD
            ignore_white_space (bool): If True, ignore whitespace during diff. True if omitted

        Returns:
            dict
        """
        commit_obj = self.repo.commit(commit_a)

        changes = commit_obj.diff(commit_b, create_patch=True,
                                  ignore_blank_lines=ignore_white_space,
                                  ignore_space_at_eol=ignore_white_space,
                                  diff_filter='cr')
        result = {}
        for change in changes:
            detail = self._parse_diff_strings(change.diff)
            if not change.b_path:
                result[change.a_path] = detail
            else:
                result[change.b_path] = detail

        return result

    def commit(self, message, author=None, committer=None):
        """Method to perform a commit operation

        Args:
            message(str): Commit message
            author(GitAuthor): User info for the author, if omitted, assume the "system"
            committer(GitAuthor): User info for the committer. If omitted, set to the author

        Returns:
            None
        """
        if author:
            self.update_author(author, committer=committer)

        self.repo.index.commit(message, author=self.author, committer=self.committer)
    # LOCAL CHANGE METHODS

    # HISTORY METHODS
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
        kwargs = {"max_count": max_count}

        if filename:
            kwargs["paths"] = [filename]

        if skip:
            kwargs["skip"] = skip

        if since:
            kwargs["since"] = since.strftime("%B %d %Y")

        if author:
            kwargs["author"] = author

        commits = list(self.repo.iter_commits(self.get_current_branch_name(), **kwargs))

        result = []
        for c in commits:
            result.append({
                            "commit": c.hexsha,
                            "author":  {"name": c.author.name, "email": c.author.email},
                            "committer": {"name": c.committer.name, "email": c.committer.email},
                            "committed_on": c.committed_datetime,
                            "message": c.message
                          })

        return result

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
    def create_branch(self, name):
        """Method to create a new branch from the current HEAD

        Args:
            name(str): Name of the branch

        Returns:
            None
        """
        raise NotImplemented

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

    def rename_branch(self, old_name, new_name):
        """Method to rename a branch

        Args:
            old_name(str): The old branch name
            new_name(str): The new branch name

        Returns:
            None
        """
        raise NotImplemented

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

    def add_remote(self, name, url):
        """Method to add a new remote

        Args:
            name(str): Name of the remote
            url(str): URL to the remote

        Returns:
            None
        """

        raise NotImplemented

    def fetch(self):
        """Method to download objects and refs from a remote

        Returns:
            None
        """
        raise NotImplemented

    def pull(self):
        """Method fetch and integrate a remote

        Returns:
            None
        """
        raise NotImplemented

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
    def merge(self, branch_name):
        """Method to join a branch history with the current branch

        Args:
            branch_name(str): Name of the branch to merge into the current branch

        Returns:
            None
        """
        raise NotImplemented

    def abort_merge(self):
        """Method to abort a merge operation

        Returns:
            None
        """
        raise NotImplemented
    # MERGE METHODS

    # UNDO METHODS
    def discard_changes(self, filename=None):
        """Discard all changes, or changes in a single file.

        Args:
            filename(str): Optional filename. If omitted, all changes are discarded

        Returns:
            None
        """
        raise NotImplemented

    def revert(self, commit):
        """Revert changes into a new commit by replaying with appropriate changes

        Args:
            commit(str): Commit to revert to

        Returns:
            None
        """
        raise NotImplemented

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
    def add_submodule(self, repository, relative_path):
        """Method to add a submodule at the provided relative path to the repo root

        Args:
            repository(str): URL to the remote repository
            relative_path(str): Relative path from the repo root where the submodule should go

        Returns:
            None
        """
        raise NotImplemented

    def list_submodules(self):
        """Method to list submodules

            Should return a list of tuples with the format:

                [(name, commit), ...]

        Returns:
            list(tuple)
        """
        raise NotImplemented

    def init_submodules(self):
        """Method to init submodules

        Returns:
            None
        """
        raise NotImplemented

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
