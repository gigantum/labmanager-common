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

from lmcommon.configuration import Configuration
from lmcommon.gitlib import get_git_interface, GitAuthor
from lmcommon.logging import LMLogger
from lmcommon.notes import NoteLogLevel, NoteStore

from .schemas import validate_schema

GIT_IGNORE_DEFAULT = """.DS_Store"""
logger = LMLogger.get_logger()


class LabBook(object):
    """Class representing a single LabBook"""

    # If this is not definied, implicity the version is "0.0".
    LABBOOK_DATA_SCHEMA_VERSION = "0.1"

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
        
        # Update the root directory to the new directory name
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

        # TODO: Remove in the future after breaking changes are completed
        # Skip schema check if it doesn't exist (aka an old labbook)
        if "schema" in self.data:
            if not validate_schema(self.LABBOOK_DATA_SCHEMA_VERSION, self.data):
                errmsg = f"Schema in Labbook {str(self)} does not match indicated version {self.LABBOOK_DATA_SCHEMA_VERSION}"
                logger.error(errmsg)
                raise ValueError(errmsg)
        else:
            logger.info("Skipping schema check on old LabBook")

    # TODO: Get feedback on better way to sanitize
    def _santize_input(self, value: str) -> str:
        """Simple method to sanitize a user provided value with characters that can be bad

        Args:
            value(str): Input string

        Returns:
            str: Output string
        """
        return ''.join(c for c in value if c not in '\<>?/;"`\'')

    def _get_file_info(self, rel_file_path: str) -> Dict[str, Any]:
        """Method to get a file's detail information

        Args:
            rel_file_path(str): The relative file path to generate info from

        Returns:
            dict
        """
        # remove leading separators if one exists.
        rel_file_path = rel_file_path[1:] if rel_file_path[0] == os.path.sep else rel_file_path

        full_path = os.path.join(self.root_dir, rel_file_path)
        file_info = os.stat(full_path)
        is_dir = os.path.isdir(full_path)

        # If it's a directory, add a trailing slash to UI renders properly
        if is_dir:
            if rel_file_path[-1] != os.path.sep:
                rel_file_path = f"{rel_file_path}{os.path.sep}"

        return {
                  'key': rel_file_path,
                  'is_dir': is_dir,
                  'size': file_info.st_size,
                  'modified_at': file_info.st_mtime
               }

    def insert_file(self, src_file: str, dst_dir: str, base_filename: Optional[str] = None) -> Dict[str, Any]:
        """Copy the file at `src_file` into the `dst_dir`. Filename removes upload ID if present.

        Args:
            src_file(str): Full path of file to insert into
            dst_dir(str): Relative path within labbook where `src_file` should be copied to
            base_filename(str): The desired basename for the file, without an upload ID prepended

        Returns:
            dict: The inserted file's info
        """

        if not os.path.abspath(src_file):
            raise ValueError(f"Source file `{src_file}` is not an absolute path")

        if not os.path.isfile(src_file):
            raise ValueError(f"Source file does not exist at `{src_file}`")

        # Remove any leading "/" -- without doing so os.path.join will break.
        dst_dir = LabBook._make_path_relative(dst_dir)

        # Check if this file contains an upload_id (which means it came from a chunked upload)
        if base_filename:
            dst_filename = base_filename
        else:
            dst_filename = os.path.basename(src_file)

        # Create the absolute file path for the destination
        dst_path = os.path.join(self.root_dir, dst_dir.replace('..', ''), dst_filename)
        if not os.path.isdir(os.path.join(self.root_dir, dst_dir.replace('..', ''))):
            raise ValueError(f"Target dir `{os.path.join(self.root_dir, dst_dir.replace('..', ''))}` does not exist")

        try:
            # Copy file to destination
            logger.info(f"Inserting new file for {str(self)} from `{src_file}` to `{dst_path}")
            shutil.copyfile(src_file, dst_path)

            # Create commit
            rel_path = dst_path.replace(self.root_dir, '')
            commit_msg = f"Added new file {rel_path}"
            self.git.add(dst_path)
            commit = self.git.commit(commit_msg)

            # Create Activity record
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
            return self._get_file_info(rel_path)
        except Exception as e:
            logger.exception(e)
            raise

    def delete_file(self, relative_path: str, directory: bool = False) -> bool:
        """Delete file (or directory) from inside lb directory.

        Part of the intention is to mirror the unix "rm" command. Thus, there
        needs to be some extra arguments in order to delete a directory, especially
        one with contents inside of it. In this case, `directory` must be true in order
        to delete a directory at the given path.

        Args:
            relative_path(str): Relative path from labbook root to target
            directory(bool): True if relative_path is a directory

        Returns:
            None
        """

        relative_path = LabBook._make_path_relative(relative_path)
        target_path = os.path.join(self.root_dir, relative_path)
        if not os.path.exists(target_path):
            raise ValueError(f"Attempted to delete non-existent path at `{target_path}`")
        else:
            try:
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

                commit_msg = f"Removed {target_type} {relative_path}."
                self.git.remove(target_path)
                commit = self.git.commit(commit_msg)
                if os.path.isfile(target_path):
                    _, ext = os.path.splitext(target_path)
                else:
                    ext = 'directory'
                ns = NoteStore(self)
                ns.create_note({
                    'linked_commit': commit.hexsha,
                    'message': commit_msg,
                    'level': NoteLogLevel.USER_MAJOR,
                    'tags': ['remove', ext],
                    'free_text': '',
                    'objects': ''
                })
                return True
            except (IOError, FileNotFoundError) as e:
                logger.exception(e)
                raise

    def move_file(self, src_rel_path: str, dst_rel_path: str) -> Dict[str, Any]:
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

            return self._get_file_info(dst_rel_path)
        except Exception as e:
            logger.critical("Failed moving file in labbook. Repository may be in corrupted state.")
            logger.exception(e)
            raise

    def makedir(self, relative_path: str, make_parents: bool = True) -> Dict[str, Any]:
        """Make a new directory inside the labbook directory.

        Args:
            relative_path(str): Path within the labbook to make directory
            make_parents(bool): If true, create intermediary directories

        Returns:
            dict: Absolute path of new directory
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
            return self._get_file_info(relative_path)

    def listdir(self, base_path: Optional[str] = None, show_hidden: bool = False) -> List[Dict[str, Any]]:
        """Return a list of all files and directories in the labbook. Never includes the .git or
         .gigantum directory.

        Args:
            base_path(str): Relative base path, if not listing from labbook's root.
            show_hidden(bool): If True, include hidden directories (EXCLUDING .git and .gigantum)

        Returns:
            List[Dict[str, str]]: List of dictionaries containing file and directory metadata
        """

        leafs: Set[Tuple[bool, str]] = set()
        # base_dir is the root directory to search, to account for relative paths inside labbook.
        base_dir = os.path.join(self.root_dir, base_path or '')
        if not os.path.isdir(base_dir):
            raise ValueError(f"Labbook listdir base_dir {base_dir} not an existing directory")

        for root, dirs, files in os.walk(base_dir):
            for f in files:
                leafs.add((False, os.path.join(root.replace(self.root_dir, ''), f)))
            for d in dirs:
                leafs.add((True, os.path.join(root.replace(self.root_dir, ''), d)))

        leafs_filtered = [l for l in leafs if '.git' not in l[1] and '.gigantum' not in l[1]]
        stats: List[Dict[str, Any]] = list()
        for is_dir, f_p in [l for l in leafs_filtered if '.git' not in l]:
            if not show_hidden and any([len(p) and p[0] == '.' for p in f_p.split('/')]):
                continue
            stats.append(self._get_file_info(f_p))

        # For more deterministic responses, sort resulting paths alphabetically.
        return sorted(stats, key=lambda a: a['key'])

    def create_favorite(self, target_sub_dir: str, relative_path: str,
                        description: Optional[str] = None, position: Optional[int] = None,
                        is_dir: bool = False) -> Dict[str, Any]:
        """Mark an existing file as a Favorite

        Args:
            target_sub_dir(str): lab book subdir where file exists (code, input, output)
            relative_path(str): Relative path within the root_dir to the file to favorite
            description(str): A short string containing information about the favorite
            position(int): The position to insert the favorite. If omitted, will append.
            is_dir(bool): If true, relative_path will expected to be a directory

        Returns:
            dict
        """
        if target_sub_dir not in ['code', 'input', 'output']:
            raise ValueError("Favorites only supported in `code`, `input`, and `output` Lab Book directories")

        # Generate desired absolute path
        target_path_rel = os.path.join(target_sub_dir, relative_path)

        # Remove any leading "/" -- without doing so os.path.join will break.
        target_path_rel = LabBook._make_path_relative(target_path_rel)
        target_path = os.path.join(self.root_dir, target_path_rel.replace('..', ''))

        if not os.path.exists(target_path):
            raise ValueError(f"Target file/dir `{target_path}` does not exist")

        if is_dir != os.path.isdir(target_path):
            raise ValueError(f"Target `{target_path}` a directory")

        try:
            logger.info(f"Marking {target_path} as favorite")

            # Open existing Favorites json if exists
            favorites_dir = os.path.join(self.root_dir, '.gigantum', 'favorites')
            if not os.path.exists(favorites_dir):
                # No favorites have been created
                os.makedirs(favorites_dir)

            favorite_data: List[Dict[str, Any]] = []
            if os.path.exists(os.path.join(favorites_dir, f'{target_sub_dir}.json')):
                # Read existing data
                with open(os.path.join(favorites_dir, f'{target_sub_dir}.json'), 'rt') as f_data:
                    favorite_data = json.load(f_data)

            favorite_record = {"key": os.path.join(target_sub_dir, relative_path),
                               "description": description,
                               "is_dir": is_dir}

            if any(f['key'] == favorite_record['key'] for f in favorite_data):
                raise ValueError(f"Favorite `{favorite_record['key']}` already exists.")

            if position:
                # insert at specific location
                if position >= len(favorite_data):
                    raise ValueError("Invalid index to insert favorite")

                if position < 0:
                    raise ValueError("Invalid index to insert favorite")

                favorite_data.insert(position, favorite_record)
                result_index = position
            else:
                # append
                favorite_data.append(favorite_record)
                result_index = len(favorite_data) - 1

            # Add index values
            favorite_data = [dict(fav_data, index=idx_val) for fav_data, idx_val in zip(favorite_data,
                                                                                        range(len(favorite_data)))]

            # Write favorites to lab book
            with open(os.path.join(favorites_dir, f'{target_sub_dir}.json'), 'wt') as f_data:
                json.dump(favorite_data, f_data)

            return favorite_data[result_index]
        except Exception as e:
            logger.exception(e)
            raise

    def remove_favorite(self, target_sub_dir: str, position: int) -> None:
        """Mark an existing file as a Favorite

        Args:
            target_sub_dir(str): lab book subdir where file exists (code, input, output)
            position(int): The position to insert the favorite. If omitted, will append.

        Returns:
            None
        """
        if target_sub_dir not in ['code', 'input', 'output']:
            raise ValueError("Favorites only supported in `code`, `input`, and `output` Lab Book directories")

        try:
            # Open existing Favorites json if exists
            favorites_dir = os.path.join(self.root_dir, '.gigantum', 'favorites')
            if not os.path.exists(favorites_dir):
                # No favorites have been created
                raise ValueError(f"No favorites have been created yet. Cannot remove item {position}!")

            favorite_data: List[Dict[str, Any]] = []
            if os.path.exists(os.path.join(favorites_dir, f'{target_sub_dir}.json')):
                # Read existing data
                with open(os.path.join(favorites_dir, f'{target_sub_dir}.json'), 'rt') as f_data:
                    favorite_data = json.load(f_data)

            if position >= len(favorite_data):
                raise ValueError("Invalid index to remove favorite")
            if position < 0:
                raise ValueError("Invalid index to remove favorite")

            # Remove favorite at index value
            del favorite_data[position]

            # Add index values
            favorite_data = [dict(fav_data, index=idx_val) for fav_data, idx_val in zip(favorite_data,
                                                                                        range(len(favorite_data)))]

            # Write favorites to back lab book
            with open(os.path.join(favorites_dir, f'{target_sub_dir}.json'), 'wt') as f_data:
                json.dump(favorite_data, f_data)

            logger.info(f"Removed {target_sub_dir} favorite #{position}")

            return None
        except Exception as e:
            logger.exception(e)
            raise

    def get_favorites(self, target_sub_dir: str) -> List[Optional[Dict[str, Any]]]:
        """Get Favorite data

        Args:
            target_sub_dir(str): lab book subdir where file exists (code, input, output)

        Returns:
            None
        """
        if target_sub_dir not in ['code', 'input', 'output']:
            raise ValueError("Favorites only supported in `code`, `input`, and `output` Lab Book directories")

        favorite_data: List[Optional[Dict[str, Any]]] = []
        favorites_dir = os.path.join(self.root_dir, '.gigantum', 'favorites')
        if os.path.exists(os.path.join(favorites_dir, f'{target_sub_dir}.json')):
            # Read existing data
            with open(os.path.join(favorites_dir, f'{target_sub_dir}.json'), 'rt') as f_data:
                favorite_data = json.load(f_data)

        return favorite_data

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
            "owner": owner,
            "schema": self.LABBOOK_DATA_SCHEMA_VERSION
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

    def rename(self, new_name: str) -> None:
        """Method to rename a labbook

        Args:
            new_name(str): New desired labbook name

        Returns:
            None
        """
        # TODO Grab LabBook Lock

        # Make sure name does not already exist
        labbooks_dir = self.root_dir.rsplit(os.path.sep, 1)[0]
        if os.path.exists(os.path.join(labbooks_dir, new_name)):
            raise ValueError(f"New LabBook name '{new_name}' already exists")

        try:
            # Rename labbook directory to new directory and update YAML file
            old_name = self.name
            self.name = new_name

            # Commit Change
            self.git.add(os.path.join(self.root_dir, ".gigantum", "labbook.yaml"))
            commit = self.git.commit(f"Renamed LabBook '{old_name}' to '{new_name}'")

            # Add Activity record
            ns = NoteStore(self)
            ns.create_note({
                'linked_commit': commit.hexsha,
                'message': f"Renamed LabBook '{old_name}' to '{new_name}'",
                'level': NoteLogLevel.USER_MAJOR,
                'tags': ['rename'],
                'free_text': '',
                'objects': ''
            })
        finally:
            # TODO: Release LabBook lock
            pass

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
        self._load_labbook_data()

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

