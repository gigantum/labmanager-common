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
import pytest
import tempfile
import os
import shutil
import uuid
from ...gitlib import GitFilesystem
from git import Repo


# Required Fixtures:
#   - mock_config: a standard config with an empty working dir

# GitFilesystem Fixtures
@pytest.fixture()
def mock_config_filesystem():
    # Create temporary working directory
    working_dir = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
    os.makedirs(working_dir)

    config = {"backend": "filesystem", "working_directory": working_dir}

    yield config  # provide the fixture value

    # Force delete the directory
    shutil.rmtree(working_dir)


def create_dummy_repo(working_dir):
    """Helper method to create a dummy repo with a file in it"""
    filename = "dummy.txt"
    repo = Repo.init(working_dir)
    with open(os.path.join(working_dir, filename), 'wt') as dt:
        dt.write("entry 1")

    repo.index.add([os.path.join(working_dir, filename)])
    repo.index.commit("initial commit")


class GitInterfaceMixin(object):
    """Mixin to test the GitInterface"""
    def test_empty_dir(self, mock_config):
        """Test trying to get the filesystem interface"""
        git = GitFilesystem(mock_config)
        assert type(git) is GitFilesystem
        assert git.repo is None

    def test_existing_repo(self, mock_config):
        """Test trying to load an existing repo dir"""
        # Create a repo in the working dir
        create_dummy_repo(mock_config["working_directory"])

        # Create a GitFilesystem instance
        git = GitFilesystem(mock_config)
        assert type(git) is GitFilesystem
        assert type(git.repo) is Repo

    def test_clone_repo(self, mock_config):
        """Test trying to clone an existing repo dir"""
        git = GitFilesystem(mock_config)

        git.clone('https://github.com/gigantum/gigantum.github.io.git')
        assert git.get_current_branch_name() == "master"
        assert os.path.isfile(os.path.join(mock_config["working_directory"], "index.html")) is True

    def test_status(self, mock_config):
        """Test getting the status of a repo as it is manipulated"""
        # Create a repo in the working dir
        create_dummy_repo(mock_config["working_directory"])

        # Create a GitFilesystem instance
        git = GitFilesystem(mock_config)

        # Create a complex repo with all possible states to check

        # Add a normal committed file
        with open(os.path.join(mock_config["working_directory"], "committed.txt"), 'wt') as dt:
            dt.write("entry asdf")
        git.repo.index.add([os.path.join(mock_config["working_directory"], "committed.txt")])
        git.repo.index.commit("initial commit")

        # Add a deleted file
        with open(os.path.join(mock_config["working_directory"], "deleted.txt"), 'wt') as dt:
            dt.write("entry sadfasdf")
        git.repo.index.add([os.path.join(mock_config["working_directory"], "deleted.txt")])
        git.repo.index.commit("delete file commit")
        os.remove(os.path.join(mock_config["working_directory"], "deleted.txt"))

        # Add a staged and edited file
        with open(os.path.join(mock_config["working_directory"], "staged_edited.txt"), 'wt') as dt:
            dt.write("entry 1")
        git.repo.index.add([os.path.join(mock_config["working_directory"], "staged_edited.txt")])
        git.repo.index.commit("edited initial")
        with open(os.path.join(mock_config["working_directory"], "staged_edited.txt"), 'wt') as dt:
            dt.write("entry edited")
        git.repo.index.add([os.path.join(mock_config["working_directory"], "staged_edited.txt")])

        # Add a staged file
        with open(os.path.join(mock_config["working_directory"], "staged.txt"), 'wt') as dt:
            dt.write("entry staged")
        git.repo.index.add([os.path.join(mock_config["working_directory"], "staged.txt")])

        # Add an unstaged edited file
        with open(os.path.join(mock_config["working_directory"], "unstaged_edited.txt"), 'wt') as dt:
            dt.write("entry 2")
        git.repo.index.add([os.path.join(mock_config["working_directory"], "unstaged_edited.txt")])
        with open(os.path.join(mock_config["working_directory"], "unstaged_edited.txt"), 'wt') as dt:
            dt.write("entry 2 edited")

        # Add an untracked file
        with open(os.path.join(mock_config["working_directory"], "untracked.txt"), 'wt') as dt:
            dt.write("entry untracked")

        # Stage a file in a sub-directory
        subdir = os.path.join(mock_config["working_directory"], "subdir")
        os.makedirs(subdir)
        with open(os.path.join(subdir, "subdir_file.txt"), 'wt') as dt:
            dt.write("entry subdir")
        git.repo.index.add([os.path.join(subdir, "subdir_file.txt")])

        # Check status clean
        status = git.status()

        assert "staged" in status
        assert status["staged"][0] == ('staged.txt', 'new')
        assert status["staged"][1] == ('staged_edited.txt', 'modified')
        assert status["staged"][2] == ('subdir/subdir_file.txt', 'new')
        assert status["staged"][3] == ('unstaged_edited.txt', 'new')

        assert "unstaged" in status
        assert status["unstaged"][0] == ('deleted.txt', 'deleted')
        assert status["unstaged"][1] == ('unstaged_edited.txt', 'modified')

        assert "untracked" in status
        assert status["untracked"] == ["untracked.txt"]

        assert len(status["staged"]) == 4
        assert len(status["unstaged"]) == 2
        assert len(status["untracked"]) == 1

    
