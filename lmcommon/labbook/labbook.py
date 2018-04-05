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
import glob
import os
import re
import shutil
from typing import (Any, Dict, List, Optional, Set, Tuple)
import uuid
import yaml
import json
import time
import datetime
import subprocess
from contextlib import contextmanager
from pkg_resources import resource_filename
import gitdb
from collections import OrderedDict

from lmcommon.configuration import Configuration, get_docker_client
from lmcommon.gitlib import get_git_interface, GitAuthor, GitRepoInterface
from lmcommon.logging import LMLogger
from lmcommon.labbook.schemas import validate_labbook_schema
from lmcommon.labbook import shims
from lmcommon.activity import ActivityStore, ActivityType, ActivityRecord, ActivityDetailType, ActivityDetailRecord
from lmcommon.labbook.schemas import CURRENT_SCHEMA

from redis import StrictRedis
import redis_lock


logger = LMLogger.get_logger()


class LabbookException(Exception):
    """Any Exception arising from inside the Labbook class will be cast as a LabbookException.

    This is to avoid having "except Exception" clauses in the client code, and to avoid
    having to be aware of every sub-library that is used by the Labbook and the exceptions that those raise.
    The principle idea behind this is to have a single catch for all Labbook-related errors. In the stack trace you
    can still observe the origin of the problem."""
    pass


class LabbookMergeException(LabbookException):
    """ Indicates failure of syncing with remote due to a merge conflict with local changes. """
    pass


def _check_git_tracked(repo: GitRepoInterface) -> None:
    """Validates that a Git repo is not leaving any uncommitted changes or files.
    Raises ValueError if it does."""

    try:
        # This is known to throw a ValueError if the repo is bare - i.e., does not yet
        # have any commits.
        # TODO - A better way to determine if the repo does not yet have any commits.
        # I tried a variety of ways and this try-catch-ValueError is the only thing that works.
        repo.commit_hash
    except ValueError as e:
        logger.info("Not checking Git status, appears to be uninitialized.")
        return

    result_status = repo.status()
    # status_key is one of "staged", "unstaged", "untracked"
    for status_key in result_status.keys():
        n = result_status.get(status_key)
        if n:
            errmsg = f"Found unexpected {status_key} files in repo {n} aborting."
            logger.error(errmsg)
            raise ValueError(errmsg)
            # TODO - Rollback, revert?


