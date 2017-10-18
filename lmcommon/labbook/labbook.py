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

from lmcommon.configuration import Configuration
from lmcommon.gitlib import get_git_interface, GitAuthor
from lmcommon.logging import LMLogger
from lmcommon.notes import NoteLogLevel, NoteStore

GIT_IGNORE_DEFAULT = """.DS_Store"""
logger = LMLogger.get_logger()


class LabBook(object):
    """Class representing a single LabBook"""

    def __init__(self, config_file: str = None) -> None:
        self.labmanager_config = Configuration(config_file)

        # Create gitlib instance
        self.git = get_git_interface(self.labmanager_config.config["git"])

        # LabBook Properties
        self._root_dir: Optional[str] = None  # The root dir is the location of the labbook this instance represents
        self._data: Optional[Dict[str, Any]] = None

        # LabBook Environment
        self._env = None

    def __str__(self):
        if self._root_dir:
            return f'<LabBook at `{self._root_dir}`>'
        else:
            return f'<LabBook UNINITIALIZED>'

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
        
        # Update the root directory to the knew directory name
        self._set_root_dir(os.path.join(base_dir, value))

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

        with open(os.path.join(self.root_dir, ".gigantum", "labbook.yaml"), 'wt') as lbfile:
            lbfile.write(yaml.dump(self._data, default_flow_style=False))

    def _validate_labbook_data(self) -> None:
        """Method to validate the LabBook data file contents

        Returns:
            None
        """
        if not re.match("^(?!-)(?!.*--)[a-z0-9-]+(?<!-)$", self.name):
            raise ValueError("Invalid `name`. Only a-z 0-9 and hyphens allowed. No leading or trailing hyphens.")

        if len(self.name) > 100:
            raise ValueError("Invalid `name`. Max length is 100 characters")

    # TODO: Get feedback on better way to sanitize
    def _santize_input(self, value: str) -> str:
        """Simple method to sanitize a user provided value with characters that can be bad

        Args:
            value(str): Input string

        Returns:
            str: Output string
        """
        return ''.join(c for c in value if c not in '\<>?/;"`\'')

    def insert_file(self, src_file: str, dst_dir: str) -> str:
        """Copy the file at `src_file` into the `dst_dir`. Filename stays the same.

        Args:
            src_file(str): Full path of file to insert into
            dst_dir(str): Relative path within labbook where `src_file` should be copied to

        Returns:
            str: Full path of copied file
        """

        if not os.path.abspath(src_file):
            raise ValueError(f"Source file `{src_file}` is not an absolute path")

        if not os.path.isfile(src_file):
            raise ValueError(f"Source file does not exist at `{src_file}`")

        # Remove any leading "/" -- without doing so os.path.join will break.
        dst_dir = LabBook._make_path_relative(dst_dir)
        dst_path = os.path.join(self.root_dir, dst_dir.replace('..', ''))
        if not os.path.isdir(dst_path):
            raise ValueError(f"Target `{dst_path}` not a directory")

        try:
            logger.info(f"Copying new file for {str(self)} from `{src_file}` to `{dst_path}")
            copied_path = shutil.copy(src_file, dst_path)
            rel_path = copied_path.replace(self.root_dir, '')
            commit_msg = f"Added new file {rel_path}."
            self.git.add(copied_path)
            commit = self.git.commit(commit_msg)
            _, ext = os.path.splitext(rel_path) or 'file'
            ns = NoteStore(self)
            ns.create_note({
                'linked_commit': commit.hexsha,
                'message': commit_msg,
                'level': NoteLogLevel.USER_MAJOR,
                'tags': [ext],
                'free_text': '',
                'objects': ''
            })
            return copied_path
        except Exception as e:
            logger.exception(e)
            raise

    def delete_file(self, relative_path: str) -> bool:
        """Delete file from inside lb directory"""
        if not relative_path:
            raise ValueError(f"Target file `{relative_path}` to delete cannot be None or empty")

        relative_path = LabBook._make_path_relative(relative_path)
        target_file_path = os.path.join(self.root_dir, relative_path)
        if not os.path.exists(target_file_path):
            raise ValueError(f"Attempted to delete non-existent path at `{target_file_path}`")
        if not os.path.isfile(target_file_path):
            raise ValueError(f"Attempted to delete non-existent file at `{target_file_path}`")
        else:
            try:
                logger.info(f"Removing file at `{target_file_path}`")
                os.remove(target_file_path)
                commit_msg = f"Removed file {relative_path}."
                self.git.remove(target_file_path)
                commit = self.git.commit(commit_msg)
                _, ext = os.path.splitext(target_file_path) or 'file'
                ns = NoteStore(self)
                ns.create_note({
                    'linked_commit': commit.hexsha,
                    'message': commit_msg,
                    'level': NoteLogLevel.USER_MAJOR,
                    'tags': [ext],
                    'free_text': '',
                    'objects': ''
                })
                return True
            except IOError as e:
                logger.exception(e)
                raise

    def move_file(self, src_rel_path: str, dst_rel_path: str) -> str:
        """Move a file or directory within a labbook, but not outside of it. Wraps
        underlying "mv" call.

        Args:
            src_rel_path(str): Source file or directory
            dst_rel_path(str): Target file name and/or directory
        """

        # Start with Validations
        if not src_rel_path:
            raise ValueError("src_rel_path cannot be None or empty")

        if not dst_rel_path:
            raise ValueError("dst_rel_path cannot be None or empty")

        src_rel_path = LabBook._make_path_relative(src_rel_path)
        dst_rel_path = LabBook._make_path_relative(dst_rel_path)

        src_abs_path = os.path.join(self.root_dir, src_rel_path.replace('..', ''))
        dst_abs_path = os.path.join(self.root_dir, dst_rel_path.replace('..', ''))

        if not os.path.exists(src_abs_path):
            raise ValueError(f"No src file exists at `{src_abs_path}`")

        try:
            src_type = 'directory' if os.path.isdir(src_abs_path) else 'file'
            logger.info(f"Moving {src_type} `{src_abs_path}` to `{dst_abs_path}`")

            self.git.remove(src_abs_path, keep_file=True)

            shutil.move(src_abs_path, dst_abs_path)
            commit_msg = f"Moved {src_type} `{src_rel_path}` to `{dst_rel_path}`"

            if os.path.isdir(dst_abs_path):
                self.git.add_all(dst_abs_path)
            else:
                self.git.add(dst_abs_path)

            commit = self.git.commit(commit_msg)
            ns = NoteStore(self)
            ns.create_note({
                'linked_commit': commit.hexsha,
                'message': commit_msg,
                'level': NoteLogLevel.USER_MAJOR,
                'tags': ['file-move'],
                'free_text': '',
                'objects': ''
            })

            return dst_abs_path
        except Exception as e:
            logger.critical("Failed moving file in labbook. Repository may be in corrupted state.")
            logger.exception(e)
            raise

    def makedir(self, relative_path: str, make_parents: bool = True) -> str:
        """Make a new directory inside the labbook directory.

        Args:
            relative_path(str): Path within the labbook to make directory
            make_parents(bool): If true, create intermediary directories

        Returns:
            str: Absolute path of new directory
        """
        if not relative_path:
            raise ValueError("relative_path argument cannot be None or empty")

        relative_path = LabBook._make_path_relative(relative_path)
        new_directory_path = os.path.join(self.root_dir, relative_path)
        if os.path.exists(new_directory_path):
            raise ValueError(f'Directory `{new_directory_path}` already exists')
        else:
            logger.info(f"Making new directory in `{new_directory_path}`")
            try:
                os.makedirs(new_directory_path, exist_ok=make_parents)
                new_dir = ''
                for d in relative_path.split(os.sep):
                    new_dir = os.path.join(new_dir, d)
                    full_new_dir = os.path.join(self.root_dir, new_dir)
                    with open(os.path.join(full_new_dir, '.gitkeep'), 'w') as gitkeep:
                        gitkeep.write("This file is necessary to keep this directory tracked by Git"
                                      " and archivable by compression tools. Do not delete or modify!")
            except Exception as e:
                logger.exception(e)
                raise
            return new_directory_path

    def listdir(self, show_hidden: bool = False) -> List[Dict[str, Any]]:
        """Return a list of all files and directories in the labbook. Never includes the .git or
         .gigantum directory.

        Args:
            show_hidden(bool): If True, include hidden directories (EXCLUDING .git and .gigantum)

        Returns:
            List[Dict[str, str]]: List of dictionaries containing file and directory metadata
        """

        leafs: Set[Tuple[bool, str]] = set()
        for root, dirs, files in os.walk(self.root_dir):
            for f in files:
                leafs.add((False, os.path.join(root.replace(self.root_dir, ''), f)))
            for d in dirs:
                leafs.add((True, os.path.join(root.replace(self.root_dir, ''), d)))

        leafs_filtered = [l for l in leafs if '.git' not in l[1] and '.gigantum' not in l[1]]
        stats: List[Dict[str, Any]] = list()
        for is_dir, f_p in [l for l in leafs_filtered if '.git' not in l]:
            if not show_hidden and any([len(p) and p[0] == '.' for p in f_p.split('/')]):
                continue
            f_p = f_p[1:] if f_p[0] == '/' else f_p
            file_info = os.stat(os.path.join(self.root_dir, f_p))
            stats.append({
                'key': f_p,
                'is_dir': is_dir,
                'size': file_info.st_size,
                'modified_at': file_info.st_mtime
            })

        return sorted(stats, key=lambda a: a['key'])

    def new(self, owner: Dict[str, str], name: str, username: str = None, description: str = None) -> str:
        """Method to create a new minimal LabBook instance on disk

        /[LabBook name]
            /code
            /input
            /output
            /.gigantum
                labbook.yaml
                /env
                    Dockerfile
                /notes
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
            "owner": owner
        }

        # Validate data
        self._validate_labbook_data()

        logger.info("Creating new labbook on disk for {}/{}/{} ...".format(username, owner, name))

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

        # Create Directory Structure
        dirs = [
            'code', 'input', 'output', '.gigantum',
            os.path.join('.gigantum', 'env'),
            os.path.join('.gigantum', 'notes'),
            os.path.join('.gigantum', 'notes', 'log'),
            os.path.join('.gigantum', 'notes', 'index'),
        ]

        for d in dirs:
            self.makedir(d, make_parents=True)

        # Create labbook.yaml file
        self._save_labbook_data()

        # Create blank Dockerfile
        # TODO: Add better base dockerfile once environment service defines this
        with open(os.path.join(self.root_dir, ".gigantum", "env", "Dockerfile"), 'wt') as dockerfile:
            dockerfile.write("FROM ubuntu:16.04")

        # Create .gitignore default file
        # TODO: Use a base .gitignore file vs. global variable
        with open(os.path.join(self.root_dir, ".gitignore"), 'wt') as gi_file:
            gi_file.write(GIT_IGNORE_DEFAULT)

        # Commit
        # TODO: Once users are properly added, create a GitAuthor instance before commit
        for s in ['code', 'input', 'output', '.gigantum']:
            self.git.add_all(os.path.join(self.root_dir, s))
        self.git.add(os.path.join(self.root_dir, ".gigantum", "labbook.yaml"))
        self.git.add(os.path.join(self.root_dir, ".gigantum", "env", "Dockerfile"))
        self.git.add(os.path.join(self.root_dir, ".gitignore"))
        self.git.commit(f"Creating new empty LabBook: {name}")

        return self.root_dir

    def from_directory(self, root_dir: str):
        """Method to populate a LabBook instance from a directory

        Args:
            root_dir(str): The absolute path to the directory containing the LabBook

        Returns:
            LabBook
        """

        logger.debug(f"Populating LabBook from directory {root_dir}")

        # Update root dir
        self._set_root_dir(root_dir)

        # Load LabBook data file
        with open(os.path.join(self.root_dir, ".gigantum", "labbook.yaml"), "rt") as data_file:
            self._data = yaml.load(data_file)

    def from_name(self, username: str, owner:str, labbook_name:str):
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
        with open(os.path.join(self.root_dir, ".gigantum", "labbook.yaml"), "rt") as data_file:
            self._data = yaml.load(data_file)

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

    def log(self, username: str = None, max_count: int = 10):
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

