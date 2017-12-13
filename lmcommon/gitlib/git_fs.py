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
from git import Repo, Head, RemoteReference
from git import InvalidGitRepositoryError, BadName
import os
import re
import shutil

from typing import Dict, List, Optional, Tuple

from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()


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
        """
        # Call super constructor
        GitRepoInterface.__init__(self, config_dict, author=author, committer=committer)

        # Set up the repository instance
        self.repo = None
        self.set_working_directory(self.config["working_directory"])

    def set_working_directory(self, directory):
        """Method to change the current working directory. Will reset the self.repo reference

        Args:
            directory(str): Absolute path to the working dir

        Returns:
            None
        """
        # Make sure you expand a user dir string
        directory = os.path.expanduser(directory)

        # Update the working dir
        self.working_directory = directory

        # Check to see if the working dir is already a repository
        try:
            self.repo = Repo(directory)
        except InvalidGitRepositoryError:
            # Make sure the working dir exists
            if not os.path.exists(directory):
                os.makedirs(directory)

            # Empty Dir
            self.repo = None

    @property
    def commit_hash(self):
        """Get the current commit hash

        Returns:
            str
        """
        return self.repo.head.object.hexsha

    @property
    def commit_hash_short(self):
        """Get the current commit hash, limit to 8 character

        Returns:
            str
        """
        return self.repo.head.object.hexsha[:8]

    @property
    def committed_on(self):
        """Get the datetime the commit occurred

        Returns:
            datetime.datetime
        """
        return self.repo.head.object.committed_datetime

    @property
    def git_path(self):
        """Get the full git path of the active branch

        Returns:
            str
        """
        return self.repo.active_branch.path

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

        logger.info("Initializing Git repository in {}".format(self.working_directory))
        self.repo = Repo.init(self.working_directory, bare=bare)

    def clone(self, source, directory: Optional[str] = None):
        """Clone a repo

        Args:
            source (str): Git ssh or https string to clone
            directory(str): Directory to clone into (optional argument)

        Returns:
            None
        """
        if self.repo:
            raise ValueError("Cannot init an existing git repository. Choose a different working directory")

        logger.info("Cloning Git repository from {} into {}".format(source, directory or self.working_directory))
        self.repo = Repo.clone_from(source, directory or self.working_directory)

    # LOCAL CHANGE METHODS
    def status(self) -> Dict[str, List[Tuple[str, str]]]:
        """Get the status of a repo

        Should return a dictionary of lists of tuples of the following format:

            {
                "staged": [(filename, status), ...],
                "unstaged": [(filename, status), ...],
                "untracked": [filename, ...]
            }

            status is the status of the file (new, modified, deleted)

        Returns:
            (dict(list))
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
            filename(str): Filename to add.

        Returns:
            None
        """
        logger.info("Adding file {} to Git repository in {}".format(filename, self.working_directory))
        self.repo.index.add([filename])

    def add_all(self, relative_directory=None):
        """Add all changes/files using the `git add -A` command

        Args:
            relative_directory(str): Relative directory (from the root_dir) to add everything

        Returns:
            None
        """
        if relative_directory:
            self.repo.git.add(os.path.join('.', relative_directory), A=True)
        else:
            self.repo.git.add(A=True)

    def remove(self, filename, force=False, keep_file=True):
        """Remove a file from tracking

        Args:
            filename(str): Filename to remove.
            force(bool): Force removal
            keep_file(bool): If true, don't delete the file (e.g. use the --cached flag)

        Returns:
            None
        """
        path_type = 'file' if os.path.isfile(filename) else 'directory'
        logger.info(f"Removing {path_type} {filename} from Git repo at {self.working_directory}")

        if os.path.isfile(filename):
            self.repo.index.remove([filename])
        else:
            # How to pass the -r to handle the directory.
            self.repo.index.remove([filename], **{'r': True})

        if not keep_file:
            if os.path.isfile(filename):
                os.remove(filename)
            else:
                shutil.rmtree(filename)

        # TODO: DMK look into if force option is needed

    @staticmethod
    def _parse_diff_strings(value):
        """Method to parse diff strings into chunks

        Args:
            value(bytes): Diff bytes from the diff command

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

    # TODO: Add support to diff branches
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
            git.Commit -- hash of new commit
        """

        if not message:
            raise ValueError("message cannot be None or empty")

        if author:
            self.update_author(author, committer=committer)

        logger.info("Committing changes to Git repo at {}".format(self.working_directory))
        return self.repo.index.commit(message, author=self.author, committer=self.committer)

    # HISTORY METHODS
    def log(self, path_info=None, max_count=None, filename=None, skip=None, since=None, author=None):
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
            path_info(str): Optional path info to filter (e.g., hash1, hash2..hash1, master)
            filename(str): Optional filename to filter on
            max_count(int): Optional number of commit records to return
            skip(int): Optional number of commit records to skip (supports building pagination)
            since(datetime.datetime): Optional *date* to limit on
            author(str): Optional filter based on author name

        Returns:
            list(dict)
        """
        kwargs = {}

        if max_count:
            kwargs["max_count"] = max_count

        if filename:
            kwargs["paths"] = [filename]

        if skip:
            kwargs["skip"] = skip

        if since:
            kwargs["since"] = since.strftime("%B %d %Y")

        if author:
            kwargs["author"] = author

        if path_info:
            commits = list(self.repo.iter_commits(path_info, **kwargs))
        else:
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

    def log_entry(self, commit):
        """Method to get single commit records

        Returns a single dictionary in format:

            {
                "commit": <commit hash (str)>,
                "author": {"name": <name (str)>, "email": <email (str)>},
                "committer": {"name": <name (str)>, "email": <email (str)>},
                "committed_on": <commit datetime (datetime.datetime)>,
                "message: <commit message (str)>
            }

        Args:
            commit(str): The commit hash for the log entry to get
    
        Returns:
            dict

        Raises:
            ValueError
        """
        if not commit:
            raise ValueError("commit cannot be None or empty")

        try:
            entry = self.repo.commit(commit)
        except BadName:
            logger.error("Commit hash {} not found: {}".format(commit, BadName))
            raise ValueError("Commit {} not found".format(commit))

        return {
                 "commit": entry.hexsha,
                 "author":  {"name": entry.author.name, "email": entry.author.email},
                 "committer": {"name": entry.committer.name, "email": entry.committer.email},
                 "committed_on": entry.committed_datetime,
                 "message": entry.message
               }

    def blame(self, filename):
        """Method to get the revision and author for each line of a file

        Returns an ordered list of dictionaries, one entry per change. Dictionary format:

            {
                "commit": <commit (str)>,
                "author": {"name": <name (str)>, "email": <email (str)>},
                "committed_on": <datetime (datetime)>,
                "message": <commit message (str)>
                "content": <content block (str)>
            }


        Args:
            filename(str): Filename to query

        Returns:
            list(dict)
        """
        blame_data = self.repo.blame('HEAD', filename)

        result = []
        for b in blame_data:
            result.append({
                            "commit": b[0].hexsha,
                            "author": {"name": b[0].author.name, "email": b[0].author.email},
                            "committed_on": b[0].committed_datetime,
                            "message": b[0].message,
                            "content": "\n".join(b[1])
                          })

        return result
    # HISTORY METHODS

    # BRANCH METHODS
    def create_branch(self, name):
        """Method to create a new branch from the current HEAD

        Args:
            name(str): Name of the branch

        Returns:
            None
        """
        branch_info_dict = self.list_branches()
        for key in branch_info_dict.keys():
            for n in branch_info_dict[key]:
                if name == n:
                    raise ValueError(f"Existing {key} branch `{n}` already exists")
        self.repo.create_head(name)

    def publish_branch(self, branch_name, remote_name="origin"):
        """Method to track a remote branch, check it out, and push

        Args:
            branch_name(str): Name of the branch
            remote_name(str): Name of the remote

        Returns:
            None
        """
        if branch_name not in self.repo.heads:
            raise ValueError("Branch `{}` not found.".format(branch_name))

        try:
            remote = self.repo.remotes[remote_name]
        except IndexError:
            raise ValueError("Remote `{}` not found.".format(remote_name))

        self.repo.heads[branch_name].checkout()
        remote.push(branch_name)

    def list_branches(self) -> Dict[str, List[str]]:
        """Method to list branches. Should return a dictionary of the format:

            {
                "local": [<name>, ...]
                "remote": [<name>, ...]
            }

            where local are branches currently available locally

        Returns:
            dict
        """
        local = []
        remote = []
        for ref in self.repo.refs:
            if type(ref) == Head:
                local.append(ref.name)
            elif type(ref) == RemoteReference:
                remote.append(ref.name)

        return {"local": local, "remote": remote}

    def delete_branch(self, name, delete_remote=False, remote="origin", force=False):
        """Method to delete a branch

        Args:
            name(str): Name of the branch to delete
            delete_remote(bool): If True, delete a remote branch
            remote(str): Name of remote to use with remote branches, defaults to "origin"
            force(bool): If True, force delete

        Returns:
            None
        """
        if name not in self.repo.heads:
            if delete_remote:
                if os.path.join(remote, name) not in [x.name for x in self.repo.refs]:
                    raise ValueError("Branch `{}` not found.".format(os.path.join(remote, name)))
                else:
                    name = os.path.join(remote, name)
            else:
                raise ValueError("Branch `{}` not found.".format(name))

        options = []
        if delete_remote:
            options.append("-r")
        if force:
            options.append("-f")

        if options:
            # Currently, using direct git interface to apply -dr option for remote branch deletion
            options.insert(0, "-d")
            options.append(name)
            self.repo.git.branch(*options)
        else:
            self.repo.delete_head(name)

    def rename_branch(self, old_name, new_name):
        """Method to rename a branch

        Args:
            old_name(str): The old branch name
            new_name(str): The new branch name

        Returns:
            None
        """
        if old_name not in self.repo.heads:
            raise ValueError("Branch `{}` not found.".format(old_name))

        self.repo.heads[old_name].rename(new_name)

    def checkout(self, branch_name: str, remote: str = "origin"):
        """Method to switch to a different branch

        Args:
            branch_name(str): Name of the branch to switch to
            remote(str): Remote to pull from
        Returns:
            None
        """
        if branch_name not in self.repo.heads:
            # Check if the branch exists in the remote and just hasn't been pulled yet
            if "{}/{}".format(remote, branch_name) not in self.repo.refs:
                raise ValueError("Branch `{}` not found.".format(branch_name))
            else:
                # Need to checkout the branch from the remote
                new_branch = self.repo.create_head(branch_name,
                                                   self.repo.remotes["origin"].refs[branch_name])
                self.repo.heads[branch_name].set_tracking_branch(self.repo.remotes["origin"].refs[branch_name])
                self.repo.heads[branch_name].checkout()
        else:
            self.repo.heads[branch_name].checkout()

        # Remove the checkout context id file if one exists
        checkout_id_file = os.path.join(self.working_directory, '.gigantum', '.checkout')
        if os.path.exists(checkout_id_file):
            os.remove(checkout_id_file)

    # BRANCH METHODS

    # TAG METHODS
    def create_tag(self, name, message):
        """Method to create a tag

        Args:
            name(str): Name of the tag
            message(str): Message with the tag

        Returns:
            None
        """
        self.repo.create_tag(name, message=message)

    def list_tags(self):
        """Method to list tags

        Returns:
            (list(dict)): list of dicts with `name` and `message` fields
        """
        return [{"name": x.tag.tag, "message": x.tag.message} for x in self.repo.tags]
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
        return [{"name": x.name, "url": list(x.urls)[0]} for x in self.repo.remotes]

    def add_remote(self, name, url, kwargs=None):
        """Method to add a new remote

        Args:
            name(str): Name of the remote
            url(str): Connection string to the remote
            kwargs(dict): Dictionary of kwargs to send to the git remote add command

        Returns:
            None
        """
        if not kwargs:
            kwargs = {}

        self.repo.create_remote(name, url, **kwargs)

    def remove_remote(self, name):
        """Method to remove a remote

        Args:
            name(str): Name of the remote

        Returns:
            None
        """
        found = False
        for r in self.repo.remotes:
            if r.name == name:
                r.remove(self.repo, name)
                found = True
                break

        if not found:
            raise ValueError("Remote not found.")

    def fetch(self, refspec=None, remote="origin"):
        """Method to download objects and refs from a remote

        Args:
            refspec(str): string describing the mapping between remote ref and local ref
            remote(str): name of remote, default to `origin`

        Returns:
            None
        """
        if len(self.repo.remotes) > 0:
            self.repo.remotes[remote].fetch(refspec)

    def pull(self, refspec=None, remote="origin"):
        """Method fetch and integrate a remote

        Args:
            refspec(str): string describing the mapping between remote ref and local ref
            remote(str): name of remote, default to `origin`

        Returns:
            None
        """
        self.repo.remotes[remote].pull(refspec=refspec)

    def push(self, remote_name="origin", refspec=None, tags=False):
        """Method update remote refs along with associated objects

        Args:
            remote_name(str): Name of the remote repository
            tags(bool): If true, push tags

        Returns:

        """
        return self.repo.remotes[remote_name].push(tags=tags)
    # REMOTE METHODS

    # MERGE METHODS
    def merge(self, branch_name):
        """Method to join a future branch history with the current branch

        Args:
            branch_name(str): Name of the FUTURE branch to merge into the current PAST branch

        Returns:
            None
        """
        if branch_name not in self.repo.heads:
            raise ValueError("Branch `{}` not found.".format(branch_name))

        # Get branch object for the right side. Should be future.
        future_branch = self.repo.heads[branch_name]

        # Get branch object for the left side. Should be behind the right side and be the current checked out branch.
        current_branch = self.repo.heads[self.get_current_branch_name()]

        # Get the merge base (where the two branches diverge)
        merge_base = self.repo.merge_base(current_branch, future_branch)

        logger.info("Merging changes from future branch {} into current branch {} in Git repo at {}".format(
            future_branch, current_branch, self.working_directory
        ))
        # Write merge to the index
        self.repo.index.merge_tree(future_branch, base=merge_base)

        # Commit
        self.repo.index.commit("Merged {} into {}".format(branch_name, self.get_current_branch_name()),
                               parent_commits=(current_branch.commit, future_branch.commit))

        # Now checkout latest commit
        current_branch.checkout(force=True)
    # MERGE METHODS

    # UNDO METHODS
    def discard_changes(self, filename=None):
        """Discard all changes, or changes in a single file.

        Args:
            filename(str): Optional filename. If omitted, all changes are discarded

        Returns:
            None
        """
        if filename:
            self.repo.index.checkout([filename], force=True)
        else:
            self.repo.index.checkout(force=True)
    # UNDO METHODS

    # SUBMODULE METHODS
    def add_submodule(self, name, relative_path, repository, branch=None):
        """Method to add a submodule at the provided relative path to the repo root and commit the change

        Args:
            name(str): Name for the submodule
            relative_path(str): Relative path from the repo root where the submodule should go
            repository(str): URL to the remote repository
            branch(str): If not None, the branch that should be used

        Returns:
            None
        """
        self.repo.create_submodule(name, relative_path, url=repository, branch=branch)
        self.repo.index.commit("Added submodule: {}".format(name))

    def list_submodules(self):
        """Method to list submodules

            Should return a list of dicts with the format:

                {
                    "name": <name of the submodule>,
                    "url": <url of repo>,
                    "branch": <name of the branch>
                }

        Returns:
            list(dict)
        """
        result = []
        for sub in self.repo.submodules:
            result.append({"name": sub.name,
                           "url": sub.url,
                           "branch": sub.branch_name})

        return result

    def update_submodules(self, init=True):
        """Method to update submodules and optionally init if needed

        Args:
            init(bool): Flag indicating if submodules should be initialized

        Returns:
            None
        """
        self.repo.submodule_update(init=init)

    def remove_submodules(self, submodule_name):
        """Method to remove submodule reference and delete the files

        submodule_path:
            submodule_name(str): Name of the submodule

        Returns:
            None
        """
        if submodule_name not in [x.name for x in self.repo.submodules]:
            raise ValueError("Submodule `{}` not found.".format(submodule_name))

        self.repo.submodules[submodule_name].remove(module=True, configuration=True)
        self.repo.index.commit("Removed submodule: {}".format(submodule_name))
