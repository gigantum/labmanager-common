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
import uuid
import yaml
import json
import time
import datetime
import gitdb
import redis_lock
from contextlib import contextmanager
from pkg_resources import resource_filename
from collections import OrderedDict
from redis import StrictRedis
from natsort import natsorted
from typing import (Any, Dict, List, Optional, Tuple)

from lmcommon.configuration import Configuration
from lmcommon.configuration.utils import call_subprocess
from lmcommon.gitlib import get_git_interface, GitAuthor, GitRepoInterface
from lmcommon.logging import LMLogger
from lmcommon.labbook.schemas import validate_labbook_schema
from lmcommon.labbook import shims
from lmcommon.activity import ActivityStore, ActivityType, ActivityRecord, ActivityDetailType, ActivityDetailRecord, \
    ActivityAction
from lmcommon.labbook.schemas import CURRENT_SCHEMA

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

    def _validate_git(method_ref):  #type: ignore
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
                    n = method_ref(self, *args, **kwargs)  #type: ignore
                except ValueError:
                    with self.lock_labbook():
                        self.sweep_uncommitted_changes()
                    n = method_ref(self, *args, **kwargs)  # type: ignore
                    with self.lock_labbook():
                        self.sweep_uncommitted_changes()
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
    def make_path_relative(path_str: str) -> str:
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

    @property
    def cuda_version(self) -> Optional[str]:
        if self._data and self._data.get("cuda_version"):
            return self._data.get("cuda_version")
        else:
            return None

    @cuda_version.setter
    def cuda_version(self, cuda_version: Optional[str] = None) -> None:
        if self._data:
            self._data['cuda_version'] = cuda_version
            self._save_labbook_data()
        else:
            raise RuntimeError("LabBook _data cannot be None")

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

    def validate_section(self, section: str) -> None:
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

    def sweep_uncommitted_changes(self, upload: bool = False,
                                  extra_msg: Optional[str] = None,
                                  show: bool = False) -> None:
        """ Sweep all changes into a commit, and create activity record.
            NOTE: This method MUST be called inside a lock.

        Args:
            upload(bool): Flag indicating if this was from a batch upload
            extra_msg(str): Optional string used to augment the activity message
            show(bool): Optional flag indicating if the result of this sweep is important enough to be shown in the feed

        Returns:

        """
        result_status = self.git.status()
        if any([result_status[k] for k in result_status.keys()]):
            self.git.add_all()
            self.git.commit("Sweep of uncommitted changes")

            ar = ActivityRecord(ActivityType.LABBOOK,
                                message="--overwritten--",
                                show=show,
                                importance=255,
                                linked_commit=self.git.commit_hash,
                                tags=['save'])
            if upload:
                ar.tags.append('upload')
            ar, newcnt, modcnt = shims.process_sweep_status(
                ar, result_status, LabBook.infer_section_from_relative_path)
            nmsg = f"{newcnt} new file(s). " if newcnt > 0 else ""
            mmsg = f"{modcnt} modified file(s). " if modcnt > 0 else ""
            ar.message = f"{extra_msg or ''}" \
                         f"{'Uploaded ' if upload else ''}" \
                         f"{nmsg}{mmsg}"
            ars = ActivityStore(self)
            ars.create_activity_record(ar)
        else:
            logger.info(f"{str(self)} no changes to sweep.")

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
        except gitdb.exc.BadName as e:
            logger.error(e)
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

    def add_remote(self, remote_name: str, url: str) -> None:
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
            raise LabbookException(e)

    def remove_remote(self, remote_name: Optional[str] = "origin") -> None:
        """Remove a remove from the git config

        Args:
            remote_name: Optional name of remote (default "origin")
        """
        try:
            logger.info(f"Removing remote {remote_name} from {str(self)}")
            self.git.remove_remote(remote_name)
        except Exception as e:
            raise LabbookException(e)

    def remove_lfs_remotes(self) -> None:
        """Remove all LFS endpoints.

        Each LFS enpoint has its own entry in the git config. It takes the form of the following:

        ```
        [lfs "https://repo.location.whatever"]
            access = basic
        ```

        In order to get the section name, which is "lfs.https://repo.location.whatever", we need to search
        by all LFS fields and remove them (and in order to get the section need to strip the variables off the end).

        Returns:
            None
        """
        lfs_sections = call_subprocess(['git', 'config', '--get-regexp', 'lfs.http*'], cwd=self.root_dir).split('\n')
        logger.info(f"LFS entries to delete are {lfs_sections}")
        for lfs_sec in set([n for n in lfs_sections if n]):
            var = lfs_sec.split(' ')[0]
            section = '.'.join(var.split('.')[:-1])
            call_subprocess(['git', 'config', '--remove-section', section], cwd=self.root_dir)

    def get_branches(self) -> Dict[str, List[str]]:
        """Return all branches a Dict of Lists. Dict contains two keys "local" and "remote".

        Args:
            None

        Returns:
            Dictionary of lists for "remote" and "local" branches.
        """

        try:
            # Note - do NOT fetch here - fetch should be done before this is called.
            return self.git.list_branches()
        except Exception as e:
            # Unsure what specific exception add_remote creates, so make a catchall.
            logger.exception(e)
            raise LabbookException(e)

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
            target_path_rel = LabBook.make_path_relative(target_path_rel)
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
            description: Optional[str] = None, bypass_lfs: bool = False, cuda: bool = False) -> str:
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
            bypass_lfs: If True does not use LFS to track input and output dirs.

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
            "cuda_version": None,
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
                # Make sure LFS install is setup and rack input and output directories
                call_subprocess(["git", "lfs", "install"], cwd=new_root_dir)
                call_subprocess(["git", "lfs", "track", "input/**"], cwd=new_root_dir)
                call_subprocess(["git", "lfs", "track", "output/**"], cwd=new_root_dir)

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
                p = os.path.join(self.root_dir, d, '.gitkeep')
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, 'w') as gk:
                    gk.write("This file is necessary to keep this directory tracked by Git"
                             " and archivable by compression tools. Do not delete or modify!")
                self.git.add(p)

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

            # NOTE: this string is used to indicate there are no more activity records to get. Changing the string will
            # break activity paging.
            # TODO: Improve method for detecting the first activity record
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

    def from_directory(self, root_dir: str) -> None:
        """Method to populate a LabBook instance from a directory

        Args:
            root_dir(str): The absolute path to the directory containing the LabBook

        Returns:
            None
        """
        self._set_root_dir(root_dir)
        self._load_labbook_data()
        self._validate_labbook_data()

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

    def list_local_labbooks(self, username: str,
                            sort_mode: str = "name",
                            reverse: bool = False) -> List[Dict[str, str]]:
        """Method to list available LabBooks

        Args:
            username(str): Username to filter the query on
            sort_mode(sort_mode): String specifying how labbooks should be sorted
            reverse(bool): Reverse sorting if True. Default is ascending (a-z, oldest-newest)

        Supported sorting modes:
            - name: naturally sort
            - created_on: sort by creation date, newest first
            - modified_on: sort by modification date, newest first

        Returns:
            dict: A list of labbooks for a given user
        """
        # Make sure you expand a user string
        working_dir = os.path.expanduser(self.labmanager_config.config["git"]["working_directory"])

        # Return only labbooks for the provided user
        files_collected = glob.glob(os.path.join(working_dir,
                                                 username,
                                                 "*",
                                                 "labbooks",
                                                 "*"))

        # Sort to give deterministic response
        files_collected = sorted(files_collected)

        # Generate dictionary to return
        result: List[Dict[str, str]] = list()
        for dir_path in files_collected:
            if os.path.isdir(dir_path):
                _, username, owner, _, labbook = dir_path.rsplit(os.path.sep, 4)

                lb_item = {"owner": owner, "name": labbook}

                if sort_mode == 'name':
                    lb_item['sort_val'] = labbook
                elif sort_mode == 'created_on':
                    # get create data from yaml file
                    try:
                        lb = LabBook()
                        lb.from_directory(dir_path)
                    except Exception as e:
                        logger.error(e)
                        continue
                    create_date = lb.creation_date

                    # SHIM - Can be removed on major release
                    if not create_date:
                        # This is an old labbook with no creation data metadata
                        first_commit = lb.git.repo.git.rev_list('HEAD', max_parents=0)
                        create_date = lb.git.log_entry(first_commit)['committed_on'].replace(tzinfo=None)

                    lb_item['sort_val'] = create_date

                elif sort_mode == 'modified_on':
                    # lookup date of last commit
                    try:
                        lb = LabBook()
                        lb.from_directory(dir_path)
                        lb_item['sort_val'] = lb.git.log(max_count=1)[0]['committed_on']
                    except Exception as e:
                        logger.error(e)
                        continue
                else:
                    raise ValueError(f"Unsupported sort_mode: {sort_mode}")

                result.append(lb_item)

        # Apply sort
        if sort_mode in ['created_on', 'modified_on']:
            # Sort on datetime objects, flipping the reverse state to match default sort behavior
            result = sorted(result, key=lambda x: x['sort_val'], reverse=reverse)
        else:
            # Use natural sort for labbook names
            result = natsorted(result, key=lambda x: x['sort_val'], reverse=reverse)

        # Remove sort_val from dictionary before returning
        for item in result:
            del item['sort_val']

        return result

    def log(self, username: str = None, max_count: int = 10):
        """Method to list commit history of a Labbook

        Args:
            username(str): Username to filter the query on
            max_count: Max number of log records to retrieve

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
            action = ActivityAction.EDIT
        else:
            commit_msg = f"Added README to LabBook"
            action = ActivityAction.CREATE

        self.git.add(readme_file)
        commit = self.git.commit(commit_msg)

        # Create detail record
        adr = ActivityDetailRecord(ActivityDetailType.LABBOOK, show=False, importance=0, action=action)
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