class LabBook(object):
    """Class representing a single LabBook"""

    def __init__(self, config_file: Optional[str] = None, author: Optional[GitAuthor] = None) -> None:
        self.labmanager_config = Configuration(config_file)

        # Create gitlib instance
        self.git = get_git_interface(self.labmanager_config.config["git"])

        # If author is set, update git interface
        if author:
            self.git.update_author(author=author)

        # LabBook Properties
        self._root_dir: Optional[str] = None  # The root dir is the location of the labbook this instance represents
        self._data: Optional[Dict[str, Any]] = None
        self._checkout_id: Optional[str] = None

        # LabBook Environment
        self._env = None

        # Redis instance for the LabBook lock
        self._lock_redis_client: Optional[StrictRedis] = None

        # Persisted Favorites data for more efficient file listing operations
        self._favorite_keys: Optional[Dict[str, Any]] = None

    def __str__(self):
        if self._root_dir:
            return f'<LabBook at `{self._root_dir}`>'
        else:
            return f'<LabBook UNINITIALIZED>'

    def _validate_git(method_ref): #type: ignore
        """Definition of decorator that validates git operations.

        Note! The approach here is taken from Stack Overflow answer https://stackoverflow.com/a/1263782
        """
        def __validator(self, *args, **kwargs):
            # Note, `create_activity_record` indicates whether this filesystem operation should be immediately
            # put into the Git history via an activity record. For now, if this is not true, then do not immediately
            # put this in the Git history. Generally, calls from within this class will set it to false (and do commits
            # later) and calls from outside will set create_activity_record to True.
            if kwargs.get('create_activity_record') is True:
                try:
                    _check_git_tracked(self.git)
                    n = method_ref(self, *args, **kwargs) #type: ignore
                except ValueError:
                    with self.lock_labbook():
                        self._sweep_uncommitted_changes()
                    n = method_ref(self, *args, **kwargs)  # type: ignore
                    with self.lock_labbook():
                        self._sweep_uncommitted_changes()
                finally:
                    _check_git_tracked(self.git)
            else:
                n = method_ref(self, *args, **kwargs)  # type: ignore
            return n
        return __validator

    @contextmanager
    def lock_labbook(self, lock_key: Optional[str] = None):
        """A context manager for locking labbook operations that is decorator compatible

        Manages the lock process along with catching and logging exceptions that may occur

        Args:
            lock_key(str): The lock key to override the default value.

        """
        lock: redis_lock.Lock = None
        try:
            config = self.labmanager_config.config['lock']

            # Get a redis client
            if not self._lock_redis_client:
                self._lock_redis_client = StrictRedis(host=config['redis']['host'],
                                                      port=config['redis']['port'],
                                                      db=config['redis']['db'])

            # Create a lock key
            if not lock_key:
                lock_key = f'filesystem_lock|{self.key}'

            # Get a lock object
            lock = redis_lock.Lock(self._lock_redis_client, lock_key,
                                   expire=config['expire'],
                                   auto_renewal=config['auto_renewal'],
                                   strict=config['redis']['strict'])

            # Get the lock
            if lock.acquire(timeout=config['timeout']):
                # Do the work
                start_time = time.time()
                yield
                if config['expire']:
                    if (time.time() - start_time) > config['expire']:
                        logger.warning(
                            f"LabBook task took more than {config['expire']}s. File locking possibly invalid.")
            else:
                raise IOError(f"Could not acquire LabBook lock within {config['timeout']} seconds.")

        except Exception as e:
            logger.error(e)
            raise
        finally:
            # Release the Lock
            if lock:
                try:
                    lock.release()
                except redis_lock.NotAcquired as e:
                    # if you didn't get the lock and an error occurs, you probably won't be able to release, so log.
                    logger.error(e)

    @property
    def root_dir(self) -> str:
        if not self._root_dir:
            raise ValueError("No lab book root dir specified. Could not get root dir")
        return self._root_dir

    @property
    def data(self) -> Optional[Dict[str, Any]]:
        return self._data

    @property
    def id(self) -> str:
        if self._data:
            return self._data["labbook"]["id"]
        else:
            raise ValueError("No ID assigned to Lab Book.")

    @property
    def name(self) -> str:
        if self._data:
            return self._data["labbook"]["name"]
        else:
            raise ValueError("No name assigned to Lab Book.")

    @name.setter
    def name(self, value: str) -> None:
        if not value:
            raise ValueError("value cannot be None or empty")

        if not self._data:
            self._data = {'labbook': {'name': value}}
        else:
            self._data["labbook"]["name"] = value
        self._validate_labbook_data()

        # Update data file
        self._save_labbook_data()

        # Rename directory
        if self._root_dir:
            base_dir, _ = self._root_dir.rsplit(os.path.sep, 1)
            os.rename(self._root_dir, os.path.join(base_dir, value))
        else:
            raise ValueError("Lab Book root dir not specified. Failed to configure git.")

        # Update the root directory to the new directory name
        self._set_root_dir(os.path.join(base_dir, value))

    @property
    def schema(self) -> int:
        if self._data:
            return self._data["schema"]
        else:
            raise ValueError("No schema stored in LabBook data.")

    @property
    def key(self) -> str:
        """Return a unique key for identifying and locating a labbbok.

        Note: A labbook does not exist notionally outside of a directory structure, therefore
        part of the key is determined by this structure. """

        dir_elements = self.root_dir.split(os.sep)
        return "|".join([dir_elements[-4], dir_elements[-3], dir_elements[-1]])

    @property
    def active_branch(self) -> str:
        return self.git.get_current_branch_name()

    @property
    def description(self) -> str:
        if self._data:
            return self._data["labbook"]["description"]
        else:
            raise ValueError("No description assigned to Lab Book.")

    @description.setter
    def description(self, value) -> None:
        value = self._santize_input(value)
        if not self._data:
            self._data = {'labbook': {'description': value}}
        else:
            self._data["labbook"]["description"] = value

        self._save_labbook_data()

    @property
    def owner(self) -> Dict[str, str]:
        if self._data:
            return self._data["owner"]
        else:
            raise ValueError("No owner assigned to Lab Book.")

    @staticmethod
    def _make_path_relative(path_str: str) -> str:
        while len(path_str or '') >= 1 and path_str[0] == os.path.sep:
            path_str = path_str[1:]
        return path_str

    @property
    def checkout_id(self) -> str:
        """Property that provides a unique ID for a checkout. This is used in the activity feed database to ensure
        parallel work in the same branch will merge safely

        Returns:
            str
        """
        if self._checkout_id:
            return self._checkout_id
        else:
            # Try to load checkout ID from disk
            checkout_file = os.path.join(self.root_dir, '.gigantum', '.checkout')
            if os.path.exists(checkout_file):
                # Load from disk
                with open(checkout_file, 'rt') as cf:
                    self._checkout_id = cf.read()
            else:
                # Create a new checkout ID and file
                self._checkout_id = f"{self.key}|{self.git.get_current_branch_name()}|{uuid.uuid4().hex[0:10]}"
                self._checkout_id = self._checkout_id.replace('|', '-')
                with open(checkout_file, 'wt') as cf:
                    cf.write(self._checkout_id)

                # Log new checkout ID creation
                logger.info(f"Created new checkout context ID {self._checkout_id}")
            return self._checkout_id

    @property
    def favorite_keys(self) -> Dict[str, List[Optional[str]]]:
        """Property that provides cached favorite data for file listing operations

        Returns:
            dict
        """
        if not self._favorite_keys:
            data: Dict[str, list] = dict()
            for section in ['code', 'input', 'output']:
                data[section] = list(self.get_favorites(section).keys())

            self._favorite_keys = data

        return self._favorite_keys

    @property
    def has_remote(self):
        """Return True if the Labbook has a remote that it can push/pull to/from

        Returns:
            bool indicating whether a remote is set.
        """
        try:
            return len(self.git.list_remotes()) > 0
        except Exception as e:
            logger.exception(e)
            raise LabbookException(e)

    @property
    def remote(self) -> Optional[str]:
        try:
            r = self.git.list_remotes()
            if r:
                return r[0]['url']
            else:
                return None
        except Exception as e:
            logger.exception(e)
            raise LabbookException(e)

    @property
    def creation_date(self) -> Optional[datetime.datetime]:
        path = os.path.join(self.root_dir, '.gigantum', 'buildinfo')
        if os.path.isfile(path):
            with open(path) as p:
                info = json.load(p)
                date_str = info.get('creation_utc')
                d = datetime.datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S.%f')
                return d
        else:
            return None

    @property
    def build_details(self) -> Optional[Dict[str, str]]:
        path = os.path.join(self.root_dir, '.gigantum', 'buildinfo')
        if os.path.isfile(path):
            with open(path) as p:
                info = json.load(p)
                return info.get('build_info')
        else:
            return None

    def _set_root_dir(self, new_root_dir: str) -> None:
        """Update the root directory and also reconfigure the git instance

        Returns:
            None
        """
        # Be sure to expand in case a user dir string is used
        self._root_dir = os.path.expanduser(new_root_dir)

        # Update the git working directory
        self.git.set_working_directory(self.root_dir)

    def _save_labbook_data(self) -> None:
        """Method to save changes to the LabBook

        Returns:
            None
        """
        if not self.root_dir:
            raise ValueError("No root directory assigned to lab book. Failed to get root directory.")

        with self.lock_labbook():
            with open(os.path.join(self.root_dir, ".gigantum", "labbook.yaml"), 'wt') as lbfile:
                lbfile.write(yaml.dump(self._data, default_flow_style=False))
                lbfile.flush()

    def _load_labbook_data(self) -> None:
        """Method to load the labbook YAML file to a dictionary

        Returns:
            None
        """
        if not self.root_dir:
            raise ValueError("No root directory assigned to lab book. Failed to get root directory.")

        with open(os.path.join(self.root_dir, ".gigantum", "labbook.yaml"), 'rt') as lbfile:
            self._data = yaml.load(lbfile)

    def _validate_labbook_data(self) -> None:
        """Method to validate the LabBook data file contents

        Returns:
            None
        """
        if not re.match("^(?!-)(?!.*--)[a-z0-9-]+(?<!-)$", self.name):
            raise ValueError("Invalid `name`. Only a-z 0-9 and hyphens allowed. No leading or trailing hyphens.")

        if len(self.name) > 100:
            raise ValueError("Invalid `name`. Max length is 100 characters")

        # Validate schema is supported by running version of the software and valid
        if not validate_labbook_schema(self.schema, self.data):
            errmsg = f"Schema in Labbook {str(self)} does not match indicated version {self.schema}"
            logger.error(errmsg)
            raise ValueError(errmsg)

    def _validate_section(self, section: str) -> None:
        """Simple method to validate a user provided section name

        Args:
            section(str): Name of a LabBook section

        Returns:
            None
        """
        if section not in ['code', 'input', 'output']:
            raise ValueError("section (code, input, output) must be provided.")

    # TODO: Get feedback on better way to sanitize
    def _santize_input(self, value: str) -> str:
        """Simple method to sanitize a user provided value with characters that can be bad

        Args:
            value(str): Input string

        Returns:
            str: Output string
        """
        return ''.join(c for c in value if c not in '\<>?/;"`\'')

    def _sweep_uncommitted_changes(self) -> None:
        if not self.is_repo_clean:
            logger.warning('Untracked changes detected; calling sweep;')
            r = subprocess.check_output(f'git add -A && git commit -m "_sweep_uncommitted_changes"',
                                        cwd=self.root_dir, shell=True)
            #self.git.add_all()
            #self.git.commit("Sweeping up lingering changes.")
        else:
            logger.info(f"{str(self)} no changes to sweep.")

        if not self.is_repo_clean:
            raise LabbookException("_sweep_uncommitted_changes failed")

    @staticmethod
    def get_activity_type_from_section(section_name: str) -> Tuple[ActivityType, ActivityDetailType, str]:
        """Method to get activity and detail types from the section name

        Args:
            section_name(str): section subdirectory/identifier (code, input, output)

        Returns:
            tuple
        """
        if section_name == 'code':
            activity_detail_type = ActivityDetailType.CODE
            activity_type = ActivityType.CODE
            section = "Code"
        elif section_name == 'input':
            activity_detail_type = ActivityDetailType.INPUT_DATA
            activity_type = ActivityType.INPUT_DATA
            section = "Input Data"
        elif section_name == 'output':
            activity_detail_type = ActivityDetailType.OUTPUT_DATA
            activity_type = ActivityType.OUTPUT_DATA
            section = "Output Data"
        else:
            # This is the labbook root, since we can't catagorize keep generic
            activity_detail_type = ActivityDetailType.LABBOOK
            activity_type = ActivityType.LABBOOK
            section = "LabBook Root"

        return activity_type, activity_detail_type, section

    @staticmethod
    def infer_section_from_relative_path(relative_path: str) -> Tuple[ActivityType, ActivityDetailType, str]:
        """Method to try to infer the "section" from a relative file path

        Args:
            relative_path(str): a relative file path within a LabBook section (code, input, output)

        Returns:
            tuple
        """
        # If leading slash, remove it first
        if relative_path[0] == os.path.sep:
            relative_path = relative_path[1:]

        # if no trailing slash add it. simple parsing below assumes no trailing and a leading slash to work.
        if relative_path[-1] != os.path.sep:
            relative_path = relative_path + os.path.sep

        possible_section, _ = relative_path.split('/', 1)
        return LabBook.get_activity_type_from_section(possible_section)

    def get_file_info(self, section: str, rel_file_path: str) -> Dict[str, Any]:
        """Method to get a file's detail information

        Args:
            rel_file_path(str): The relative file path to generate info from
            section(str): The section name (code, input, output)

        Returns:
            dict
        """
        # remove leading separators if one exists.
        rel_file_path = rel_file_path[1:] if rel_file_path[0] == os.path.sep else rel_file_path
        full_path = os.path.join(self.root_dir, section, rel_file_path)

        file_info = os.stat(full_path)
        is_dir = os.path.isdir(full_path)

        # If it's a directory, add a trailing slash so UI renders properly
        if is_dir:
            if rel_file_path[-1] != os.path.sep:
                rel_file_path = f"{rel_file_path}{os.path.sep}"

        return {
                  'key': rel_file_path,
                  'is_dir': is_dir,
                  'size': file_info.st_size if not is_dir else 0,
                  'modified_at': file_info.st_mtime,
                  'is_favorite': rel_file_path in self.favorite_keys[section]
               }

    @property
    def is_repo_clean(self) -> bool:
        """Return true if the Git repo is ready to be push, pulled, or merged. I.e., no uncommitted changes
        or un-tracked files. """

        try:
            result_status = self.git.status()
            for status_key in result_status.keys():
                n = result_status.get(status_key)
                if n:
                    logger.warning(f"Found {status_key} in {str(self)}: {n}")
                    return False
            return True
        except gitdb.exc.BadName:
            return False

    def checkout_branch(self, branch_name: str, new: bool = False) -> None:
        """
        Checkout a Git branch. Create a new branch locally.

        Args:
            branch_name(str): Name of branch to checkout or create
            new(bool): Indicates this branch should be created.

        Return:
            None
        """
        if not self.is_repo_clean:
            raise LabbookException(f"Cannot checkout {branch_name}: Untracked and/or uncommitted changes")

        try:
            if new:
                logger.info(f"Creating a new branch {branch_name}...")
                self.git.create_branch(branch_name)
            logger.info(f"Checking out branch {branch_name}...")
            self.git.checkout(branch_name=branch_name)

            # Clear out checkout context
            if self._root_dir and os.path.exists(os.path.join(self._root_dir, ".gigantum", ".checkout")):
                os.remove(os.path.join(self._root_dir, ".gigantum", ".checkout"))
            self._checkout_id = None
        except ValueError as e:
            logger.error(f"Cannot checkout branch {branch_name}: {e}")
            raise LabbookException(e)

    def get_commits_behind_remote(self, remote_name: str = "origin") -> Tuple[str, int]:
        """Return the number of commits local branch is behind remote. Note, only works with
        currently checked-out branch.

        Args:
            remote_name: Name of remote, e.g., "origin"

        Returns:
            tuple containing branch name, and number of commits behind (zero implies up-to-date)
        """
        try:
            if remote_name in [n['name'] for n in self.git.list_remotes()]:
                self.git.fetch(remote=remote_name)
            result_str = self.git.repo.git.status().replace('\n', ' ')
        except Exception as e:
            logger.exception(e)
            raise LabbookException(e)

        logger.info(f"Checking state of branch {self.active_branch}: {result_str}")

        if 'branch is up-to-date' in result_str:
            return self.active_branch, 0
        elif 'branch is behind' in result_str:
            m = re.search(' by ([\d]+) commit', result_str)
            if m:
                assert int(m.groups()[0]) > 0
                return self.active_branch, int(m.groups()[0])
            else:
                logger.error("Could not find count in: {result_str}")
                raise LabbookException("Unable to determine commit behind-count")
        else:
            # This branch is local-only
            return self.active_branch, 0

    def add_remote(self, remote_name: str, url: str):
        """Add a new git remote

        Args:
            remote_name: Name of remote, e.g., "origin"
            url: Path to remote Git repository.
        """

        try:
            logger.info(f"Adding new remote {remote_name} at {url}")
            self.git.add_remote(remote_name, url)
            self.git.fetch(remote=remote_name)
        except Exception as e:
            # Unsure what specific exception add_remote creates, so make a catchall.
            logger.exception(e)
            raise LabbookException(e)

    def get_branches(self) -> Dict[str, List[str]]:
        """Return all branches a Dict of Lists. Dict contains two keys "local" and "remote".

        Args:
            None

        Returns:
            Dictionary of lists for "remote" and "local" branches.
        """

        try:
            logger.debug(f"Getting branches for {str(self)}")
            self.git.fetch()
            return self.git.list_branches()
        except Exception as e:
            # Unsure what specific exception add_remote creates, so make a catchall.
            logger.exception(e)
            raise LabbookException(e)


    @_validate_git
    def insert_file(self, section: str, src_file: str, dst_dir: str,
                    base_filename: Optional[str] = None) -> Dict[str, Any]:
        """Copy the file at `src_file` into the `dst_dir`. Filename removes upload ID if present.

        Args:
            section(str): Section name (code, input, output)
            src_file(str): Full path of file to insert into
            dst_dir(str): Relative path within labbook where `src_file` should be copied to
            base_filename(str): The desired basename for the file, without an upload ID prepended

        Returns:
            dict: The inserted file's info
        """
        self._validate_section(section)

        if not os.path.abspath(src_file):
            raise ValueError(f"Source file `{src_file}` is not an absolute path")

        if not os.path.isfile(src_file):
            raise ValueError(f"Source file does not exist at `{src_file}`")

        with self.lock_labbook():
            # Remove any leading "/" -- without doing so os.path.join will break.
            dst_dir = LabBook._make_path_relative(os.path.join(section, dst_dir))

            # Check if this file contains an upload_id (which means it came from a chunked upload)
            if base_filename:
                dst_filename = base_filename
            else:
                dst_filename = os.path.basename(src_file)

            # Create the absolute file path for the destination
            dst_path = os.path.join(self.root_dir, dst_dir.replace('..', ''), dst_filename)
            if not os.path.isdir(os.path.join(self.root_dir, dst_dir.replace('..', ''))):
                raise ValueError(f"Target dir `{os.path.join(self.root_dir, dst_dir.replace('..', ''))}` does not exist")

            # Copy file to destination
            rel_path = dst_path.replace(os.path.join(self.root_dir, section), '')
            logger.info(f"Inserting new file for {str(self)} from `{src_file}` to `{dst_path}")
            shutil.copyfile(src_file, dst_path)

            if not shims.in_untracked(self.root_dir, section):
                # If we are setting this section to be untracked
                activity_type, activity_detail_type, section_str = self.get_activity_type_from_section(section)

                # Create commit
                commit_msg = f"Added new {section_str} file {rel_path}"
                self.git.add(dst_path)
                commit = self.git.commit(commit_msg)

                # Create Activity record and detail
                _, ext = os.path.splitext(rel_path) or 'file'

                # Create detail record
                adr = ActivityDetailRecord(activity_detail_type, show=False, importance=0)
                adr.add_value('text/plain', commit_msg)

                # Create activity record
                ar = ActivityRecord(activity_type,
                                    message=commit_msg,
                                    show=True,
                                    importance=255,
                                    linked_commit=commit.hexsha,
                                    tags=[ext])
                ar.add_detail_object(adr)

                # Store
                ars = ActivityStore(self)
                ars.create_activity_record(ar)

            return self.get_file_info(section, rel_path)

    @_validate_git
    def delete_file(self, section: str, relative_path: str, directory: bool = False) -> bool:
        """Delete file (or directory) from inside lb section.


        Part of the intention is to mirror the unix "rm" command. Thus, there
        needs to be some extra arguments in order to delete a directory, especially
        one with contents inside of it. In this case, `directory` must be true in order
        to delete a directory at the given path.

        Args:
            section(str): Section name (code, input, output)
            relative_path(str): Relative path from labbook root to target
            directory(bool): True if relative_path is a directory

        Returns:
            None
        """
        self._validate_section(section)
        with self.lock_labbook():
            relative_path = LabBook._make_path_relative(relative_path)
            target_path = os.path.join(self.root_dir, section, relative_path)
            if not os.path.exists(target_path):
                raise ValueError(f"Attempted to delete non-existent path at `{target_path}`")
            else:
                target_type = 'file' if os.path.isfile(target_path) else 'directory'
                logger.info(f"Removing {target_type} at `{target_path}`")
                if os.path.isdir(target_path):
                    if directory:
                        shutil.rmtree(target_path)
                    else:
                        errmsg = f"Cannot recursively remove directory unless `directory` arg is True"
                        logger.error(errmsg)
                        raise ValueError(errmsg)
                elif os.path.isfile(target_path):
                    os.remove(target_path)
                else:
                    errmsg = f"File at {target_path} neither file nor directory"
                    logger.error(errmsg)
                    raise ValueError(errmsg)

                if shims.in_untracked(self.root_dir, section=section):
                    return True

                commit_msg = f"Removed {target_type} {relative_path}."
                self.git.remove(target_path)
                commit = self.git.commit(commit_msg)
                if os.path.isfile(target_path):
                    _, ext = os.path.splitext(target_path)
                else:
                    ext = 'directory'

                # Get LabBook section
                activity_type, activity_detail_type, section_str = self.get_activity_type_from_section(section)

                # Create detail record
                adr = ActivityDetailRecord(activity_detail_type, show=False, importance=0)
                adr.add_value('text/plain', commit_msg)

                # Create activity record
                ar = ActivityRecord(activity_type,
                                    message=commit_msg,
                                    linked_commit=commit.hexsha,
                                    show=True,
                                    importance=255,
                                    tags=[ext])
                ar.add_detail_object(adr)

                # Store
                ars = ActivityStore(self)
                ars.create_activity_record(ar)

                return True

    @_validate_git
    def move_file(self, section: str, src_rel_path: str, dst_rel_path: str) -> Dict[str, Any]:

        """Move a file or directory within a labbook, but not outside of it. Wraps
        underlying "mv" call.

        Args:
            section(str): Section name (code, input, output)
            src_rel_path(str): Source file or directory
            dst_rel_path(str): Target file name and/or directory
        """
        self._validate_section(section)
        # Start with Validations
        if not src_rel_path:
            raise ValueError("src_rel_path cannot be None or empty")

        if not dst_rel_path:
            raise ValueError("dst_rel_path cannot be None or empty")

        is_untracked = shims.in_untracked(self.root_dir, section)
        with self.lock_labbook():
            src_rel_path = LabBook._make_path_relative(src_rel_path)
            dst_rel_path = LabBook._make_path_relative(dst_rel_path)

            src_abs_path = os.path.join(self.root_dir, section, src_rel_path.replace('..', ''))
            dst_abs_path = os.path.join(self.root_dir, section, dst_rel_path.replace('..', ''))

            if not os.path.exists(src_abs_path):
                raise ValueError(f"No src file exists at `{src_abs_path}`")

            try:
                src_type = 'directory' if os.path.isdir(src_abs_path) else 'file'
                logger.info(f"Moving {src_type} `{src_abs_path}` to `{dst_abs_path}`")

                if not is_untracked:
                    self.git.remove(src_abs_path, keep_file=True)

                shutil.move(src_abs_path, dst_abs_path)

                if not is_untracked:
                    commit_msg = f"Moved {src_type} `{src_rel_path}` to `{dst_rel_path}`"

                    if os.path.isdir(dst_abs_path):
                        self.git.add_all(dst_abs_path)
                    else:
                        self.git.add(dst_abs_path)

                    commit = self.git.commit(commit_msg)

                    # Get LabBook section
                    activity_type, activity_detail_type, section_str = self.get_activity_type_from_section(section)

                    # Create detail record
                    adr = ActivityDetailRecord(activity_detail_type, show=False, importance=0)
                    adr.add_value('text/markdown', commit_msg)

                    # Create activity record
                    ar = ActivityRecord(activity_type,
                                        message=commit_msg,
                                        linked_commit=commit.hexsha,
                                        show=True,
                                        importance=255,
                                        tags=['file-move'])
                    ar.add_detail_object(adr)

                    # Store
                    ars = ActivityStore(self)
                    ars.create_activity_record(ar)

                return self.get_file_info(section, dst_rel_path)
            except Exception as e:
                logger.critical("Failed moving file in labbook. Repository may be in corrupted state.")
                logger.exception(e)
                raise

    @_validate_git
    def makedir(self, relative_path: str, make_parents: bool = True, create_activity_record: bool = False) -> None:
        """Make a new directory inside the labbook directory.

        Args:
            relative_path(str): Path within the labbook to make directory
            make_parents(bool): If true, create intermediary directories
            create_activity_record(bool): If true, create commit and activity record

        Returns:
            str: Absolute path of new directory
        """
        if not relative_path:
            raise ValueError("relative_path argument cannot be None or empty")

        with self.lock_labbook():
            relative_path = LabBook._make_path_relative(relative_path)
            new_directory_path = os.path.join(self.root_dir, relative_path)
            section = relative_path.split(os.sep)[0]
            git_untracked = shims.in_untracked(self.root_dir, section)
            if os.path.exists(new_directory_path):
                #raise ValueError(f'Directory `{new_directory_path}` already exists')
                return
            else:
                logger.info(f"Making new directory in `{new_directory_path}`")
                os.makedirs(new_directory_path, exist_ok=make_parents)
                if git_untracked:
                    logger.warning(f'New {str(self)} untracked directory `{new_directory_path}`')
                    return
                new_dir = ''
                for d in relative_path.split(os.sep):
                    new_dir = os.path.join(new_dir, d)
                    full_new_dir = os.path.join(self.root_dir, new_dir)

                    gitkeep_path = os.path.join(full_new_dir, '.gitkeep')
                    if not os.path.exists(gitkeep_path):
                        with open(gitkeep_path, 'w') as gitkeep:
                            gitkeep.write("This file is necessary to keep this directory tracked by Git"
                                          " and archivable by compression tools. Do not delete or modify!")
                        self.git.add(gitkeep_path)

                if create_activity_record:
                    # Create detail record
                    activity_type, activity_detail_type, section_str = self.infer_section_from_relative_path(relative_path)
                    adr = ActivityDetailRecord(activity_detail_type, show=False, importance=0)

                    msg = f"Created new {section_str} directory `{relative_path}`"
                    commit = self.git.commit(msg)
                    adr.add_value('text/markdown', msg)

                    # Create activity record
                    ar = ActivityRecord(activity_type,
                                        message=msg,
                                        linked_commit=commit.hexsha,
                                        show=True,
                                        importance=255,
                                        tags=['directory-create'])
                    ar.add_detail_object(adr)

                    # Store
                    ars = ActivityStore(self)
                    ars.create_activity_record(ar)

    def walkdir(self, section: str, show_hidden: bool = False) -> List[Dict[str, Any]]:
        """Return a list of all files and directories in a section of the labbook. Never includes the .git or
         .gigantum directory.

        Args:
            section(str): The labbook section (code, input, output) to walk
            show_hidden(bool): If True, include hidden directories (EXCLUDING .git and .gigantum)

        Returns:
            List[Dict[str, str]]: List of dictionaries containing file and directory metadata
        """
        self._validate_section(section)

        keys: List[str] = list()
        # base_dir is the root directory to search, to account for relative paths inside labbook.
        base_dir = os.path.join(self.root_dir, section)
        if not os.path.isdir(base_dir):
            raise ValueError(f"Labbook walkdir base_dir {base_dir} not an existing directory")

        for root, dirs, files in os.walk(base_dir):
            # Remove directories we ignore so os.walk does not traverse into them during future iterations
            if '.git' in dirs:
                del dirs[dirs.index('.git')]
            if '.gigantum' in dirs:
                del dirs[dirs.index('.gigantum')]

            # For more deterministic responses, sort resulting paths alphabetically.
            # Store directories then files, so pagination loads things in an intuitive order
            dirs.sort()
            keys.extend(sorted([os.path.join(root.replace(base_dir, ''), d) for d in dirs]))
            keys.extend(sorted([os.path.join(root.replace(base_dir, ''), f) for f in files]))

        # Create stats
        stats: List[Dict[str, Any]] = list()
        for f_p in keys:
            if not show_hidden and any([len(p) and p[0] == '.' for p in f_p.split(os.path.sep)]):
                continue
            stats.append(self.get_file_info(section, f_p))

        return stats

    def listdir(self, section: str, base_path: Optional[str] = None, show_hidden: bool = False) -> List[Dict[str, Any]]:
        """Return a list of all files and directories in a directory. Never includes the .git or
         .gigantum directory.

        Args:
            section(str): the labbook section to start from
            base_path(str): Relative base path, if not listing from labbook's root.
            show_hidden(bool): If True, include hidden directories (EXCLUDING .git and .gigantum)

        Returns:
            List[Dict[str, str]]: List of dictionaries containing file and directory metadata
        """
        self._validate_section(section)
        # base_dir is the root directory to search, to account for relative paths inside labbook.
        base_dir = os.path.join(self.root_dir, section, base_path or '')
        if not os.path.isdir(base_dir):
            raise ValueError(f"Labbook listdir base_dir {base_dir} not an existing directory")

        stats: List[Dict[str, Any]] = list()
        for item in os.listdir(base_dir):
            if item in ['.git', '.gigantum']:
                # Never include .git or .gigantum
                continue

            if not show_hidden and any([len(p) and p[0] == '.' for p in item.split('/')]):
                continue

            # Create tuple (isDir, key)
            stats.append(self.get_file_info(section, os.path.join(base_path or "", item)))

        # For more deterministic responses, sort resulting paths alphabetically.
        return sorted(stats, key=lambda a: a['key'])

    def create_favorite(self, section: str, relative_path: str,
                        description: Optional[str] = None, is_dir: bool = False) -> Dict[str, Any]:
        """Mark an existing file as a Favorite

        Data is stored in a json document, with each object name the relative path to the file

        Args:
            section(str): lab book subdir where file exists (code, input, output)
            relative_path(str): Relative path within the section to the file to favorite
            description(str): A short string containing information about the favorite
            is_dir(bool): If true, relative_path will expected to be a directory

        Returns:
            dict
        """
        if section not in ['code', 'input', 'output']:
            raise ValueError("Favorites only supported in `code`, `input`, and `output` Lab Book directories")

        with self.lock_labbook():
            # Generate desired absolute path
            target_path_rel = os.path.join(section, relative_path)

            # Remove any leading "/" -- without doing so os.path.join will break.
            target_path_rel = LabBook._make_path_relative(target_path_rel)
            target_path = os.path.join(self.root_dir, target_path_rel.replace('..', ''))

            if not os.path.exists(target_path):
                raise ValueError(f"Target file/dir `{target_path}` does not exist")

            if is_dir != os.path.isdir(target_path):
                raise ValueError(f"Target `{target_path}` a directory")

            logger.info(f"Marking {target_path} as favorite")

            # Open existing Favorites json if exists
            favorites_dir = os.path.join(self.root_dir, '.gigantum', 'favorites')
            if not os.path.exists(favorites_dir):
                # No favorites have been created
                os.makedirs(favorites_dir)

            favorite_data: Dict[str, Any] = dict()
            if os.path.exists(os.path.join(favorites_dir, f'{section}.json')):
                # Read existing data
                with open(os.path.join(favorites_dir, f'{section}.json'), 'rt') as f_data:
                    favorite_data = json.load(f_data)

            # Ensure the key has a trailing slash if a directory to meet convention
            if is_dir:
                if relative_path[-1] != os.path.sep:
                    relative_path = relative_path + os.path.sep

            if relative_path in favorite_data:
                raise ValueError(f"Favorite `{relative_path}` already exists in {section}.")

            # Get last index
            if favorite_data:
                last_index = max([int(favorite_data[x]['index']) for x in favorite_data])
                index_val = last_index + 1
            else:
                index_val = 0

            # Create new record
            favorite_data[relative_path] = {"key": relative_path,
                                            "index": index_val,
                                            "description": description,
                                            "is_dir": is_dir}

            # Always be sure to sort the ordered dict
            favorite_data = OrderedDict(sorted(favorite_data.items(), key=lambda val: val[1]['index']))

            # Write favorites to lab book
            fav_data_file = os.path.join(favorites_dir, f'{section}.json')
            with open(fav_data_file, 'wt') as f_data:
                json.dump(favorite_data, f_data, indent=2)

            # Remove cached favorite key data
            self._favorite_keys = None

            # Commit the changes
            self.git.add(fav_data_file)
            self.git.commit(f"Committing new Favorite file {fav_data_file}")

            return favorite_data[relative_path]

    def update_favorite(self, section: str, relative_path: str,
                        new_description: Optional[str] = None,
                        new_index: Optional[int] = None) -> Dict[str, Any]:
        """Mark an existing file as a Favorite

        Args:
            section(str): lab book subdir where file exists (code, input, output)
            relative_path(str): Relative path within the section to the file to favorite
            new_description(str): A short string containing information about the favorite
            new_index(int): The position to move the favorite

        Returns:
            dict
        """
        if section not in ['code', 'input', 'output']:
            raise ValueError("Favorites only supported in `code`, `input`, and `output` Lab Book directories")

        with self.lock_labbook():
            # Open existing Favorites json
            favorites_file = os.path.join(self.root_dir, '.gigantum', 'favorites', f'{section}.json')
            if not os.path.exists(favorites_file):
                # No favorites have been created
                raise ValueError(f"No favorites exist in '{section}'. Create a favorite before trying to update")

            # Read existing data
            with open(favorites_file, 'rt') as f_data:
                favorite_data = json.load(f_data)

            # Ensure the favorite already exists is valid
            if relative_path not in favorite_data:
                raise ValueError(f"Favorite {relative_path} in section {section} does not exist. Cannot update.")

            # Update description if needed
            if new_description:
                logger.info(f"Updating description for {relative_path} favorite in section {section}.")
                favorite_data[relative_path]['description'] = new_description

            # Update the index if needed
            if new_index is not None:
                if new_index < 0 or new_index > len(favorite_data.keys()) - 1:
                    raise ValueError(f"Invalid index during favorite update: {new_index}")

                if new_index < favorite_data[relative_path]['index']:
                    # Increment index of all items "after" updated index
                    for fav in favorite_data:
                        if favorite_data[fav]['index'] >= new_index:
                            favorite_data[fav]['index'] = favorite_data[fav]['index'] + 1

                elif new_index > favorite_data[relative_path]['index']:
                    # Decrement index of all items "before" updated index
                    for fav in favorite_data:
                        if favorite_data[fav]['index'] <= new_index:
                            favorite_data[fav]['index'] = favorite_data[fav]['index'] - 1

                # Update new index
                favorite_data[relative_path]['index'] = new_index

            # Always be sure to sort the ordered dict
            favorite_data = OrderedDict(sorted(favorite_data.items(), key=lambda val: val[1]['index']))

            # Write favorites to lab book
            with open(favorites_file, 'wt') as f_data:
                json.dump(favorite_data, f_data, indent=2)

            # Remove cached favorite key data
            self._favorite_keys = None

            # Commit the changes
            self.git.add(favorites_file)
            self.git.commit(f"Committing update to Favorite file {favorites_file}")

            return favorite_data[relative_path]

    def remove_favorite(self, section: str, relative_path: str) -> None:
        """Mark an existing file as a Favorite

        Args:
            section(str): lab book subdir where file exists (code, input, output)
            relative_path(str): Relative path within the section to the file to favorite

        Returns:
            None
        """
        if section not in ['code', 'input', 'output']:
            raise ValueError("Favorites only supported in `code`, `input`, and `output` Lab Book directories")

        with self.lock_labbook():
            # Open existing Favorites json if exists
            favorites_dir = os.path.join(self.root_dir, '.gigantum', 'favorites')

            data_file = os.path.join(favorites_dir, f'{section}.json')
            if not os.path.exists(data_file):
                raise ValueError(f"No {section} favorites have been created yet. Cannot remove item {relative_path}!")

            # Read existing data
            with open(data_file, 'rt') as f_data:
                favorite_data = json.load(f_data)

            if relative_path not in favorite_data:
                raise ValueError(f"Favorite {relative_path} not found in {section}. Cannot remove.")

            # Remove favorite at index value
            del favorite_data[relative_path]

            # Always be sure to sort the ordered dict
            favorite_data = OrderedDict(sorted(favorite_data.items(), key=lambda val: val[1]['index']))

            # Reset index vals
            for idx, fav in enumerate(favorite_data):
                favorite_data[fav]['index'] = idx

            # Write favorites to back lab book
            with open(data_file, 'wt') as f_data:
                json.dump(favorite_data, f_data, indent=2)

            logger.info(f"Removed {section} favorite {relative_path}")

            # Remove cached favorite key data
            self._favorite_keys = None

            # Commit the changes
            self.git.add(data_file)
            self.git.commit(f"Committing update to Favorite file {data_file}")

            return None

    def get_favorites(self, section: str) -> OrderedDict:
        """Get Favorite data in an OrderedDict, sorted by index

        Args:
            section(str): lab book subdir where file exists (code, input, output)

        Returns:
            None
        """
        if section not in ['code', 'input', 'output']:
            raise ValueError("Favorites only supported in `code`, `input`, and `output` Lab Book directories")

        favorite_data: OrderedDict = OrderedDict()
        favorites_dir = os.path.join(self.root_dir, '.gigantum', 'favorites')
        if os.path.exists(os.path.join(favorites_dir, f'{section}.json')):
            # Read existing data
            with open(os.path.join(favorites_dir, f'{section}.json'), 'rt') as f_data:
                favorite_data = json.load(f_data, object_pairs_hook=OrderedDict)

        return favorite_data

    def new(self, owner: Dict[str, str], name: str, username: Optional[str] = None,
            description: Optional[str] = None, bypass_lfs: bool = False) -> str:
        """Method to create a new minimal LabBook instance on disk

        /[LabBook name]
            /code
            /input
            /output
            /.gigantum
                labbook.yaml
                .checkout
                /env
                    Dockerfile
                /activity
                    /log
                    /index
            /.git

        Args:
            owner(dict): Owner information. Can be a user or a team/org.
            name(str): Name of the LabBook
            username(str): Username of the logged in user. Used to store the LabBook in the proper location. If omitted
                           the owner username is used
            description(str): A short description of the LabBook

        Returns:
            str: Path to the LabBook contents
        """
        if not owner:
            raise ValueError("You must provide owner details when creating a LabBook.")

        if not username:
            logger.warning("Using owner username `{}` when making new labbook".format(owner['username']))
            username = owner["username"]

        if not name:
            raise ValueError("Name must be provided for new labbook")

        if name == 'export':
            raise ValueError("LabBook cannot be named `export`.")

        # Build data file contents
        self._data = {
            "labbook": {"id": uuid.uuid4().hex,
                        "name": name,
                        "description": self._santize_input(description or '')},
            "owner": owner,
            "schema": CURRENT_SCHEMA
        }

        # Validate data
        self._validate_labbook_data()

        logger.info("Creating new labbook on disk for {}/{}/{} ...".format(username, owner, name))

        # lock while creating initial directory
        with self.lock_labbook(lock_key=f"new_labbook_lock|{username}|{owner['username']}|{name}"):
            # Verify or Create user subdirectory
            # Make sure you expand a user dir string
            starting_dir = os.path.expanduser(self.labmanager_config.config["git"]["working_directory"])
            user_dir = os.path.join(starting_dir, username)
            if not os.path.isdir(user_dir):
                os.makedirs(user_dir)

            # Create owner dir - store LabBooks in working dir > logged in user > owner
            owner_dir = os.path.join(user_dir, owner["username"])
            if not os.path.isdir(owner_dir):
                os.makedirs(owner_dir)

                # Create `labbooks` subdir in the owner dir
                owner_dir = os.path.join(owner_dir, "labbooks")
            else:
                owner_dir = os.path.join(owner_dir, "labbooks")

            # Verify name not already in use
            if os.path.isdir(os.path.join(owner_dir, name)):
                # Exists already. Raise an exception
                raise ValueError(f"LabBook `{name}` already exists locally. Choose a new LabBook name")

            # Create LabBook subdirectory
            new_root_dir = os.path.join(owner_dir, name)

            logger.info(f"Making labbook directory in {new_root_dir}")

            os.makedirs(new_root_dir)
            self._set_root_dir(new_root_dir)

            # Init repository
            self.git.initialize()

            # Setup LFS
            if self.labmanager_config.config["git"]["lfs_enabled"] and not bypass_lfs:
                # Make sure LFS install is setup
                subprocess.run(f"git lfs install", shell=True, check=True, cwd=new_root_dir)

                # Track input and output directories
                subprocess.run(f"git lfs track input/**", shell=True, check=True, cwd=new_root_dir)
                subprocess.run(f"git lfs track output/**", shell=True, check=True, cwd=new_root_dir)

                # Commit .gitattributes file
                self.git.add(os.path.join(self.root_dir, ".gitattributes"))
                self.git.commit("Configuring LFS")

            # Create Directory Structure
            dirs = [
                'code', 'input', 'output', '.gigantum',
                os.path.join('.gigantum', 'env'),
                os.path.join('.gigantum', 'env', 'base'),
                os.path.join('.gigantum', 'env', 'custom'),
                os.path.join('.gigantum', 'env', 'package_manager'),
                os.path.join('.gigantum', 'activity'),
                os.path.join('.gigantum', 'activity', 'log'),
                os.path.join('.gigantum', 'activity', 'index'),
                os.path.join('.gigantum', 'activity', 'importance'),
            ]

            for d in dirs:
                self.makedir(d, make_parents=True)

            # Create labbook.yaml file
            self._save_labbook_data()

            # Save build info
            try:
                buildinfo = Configuration().config['build_info']
            except KeyError:
                logger.warning("Could not obtain build_info from config")
                buildinfo = None
            buildinfo = {
                'creation_utc': datetime.datetime.utcnow().isoformat(),
                'build_info': buildinfo
            }

            buildinfo_path = os.path.join(self.root_dir, '.gigantum', 'buildinfo')
            with open(buildinfo_path, 'w') as f:
                json.dump(buildinfo, f)
            self.git.add(buildinfo_path)

            # Create .gitignore default file
            shutil.copyfile(os.path.join(resource_filename('lmcommon', 'labbook'), 'gitignore.default'),
                            os.path.join(self.root_dir, ".gitignore"))

            # Commit
            for s in ['code', 'input', 'output', '.gigantum']:
                self.git.add_all(os.path.join(self.root_dir, s))
            self.git.add(os.path.join(self.root_dir, ".gigantum", "labbook.yaml"))
            self.git.add(os.path.join(self.root_dir, ".gitignore"))
            self.git.create_branch(name="gm.workspace")
            self.git.commit(f"Creating new empty LabBook: {name}")

            user_workspace_branch = f"gm.workspace-{username}"
            self.git.create_branch(user_workspace_branch)
            self.checkout_branch(branch_name=user_workspace_branch)

            if self.active_branch != user_workspace_branch:
                raise ValueError(f"active_branch should be '{user_workspace_branch}'")

            return self.root_dir

    def from_key(self, key: str) -> None:
        """Method to populate labbook from a unique key.

        Args:
            key(str): Encoded key of labbook

        Returns:
            None (Populates this labbook instance)
        """

        logger.debug(f"Populating LabBook from key {key}")

        if len(key.split("|")) != 3:
            raise ValueError(f"Invalid LabBook key `{key}`")

        user_key, owner_key, lb_name_key = key.split("|")
        self.from_name(user_key, owner_key, lb_name_key)

    def rename(self, new_name: str) -> None:
        """Method to rename a labbook

        Args:
            new_name(str): New desired labbook name

        Returns:
            None
        """
        old_name = self.name
        with self.lock_labbook(lock_key=f"rename_lock|{old_name}|{new_name}"):
            # Make sure name does not already exist
            labbooks_dir = self.root_dir.rsplit(os.path.sep, 1)[0]
            if os.path.exists(os.path.join(labbooks_dir, new_name)):
                raise ValueError(f"New LabBook name '{new_name}' already exists")

            # Rename labbook directory to new directory and update YAML file
            self.name = new_name

            # Remove the .checkout file, as you should create a new checkout context due to the labbook renaming
            if os.path.exists(os.path.join(self.root_dir, ".gigantum", ".checkout")):
                os.remove(os.path.join(self.root_dir, ".gigantum", ".checkout"))

            # Commit Change
            self.git.add(os.path.join(self.root_dir, ".gigantum", "labbook.yaml"))
            commit_msg = f"Renamed LabBook '{old_name}' to '{new_name}'"
            commit = self.git.commit(commit_msg)

            # Create detail record
            adr = ActivityDetailRecord(ActivityDetailType.LABBOOK, show=False, importance=0)
            adr.add_value('text/plain', commit_msg)

            # Create activity record
            ar = ActivityRecord(ActivityType.LABBOOK,
                                message=commit_msg,
                                show=True,
                                importance=255,
                                linked_commit=commit.hexsha)
            ar.add_detail_object(adr)

            # Store
            ars = ActivityStore(self)
            ars.create_activity_record(ar)

    def from_directory(self, root_dir: str) -> None:
        """Method to populate a LabBook instance from a directory

        Args:
            root_dir(str): The absolute path to the directory containing the LabBook

        Returns:
            None
        """

        logger.debug(f"Populating LabBook from directory {root_dir}")

        # Update root dir
        self._set_root_dir(root_dir)

        # Load LabBook data file
        self._load_labbook_data()
        self._validate_labbook_data()

        # If an old labbook that still uses master branch
        # Eventually, this clause will be removed.
        if self.active_branch == 'master':
            shims.to_workspace_branch(self)

    def from_name(self, username: str, owner: str, labbook_name: str):
        """Method to populate a LabBook instance based on the user and name of the labbook

        Args:
            username(str): The username of the logged in user
            owner(str): The username/org name of the owner of the LabBook
            labbook_name(str): the name of the LabBook

        Returns:
            LabBook
        """

        if not username:
            raise ValueError("username cannot be None or empty")

        if not owner:
            raise ValueError("owner cannot be None or empty")

        if not labbook_name:
            raise ValueError("labbook_name cannot be None or empty")

        labbook_path = os.path.expanduser(os.path.join(self.labmanager_config.config["git"]["working_directory"],
                                                       username,
                                                       owner,
                                                       "labbooks",
                                                       labbook_name))

        # Make sure directory exists
        if not os.path.isdir(labbook_path):
            raise ValueError("LabBook `{}` not found locally.".format(labbook_name))

        # Update root dir
        self._set_root_dir(labbook_path)

        # Load LabBook data file
        self._load_labbook_data()

        # Make sure name matches directory name.
        dname = [t for t in self.root_dir.split(os.sep) if t][-1]
        if self.name != dname:
            raise ValueError(f"Labbook name {self.name} does not match directory name {dname}")

    def from_remote(self, remote_url: str, username: str, owner: str, labbook_name: str):
        """Clone a labbook from a remote Git repository.

        Args:
            remote_url(str): URL or path of remote repo
            username(str): Username of logged in user
            owner(str): Owner/namespace of labbook
            labbook_name(str): Name of labbook

        Returns:
            None
        """

        if not remote_url:
            raise ValueError("remote_url cannot be None or empty")

        if not username:
            raise ValueError("username cannot be None or empty")

        if not owner:
            raise ValueError("owner cannot be None or empty")

        if not labbook_name:
            raise ValueError("labbook_name cannot be None or empty")

        starting_dir = os.path.expanduser(self.labmanager_config.config["git"]["working_directory"])

        # Expected full path of the newly imported labbook.
        est_root_dir = os.path.join(starting_dir, username, owner, 'labbooks', labbook_name)
        if os.path.exists(est_root_dir):
            errmsg = f"Cannot clone labbook, path already exists at `{est_root_dir}`"
            logger.error(errmsg)
            raise ValueError(errmsg)

        logger.info(f"Cloning labbook from remote origin `{remote_url}` into `{est_root_dir}...")
        self.git.clone(remote_url, directory=est_root_dir)
        self.git.fetch()
        logger.info(f"Checking out gm.workspace")
        self.git.checkout("gm.workspace")

        logger.info(f"Checking out gm.workspace-{username}")
        if f'origin/gm.workspace-{username}' in self.get_branches()['remote']:
            self.git.checkout(f"gm.workspace-{username}")
        else:
            self.checkout_branch(f"gm.workspace-{username}", new=True)

        # Once the git repo is cloned, the problem just becomes a regular import from file system.
        self.from_directory(est_root_dir)

    def list_local_labbooks(self, username: str = None) -> Optional[Dict[Optional[str], List[Dict[str, str]]]]:
        """Method to list available LabBooks

        Args:
            username(str): Username to filter the query on

        Returns:
            dict: A dictionary containing labbooks grouped by local username
        """
        # Make sure you expand a user string
        working_dir = os.path.expanduser(self.labmanager_config.config["git"]["working_directory"])

        if not username:
            # Return all available labbooks
            files_collected = glob.glob(os.path.join(working_dir,
                                                     "*",
                                                     "*",
                                                     "labbooks",
                                                     "*"))
        else:
            # Return only labbooks for the provided user
            files_collected = glob.glob(os.path.join(working_dir,
                                                     username,
                                                     "*",
                                                     "labbooks",
                                                     "*"))
        # Sort to give deterministic response
        files_collected = sorted(files_collected)

        # Generate dictionary to return
        result: Optional[Dict[Optional[str], List[Dict[str, str]]]] = None
        for dir_path in files_collected:
            if os.path.isdir(dir_path):
                _, username, owner, _, labbook = dir_path.rsplit(os.path.sep, 4)
                if result:
                    if username not in result:
                        result[username] = [{"owner": owner, "name": labbook}]
                    else:
                        result[username].append({"owner": owner, "name": labbook})
                else:
                    result = {username: [{"owner": owner, "name": labbook}]}

        return result

    def log(self, username: str = None, max_count: int=10):
        """Method to list commit history of a Labbook

        Args:
            username(str): Username to filter the query on

        Returns:
            dict
        """
        # TODO: Add additional optional args to the git.log call to support further filtering
        return self.git.log(max_count=max_count, author=username)

    def log_entry(self, commit: str):
        """Method to get a single log entry by commit

        Args:
            commit(str): commit hash of the entry

        Returns:
            dict
        """
        return self.git.log_entry(commit)

    def write_readme(self, contents: str) -> None:
        """Method to write a string to the readme file within the LabBook. Must write ENTIRE document at once.

        Args:
            contents(str): entire readme document in markdown format

        Returns:
            None
        """
        # Validate readme data
        if len(contents) > (1000000 * 5):
            raise ValueError("Readme file is larger than the 5MB limit")

        if type(contents) is not str:
            raise TypeError("Invalid content. Must provide string")

        readme_file = os.path.join(self.root_dir, 'README.md')
        readme_exists = os.path.exists(readme_file)

        # Write file to disk
        with open(readme_file, 'wt') as rf:
            rf.write(contents)

        # Create commit
        if readme_exists:
            commit_msg = f"Updated LabBook README"
        else:
            commit_msg = f"Added README to LabBook"

        self.git.add(readme_file)
        commit = self.git.commit(commit_msg)

        # Create detail record
        adr = ActivityDetailRecord(ActivityDetailType.LABBOOK, show=False, importance=0)
        adr.add_value('text/plain', commit_msg)

        # Create activity record
        ar = ActivityRecord(ActivityType.LABBOOK,
                            message=commit_msg,
                            show=False,
                            importance=255,
                            linked_commit=commit.hexsha,
                            tags=['readme'])
        ar.add_detail_object(adr)

        # Store
        ars = ActivityStore(self)
        ars.create_activity_record(ar)

    def get_readme(self) -> Optional[str]:
        """Method to read the readme document

        Returns:
            (str): entire readme document in markdown format
        """
        readme_file = os.path.join(self.root_dir, 'README.md')
        contents = None
        if os.path.exists(readme_file):
            with open(readme_file, 'rt') as rf:
                contents = rf.read()
        
        return contents

