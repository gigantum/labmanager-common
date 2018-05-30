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
from typing import Any
import tempfile
import os
import shutil
import uuid
import datetime
from lmcommon.gitlib import GitFilesystem, GitFilesystemShimmed, GitAuthor
from git import Repo
from git.exc import GitCommandError


def get_backend():
    return os.environ['GITLIB_FS_BACKEND']

def get_fs_class():
    if get_backend() == 'filesystem':
        return GitFilesystem
    elif get_backend() == 'filesystem-shim':
        return GitFilesystemShimmed
    else:
        raise NotImplementedError('Invalid FS class')

# Required Fixtures:
#   - mock_config: a standard config with an empty working dir
#   - mock_initialized: a gitlib instance initialized with an empty repo
#   - mock_initialized_remote: a gitlib instance initialized with an empty repo and create bare repo

# GitFilesystem Fixtures
@pytest.fixture()
def mock_config_filesystem():
    # Create temporary working directory
    working_dir = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
    os.makedirs(working_dir)

    config = {"backend": get_backend(), "working_directory": working_dir}

    yield config  # provide the fixture value

    # Force delete the directory
    shutil.rmtree(working_dir)


@pytest.fixture()
def mock_initialized_filesystem():
    """Create an initialized git lib instance

    Returns:
        (gitlib.git.GitRepoInterface, str): the instance, the working dir
    """
    # Create temporary working directory
    working_dir = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
    os.makedirs(working_dir)

    config = {"backend": get_backend(), "working_directory": working_dir}

    # Init the empty repo
    create_dummy_repo(working_dir)
    git = get_fs_class()(config)

    yield git, working_dir  # provide the fixture value

    # Force delete the directory
    shutil.rmtree(working_dir)


@pytest.fixture()
def mock_initialized_filesystem_with_remote():
    """Create an initialized git lib instance and also create a bare initialized repo

        returns a clone of the repo on master, the working dir for that repo, the bare repo, and the working bare dir

    Returns:
        (gitlib.git.GitRepoInterface, str, gitlib.git.GitRepoInterface, str)
    """
    # Create temporary working directory for the bare repo
    bare_working_dir = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
    os.makedirs(bare_working_dir)
    bare_repo = Repo.init(bare_working_dir, bare=True)
    populate_bare_repo(bare_working_dir)

    # Create temporary working directory
    working_dir = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
    os.makedirs(working_dir)

    config = {"backend": get_backend(), "working_directory": working_dir}

    # Init the empty repo
    git = get_fs_class()(config)
    git.clone(bare_working_dir)

    yield git, working_dir, bare_repo, bare_working_dir  # provide the fixture value

    # Force delete the directory
    shutil.rmtree(bare_working_dir)
    shutil.rmtree(working_dir)


def populate_bare_repo(working_dir):
    """Method to populate the bare repo with a branch, files, and tag"""
    # Create a local repo so we can manipulate the remote
    scratch_working_dir = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
    os.makedirs(scratch_working_dir)
    config = {"backend": get_backend(), "working_directory": scratch_working_dir}

    # Init the empty repo
    git = get_fs_class()(config)
    git.clone(working_dir)

    # Add a file to master and commit
    write_file(git, "test1.txt", "Original Content", commit_msg="initial commit")
    git.repo.remotes.origin.push()

    # Create a branch from master
    new_branch = git.repo.create_head("test_branch", git.repo.refs.master)
    git.repo.head.set_reference(new_branch)
    write_file(git, "test2.txt", "Original Content", commit_msg="second commit")
    git.repo.remotes.origin.push("test_branch")

    # Tag
    tag = git.repo.create_tag("test_tag_1", message="a test tag")
    git.repo.remotes.origin.push(tag)

    # Check master back out
    git.repo.heads.master.checkout()

    # Delete temp dir
    shutil.rmtree(scratch_working_dir)


def create_dummy_repo(working_dir):
    """Helper method to create a dummy repo with a file in it"""
    filename = "dummy.txt"
    repo = Repo.init(working_dir)
    with open(os.path.join(working_dir, filename), 'wt') as dt:
        dt.write("entry 1")

    repo.index.add([os.path.join(working_dir, filename)])
    repo.index.commit("initial commit")


def write_file(git_instance, filename, content, add=True, commit_msg=None):
    """Write content to a file

    Args:
        filename(str): The relative file path from the working dir
        content(str): What to write
        add(bool): If true, ddd to git repo
        commit_msg (str): If not none, commit file with this message

    Returns:

    """
    working_dir = git_instance.config["working_directory"]
    with open(os.path.join(working_dir, filename), 'wt') as dt:
        dt.write(content)

    if add:
        git_instance.add(os.path.join(working_dir, filename))

    if commit_msg:
        git_instance.commit(commit_msg)


class GitInterfaceMixin(object):
    """Mixin to test the GitInterface"""
    class_type: Any = None

    def get_git_obj(self, config):
        raise NotImplemented

    def test_empty_dir(self, mock_config):
        """Test trying to get the filesystem interface"""
        git = self.get_git_obj(mock_config)
        assert type(git) is self.class_type
        assert git.repo is None

    def test_existing_repo(self, mock_config):
        """Test trying to load an existing repo dir"""
        # Create a repo in the working dir
        create_dummy_repo(mock_config["working_directory"])

        # Create a GitFilesystem instance
        git = self.get_git_obj(mock_config)
        assert type(git) is self.class_type
        assert type(git.repo) is Repo

    def test_update_working_directory(self, mock_config):
        """Test trying to load an existing repo dir"""
        # Create a repo in the working dir
        create_dummy_repo(mock_config["working_directory"])

        # Create a GitFilesystem instance
        git = self.get_git_obj(mock_config)
        assert type(git) is self.class_type
        assert type(git.repo) is Repo
        assert git.working_directory == mock_config["working_directory"]

        new_working_dir = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
        os.makedirs(new_working_dir)
        git.set_working_directory(new_working_dir)

        assert git.repo is None
        assert git.working_directory == new_working_dir

        git.initialize()
        assert type(git.repo) is Repo

        shutil.rmtree(new_working_dir)

    def test_clone_repo(self, mock_initialized_remote):
        """Test trying to clone an existing repo dir"""
        scratch_working_dir = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
        os.makedirs(scratch_working_dir)
        config = {"backend": get_backend(), "working_directory": scratch_working_dir}

        git = self.get_git_obj(config)
        git.clone(mock_initialized_remote[3])

        assert len(git.repo.heads) == 1
        assert len(git.repo.remotes["origin"].fetch()) == 2
        assert len(git.repo.refs) == 5

        # Make sure only master content
        assert os.path.isfile(os.path.join(scratch_working_dir, 'test1.txt')) is True
        assert os.path.isfile(os.path.join(scratch_working_dir, 'test2.txt')) is False

        # Delete temp dir
        shutil.rmtree(scratch_working_dir)

    def test_author_invalid(self, mock_initialized):
        """Test changing the git author info"""
        git = mock_initialized[0]

        with pytest.raises(ValueError):
            git.update_author('Test User')

        with pytest.raises(ValueError):
            git.update_author('Test User 1', committer='Test User 2')

        with pytest.raises(ValueError):
            git.update_author('Test User 1', committer=GitAuthor("Author", "a@test.com"))

        with pytest.raises(ValueError):
            git.update_author(GitAuthor("Author", "a@test.com"), committer="Test User 2")

    def test_author(self, mock_initialized):
        """Test changing the git author info"""
        git = mock_initialized[0]

        # Test defaults
        assert type(git.author) == GitAuthor
        assert type(git.committer) == GitAuthor
        assert git.author.name == "Gigantum AutoCommit"
        assert git.author.email == "noreply@gigantum.io"
        assert git.committer.name == "Gigantum AutoCommit"
        assert git.committer.email == "noreply@gigantum.io"

        # Test updating just author
        git.update_author(GitAuthor("New Name", "test@test.com"))
        assert git.author.name == "New Name"
        assert git.author.email == "test@test.com"
        assert git.committer.name == "Gigantum AutoCommit"
        assert git.committer.email == "noreply@gigantum.io"

        # Test updating both
        git.update_author(GitAuthor("Author", "a@test.com"), GitAuthor("Committer", "c@test.com"))
        assert git.author.name == "Author"
        assert git.author.email == "a@test.com"
        assert git.committer.name == "Committer"
        assert git.committer.email == "c@test.com"

    def test_status(self, mock_config):
        """Test getting the status of a repo as it is manipulated"""
        # Create a repo in the working dir
        create_dummy_repo(mock_config["working_directory"])

        # Create a GitFilesystem instance
        git = self.get_git_obj(mock_config)

        # Create a complex repo with all possible states to check

        # Add a normal committed file
        write_file(git, "committed.txt", "File number 1\n", commit_msg="initial commit")

        # Add a deleted file
        write_file(git, "deleted.txt", "File number 2\n", commit_msg="delete file commit")
        os.remove(os.path.join(mock_config["working_directory"], "deleted.txt"))

        # Add a staged and edited file
        write_file(git, "staged_edited.txt", "entry 1", commit_msg="edited initial")
        write_file(git, "staged_edited.txt", "entry edited")

        # Add a staged file
        write_file(git, "staged.txt", "entry staged")

        # Add an unstaged edited file
        write_file(git, "unstaged_edited.txt", "entry 2")
        write_file(git, "unstaged_edited.txt", "entry 2 edited", add=False)

        # Add an untracked file
        write_file(git, "untracked.txt", "entry untracked", add=False)

        # Stage a file in a sub-directory
        subdir = os.path.join(mock_config["working_directory"], "subdir")
        os.makedirs(subdir)
        write_file(git, os.path.join(subdir, "subdir_file.txt"), "entry subdir")

        # Check status clean
        status = git.status()

        assert "staged" in status
        assert status["staged"][0] == ('staged.txt', 'added')
        assert status["staged"][1] == ('staged_edited.txt', 'modified')
        assert status["staged"][2] == ('subdir/subdir_file.txt', 'added')
        assert status["staged"][3] == ('unstaged_edited.txt', 'added')

        assert "unstaged" in status
        assert status["unstaged"][0] == ('deleted.txt', 'deleted')
        assert status["unstaged"][1] == ('unstaged_edited.txt', 'modified')

        assert "untracked" in status
        assert status["untracked"] == ["untracked.txt"]

        assert len(status["staged"]) == 4
        assert len(status["unstaged"]) == 2
        assert len(status["untracked"]) == 1

    def test_add(self, mock_initialized):
        """Test adding a file to a repository"""
        git = mock_initialized[0]
        working_directory = mock_initialized[1]

        print(f"mock_initialized={mock_initialized}")
        # Create file
        write_file(git, "add.txt", "entry 1", add=False)

        # Verify untracked
        status = git.status()

        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 1
        assert status["untracked"] == ["add.txt"]

        # Add file
        git.add(os.path.join(working_directory, "add.txt"))

        # Verify untracked
        status = git.status()

        assert len(status["staged"]) == 1
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 0
        assert status["staged"][0] == ("add.txt", 'added')

    def test_add_all_working_dir(self, mock_initialized):
        """Test adding all files and changes in the working directory"""
        git = mock_initialized[0]
        working_directory = mock_initialized[1]

        # Create files
        write_file(git, "file1.txt", "dsfgfghfghhsdf", commit_msg="first commit")
        write_file(git, "file2.txt", "34356234532453", commit_msg="second commit")

        # Create an untracked file, remove a file
        write_file(git, "file2.txt", "343562345324535656", add=False)
        write_file(git, "file3.txt", "jhgjhgffgdsfgdvdas", add=False)
        os.remove(os.path.join(working_directory, "file1.txt"))

        # Verify untracked
        status = git.status()

        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 2
        assert len(status["untracked"]) == 1
        assert status["untracked"] == ["file3.txt"]

        # Add file
        git.add_all()

        # Verify untracked
        status = git.status()

        assert len(status["staged"]) == 3
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 0
        assert status["staged"][0] == ("file1.txt", 'deleted')
        assert status["staged"][1] == ("file2.txt", 'modified')
        assert status["staged"][2] == ("file3.txt", 'added')

    def test_add_all_sub_dir(self, mock_initialized):
        """Test adding all files and changes in a sub directory of the working directory"""
        git = mock_initialized[0]
        working_directory = mock_initialized[1]

        os.makedirs(os.path.join(working_directory, "env"))

        # Create files
        write_file(git, os.path.join("untracked.txt"), "4545", add=False)
        write_file(git, os.path.join('env', "file1.txt"), "dsfgfghfghhsdf", commit_msg="first commit")
        write_file(git, os.path.join('env', "file2.txt"), "34356234532453", commit_msg="second commit")

        # Create an untracked file, remove a file
        write_file(git, os.path.join('env', "file2.txt"), "343562345324535656", add=False)
        write_file(git, os.path.join('env', "file3.txt"), "jhgjhgffgdsfgdvdas", add=False)
        os.remove(os.path.join(working_directory, 'env', "file1.txt"))

        # Verify untracked
        status = git.status()

        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 2
        assert len(status["untracked"]) == 2
        assert status["untracked"] == ["env/file3.txt", "untracked.txt"]

        # Add file
        git.add_all("env")

        # Verify untracked
        status = git.status()

        assert len(status["staged"]) == 3
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 1
        assert status["staged"][0] == ("env/file1.txt", 'deleted')
        assert status["staged"][1] == ("env/file2.txt", 'modified')
        assert status["staged"][2] == ("env/file3.txt", 'added')

    def test_remove_staged_file(self, mock_initialized):
        """Test removing files from a repository"""
        git = mock_initialized[0]
        working_directory = mock_initialized[1]

        # Create file
        write_file(git, "staged.txt", "entry 1")

        # Verify staged
        status = git.status()
        assert len(status["staged"]) == 1
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 0
        assert status["staged"][0] == ("staged.txt", 'added')

        # Remove
        git.remove(os.path.join(working_directory, "staged.txt"))
        # Verify removed
        status = git.status()
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 1
        assert status["untracked"] == ["staged.txt"]

    def test_remove_committed_file(self, mock_initialized):
        """Test removing files from a repository"""
        git = mock_initialized[0]
        working_directory = mock_initialized[1]

        # Create file
        write_file(git, "staged.txt", "entry 1", commit_msg="Test commit")

        # Verify nothing staged
        status = git.status()
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 0

        # Remove
        git.remove(os.path.join(working_directory, "staged.txt"))
        # Verify removed
        status = git.status()
        assert len(status["staged"]) == 1
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 1
        assert status["untracked"] == ["staged.txt"]
        assert status["staged"][0] == ("staged.txt", "deleted")

    def test_remove_committed_file_delete(self, mock_initialized):
        """Test removing file from a repository and delete it"""
        git = mock_initialized[0]
        working_directory = mock_initialized[1]

        # Create file
        write_file(git, "staged.txt", "entry 1", commit_msg="Test commit")

        # Verify nothing staged
        status = git.status()
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 0

        # Remove
        git.remove(os.path.join(working_directory, "staged.txt"), keep_file=False)
        # Verify removed
        status = git.status()
        assert len(status["staged"]) == 1
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 0
        assert status["staged"][0] == ("staged.txt", "deleted")

    def test_diff_unstaged(self, mock_initialized):
        """Test getting the diff for unstaged changes"""
        git = mock_initialized[0]
        working_directory = mock_initialized[1]

        # Create files
        with open(os.path.join(working_directory, "test.txt"), 'wt') as dt:
            dt.write("Line Top\n")
            for val in range(0, 30):
                dt.write("Line {}\n".format(val))
            dt.write("Line Bottom\n")
        with open(os.path.join(working_directory, "test2.txt"), 'wt') as dt:
            dt.write("File number 2\n")
        git.add(os.path.join(working_directory, "test.txt"))
        git.add(os.path.join(working_directory, "test2.txt"))
        git.repo.index.commit("commit 1")

        # Edit file 1 - Add a line
        with open(os.path.join(working_directory, "test.txt"), 'wt') as dt:
            dt.write("Line Top Has Changed\n")
            for val in range(0, 30):
                dt.write("Line {}\n".format(val))
            dt.write("Line Bottom Has Changed\n")

        # Edit file 2
        with open(os.path.join(working_directory, "test2.txt"), 'wt') as dt:
            dt.write("File number 2 changed\n")

        diff_info = git.diff_unstaged()

        assert len(diff_info.keys()) == 2
        assert "test.txt" in diff_info
        assert len(diff_info["test.txt"]) == 2
        assert "test2.txt" in diff_info
        assert len(diff_info["test2.txt"]) == 1

    def test_diff_unstaged_file(self, mock_initialized):
        """Test getting the diff of a file that has been changed"""
        git = mock_initialized[0]
        working_directory = mock_initialized[1]

        # Create files
        with open(os.path.join(working_directory, "test.txt"), 'wt') as dt:
            dt.write("Line Top\n")
            for val in range(0, 30):
                dt.write("Line {}\n".format(val))
            dt.write("Line Bottom\n")
        with open(os.path.join(working_directory, "test2.txt"), 'wt') as dt:
            dt.write("File number 2\n")
        git.add(os.path.join(working_directory, "test.txt"))
        git.add(os.path.join(working_directory, "test2.txt"))
        git.repo.index.commit("commit 1")

        # Edit file 1 - Add a line
        with open(os.path.join(working_directory, "test.txt"), 'wt') as dt:
            dt.write("Line Top Has Changed\n")
            for val in range(0, 30):
                dt.write("Line {}\n".format(val))
            dt.write("Line Bottom Has Changed\n")

        # Edit file 2
        with open(os.path.join(working_directory, "test2.txt"), 'wt') as dt:
            dt.write("File number 2 changed\n")

        diff_info = git.diff_unstaged("test.txt")

        assert len(diff_info.keys()) == 1
        assert "test.txt" in diff_info
        assert len(diff_info["test.txt"]) == 2

    def test_diff_staged(self, mock_initialized):
        """Test getting the diff for staged changes"""
        git = mock_initialized[0]
        working_directory = mock_initialized[1]

        # Create files
        with open(os.path.join(working_directory, "test.txt"), 'wt') as dt:
            dt.write("Line Top\n")
            for val in range(0, 30):
                dt.write("Line {}\n".format(val))
            dt.write("Line Bottom\n")
        with open(os.path.join(working_directory, "test2.txt"), 'wt') as dt:
            dt.write("File number 2\n")
        git.add(os.path.join(working_directory, "test.txt"))
        git.add(os.path.join(working_directory, "test2.txt"))
        git.repo.index.commit("commit 1")

        # Edit file 1 - Add a line
        with open(os.path.join(working_directory, "test.txt"), 'wt') as dt:
            dt.write("Line Top Has Changed\n")
            for val in range(0, 30):
                dt.write("Line {}\n".format(val))
            dt.write("Line Bottom Has Changed\n")

        # Edit file 2
        with open(os.path.join(working_directory, "test2.txt"), 'wt') as dt:
            dt.write("File number 2 changed\n")

        git.add(os.path.join(working_directory, "test.txt"))
        git.add(os.path.join(working_directory, "test2.txt"))

        diff_info = git.diff_staged()

        assert len(diff_info.keys()) == 2
        assert "test.txt" in diff_info
        assert len(diff_info["test.txt"]) == 2
        assert "test2.txt" in diff_info
        assert len(diff_info["test2.txt"]) == 1

    def test_diff_staged_file(self, mock_initialized):
        """Test getting the diff of a file that has been changed and staged"""
        git = mock_initialized[0]
        working_directory = mock_initialized[1]

        # Create file
        with open(os.path.join(working_directory, "test.txt"), 'wt') as dt:
            dt.write("Line Top\n")
            for val in range(0, 30):
                dt.write("Line {}\n".format(val))
            dt.write("Line Bottom\n")
        with open(os.path.join(working_directory, "test2.txt"), 'wt') as dt:
            dt.write("File number 2\n")
        git.add(os.path.join(working_directory, "test.txt"))
        git.add(os.path.join(working_directory, "test2.txt"))
        git.repo.index.commit("commit 1")

        # Edit file 1 - Add a line
        with open(os.path.join(working_directory, "test.txt"), 'wt') as dt:
            dt.write("Line Top Has Changed\n")
            for val in range(0, 30):
                dt.write("Line {}\n".format(val))
            dt.write("Line Bottom Has Changed\n")

        # Edit file 2
        with open(os.path.join(working_directory, "test2.txt"), 'wt') as dt:
            dt.write("File number 2 changed\n")

        git.add(os.path.join(working_directory, "test.txt"))
        git.add(os.path.join(working_directory, "test2.txt"))

        diff_info = git.diff_staged("test.txt")

        assert len(diff_info.keys()) == 1
        assert "test.txt" in diff_info
        assert len(diff_info["test.txt"]) == 2

    def test_diff_commits(self, mock_initialized):
        """Test getting the diff between commits in a branch"""
        git = mock_initialized[0]
        working_directory = mock_initialized[1]

        # Create files
        write_file(git, "test1.txt", "File number 1\n")
        write_file(git, "test2.txt", "File number 2\n", commit_msg="commit 1")
        commit1 = git.repo.head.commit

        # Edit file 1 - Add a line
        write_file(git, "test1.txt", "File number 1 has changed\n", commit_msg="commit 2")
        commit2 = git.repo.head.commit

        # Edit file 2
        write_file(git, "test2.txt", "File number 2 has changed\n", commit_msg="commit 3")
        commit3 = git.repo.head.commit

        # Create another file
        write_file(git, "test3.txt", "File number 3\n", commit_msg="commit 4")
        commit4 = git.repo.head.commit

        # Diff with defaults (HEAD compared to previous commit)
        diff_info = git.diff_commits()

        assert len(diff_info.keys()) == 1
        assert "test3.txt" in diff_info
        assert len(diff_info["test3.txt"]) == 1

        # Diff HEAD with first commit
        diff_info = git.diff_commits(commit_a=commit1.hexsha)

        assert len(diff_info.keys()) == 3
        assert "test1.txt" in diff_info
        assert "test2.txt" in diff_info
        assert "test3.txt" in diff_info
        assert len(diff_info["test1.txt"]) == 1
        assert len(diff_info["test2.txt"]) == 1
        assert len(diff_info["test3.txt"]) == 1

        # Diff two middle commits
        diff_info = git.diff_commits(commit_a=commit2.hexsha, commit_b=commit3.hexsha)

        assert len(diff_info.keys()) == 1
        assert "test2.txt" in diff_info
        assert len(diff_info["test2.txt"]) == 1

    def test_commit(self, mock_initialized):
        """Test making a commit"""
        git = mock_initialized[0]
        working_directory = mock_initialized[1]

        # Create files
        write_file(git, "test1.txt", "File number 1\n")

        subdir = os.path.join(working_directory, "subdir")
        os.makedirs(subdir)
        write_file(git, os.path.join(subdir, "subdir_file.txt"), "entry subdir")

        write_file(git, "untracked.txt", "Untracked File", add=False)

        status = git.status()
        assert len(status["staged"]) == 2
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 1
        assert status["untracked"] == ["untracked.txt"]
        assert status["staged"][1] == ("test1.txt", "added")
        assert status["staged"][0] == (os.path.join("subdir", "subdir_file.txt"), "added")

        # Make commit
        git.commit("commit 1")

        # Verify
        status = git.status()
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 1
        assert status["untracked"] == ["untracked.txt"]

        assert git.repo.head.commit.message == "commit 1"
        assert git.repo.head.commit.author.name == "Gigantum AutoCommit"
        assert git.repo.head.commit.author.email == "noreply@gigantum.io"

    def test_commit_with_author(self, mock_initialized):
        """Test making a commit"""
        git = mock_initialized[0]

        # Create files
        write_file(git, "test1.txt", "File number 1\n")

        status = git.status()
        assert len(status["staged"]) == 1
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 0
        assert status["staged"][0] == ("test1.txt", "added")

        # Make commit
        git.commit("commit message test",
                   author=GitAuthor("Test User 1", "user@gigantum.io"),
                   committer=GitAuthor("Test User 2", "user2@gigantum.io"))

        # Verify
        status = git.status()
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 0

        assert git.repo.head.commit.message == "commit message test"
        assert git.repo.head.commit.author.name == "Test User 1"
        assert git.repo.head.commit.author.email == "user@gigantum.io"
        assert git.repo.head.commit.committer.name == "Test User 2"
        assert git.repo.head.commit.committer.email == "user2@gigantum.io"
        assert git.author.__dict__ == GitAuthor("Test User 1", "user@gigantum.io").__dict__
        assert git.committer.__dict__ == GitAuthor("Test User 2", "user2@gigantum.io").__dict__

    def test_log(self, mock_initialized):
        """Test getting commit history"""
        git = mock_initialized[0]

        # Create files
        commit_list = []
        write_file(git, "test1.txt", "File number 1\n", commit_msg="commit 1")
        commit_list.append(git.repo.head.commit)

        write_file(git, "test2.txt", "File number 2\n", commit_msg="commit 2")
        commit_list.append(git.repo.head.commit)

        # Edit file 1 - Add a line
        write_file(git, "test1.txt", "File 1 has changed\n", commit_msg="commit 3")
        commit_list.append(git.repo.head.commit)

        # Edit file 2
        write_file(git, "test2.txt", "File 2 has changed\n", commit_msg="commit 4")
        commit_list.append(git.repo.head.commit)

        # Create another file
        write_file(git, "test3.txt", "File number 3\n")
        git.commit("commit 5", author=GitAuthor("U1", "test@gigantum.io"),
                   committer=GitAuthor("U2", "test2@gigantum.io"))
        commit_list.append(git.repo.head.commit)

        # Get history
        log_info = git.log()

        assert len(log_info) == 6
        # Check, reverse commit_list and drop last commit from log (which was the initial commit in the
        # setup fixture). This orders from most recent to least and checks
        for truth, log in zip(reversed(commit_list), log_info[:-1]):
            assert log["author"] == {"name": truth.author.name, "email": truth.author.email}
            assert log["committer"] == {"name": truth.committer.name, "email": truth.committer.email}
            assert log["message"] == truth.message
            assert log["commit"] == truth.hexsha

        # Get history for a single file
        log_info = git.log(filename="test2.txt")

        assert len(log_info) == 2
        log_info[0]["message"] = "commit 4"
        log_info[1]["message"] = "commit 2"

    def test_log_page(self, mock_initialized):
        """Test getting commit history"""
        git = mock_initialized[0]

        # Create files
        commit_list = []
        write_file(git, "test1.txt", "File number 1\n", commit_msg="commit 1")
        commit_list.append(git.repo.head.commit)

        write_file(git, "test2.txt", "File number 2\n", commit_msg="commit 2")
        commit_list.append(git.repo.head.commit)

        # Edit file 1 - Add a line
        write_file(git, "test1.txt", "File 1 has changed\n", commit_msg="commit 3")
        commit_start = git.repo.head.commit
        commit_list.append(git.repo.head.commit)

        # Edit file 2
        write_file(git, "test2.txt", "File 2 has changed\n", commit_msg="commit 4")
        commit_list.append(git.repo.head.commit)

        # Create another file
        write_file(git, "test3.txt", "File number 3\n")
        git.commit("commit 5", author=GitAuthor("U1", "test@gigantum.io"),
                   committer=GitAuthor("U2", "test2@gigantum.io"))
        commit_list.append(git.repo.head.commit)

        # Get history
        log_info = git.log(path_info=commit_start)

        assert len(log_info) == 4
        assert commit_list[2].hexsha == commit_start.hexsha
        assert log_info[0]['commit'] == commit_list[2].hexsha
        assert log_info[1]['commit'] == commit_list[1].hexsha
        assert log_info[2]['commit'] == commit_list[0].hexsha

        # Get history
        log_info = git.log(path_info=commit_start, max_count=2)

        assert len(log_info) == 2
        assert commit_list[2].hexsha == commit_start.hexsha
        assert log_info[0]['commit'] == commit_list[2].hexsha
        assert log_info[1]['commit'] == commit_list[1].hexsha


    def test_log_filter(self, mock_initialized):
        """Test getting commit history with some filtering"""
        git = mock_initialized[0]

        # Create files
        commit_list = []
        write_file(git, "test1.txt", "File number 1\n", commit_msg="commit 1")
        commit_list.append(git.repo.head.commit)

        write_file(git, "test2.txt", "File number 2\n", commit_msg="commit 2")
        commit_list.append(git.repo.head.commit)

        # Edit file 1 - Add a line
        write_file(git, "test1.txt", "File 1 has changed\n", commit_msg="commit 3")
        commit_list.append(git.repo.head.commit)

        # Edit file 2
        write_file(git, "test2.txt", "File 2 has changed\n", commit_msg="commit 4")
        commit_list.append(git.repo.head.commit)

        # Create another file
        write_file(git, "test3.txt", "File number 3\n")
        git.commit("commit 5", author=GitAuthor("U1", "test@gigantum.io"),
                   committer=GitAuthor("U2", "test2@gigantum.io"))
        commit_list.append(git.repo.head.commit)

        # Get history, limit to 2
        log_info = git.log(max_count=2)

        assert len(log_info) == 2
        log_info[0]["message"] = "commit 5"
        log_info[1]["message"] = "commit 4"

        # Get history, limit to 2 and skip 2
        log_info = git.log(max_count=2, skip=2)

        assert len(log_info) == 2
        log_info[0]["message"] = "commit 3"
        log_info[1]["message"] = "commit 2"

        # Get history, limit to 1 day in the future
        log_info = git.log(since=datetime.datetime.now() + datetime.timedelta(days=1))
        assert len(log_info) == 0

        # Get history, limit to U1 author
        log_info = git.log(author="U1")
        assert len(log_info) == 1
        log_info[0]["message"] = "commit 5"

    def test_blame(self, mock_initialized):
        """Test getting blame history for a file"""
        git = mock_initialized[0]
        working_dir = mock_initialized[1]

        # Create files
        write_file(git, "test1.txt", "Write 1 by default\nWrite 2 by default\nWrite 3 by default\n", commit_msg="commit 1")
        commit1 = git.repo.head.commit

        with open(os.path.join(working_dir, "test1.txt"), 'at') as dt:
            dt.write("Write 1 by U1\n")
        git.add(os.path.join(working_dir, "test1.txt"))
        git.commit("commit 2", author=GitAuthor("U1", "test@gigantum.io"),
                   committer=GitAuthor("U2", "test2@gigantum.io"))
        commit2 = git.repo.head.commit

        with open(os.path.join(working_dir, "test1.txt"), 'at') as dt:
            dt.write("Write 4 by default\nWrite 5 by default\n")
        git.add(os.path.join(working_dir, "test1.txt"))
        git.commit("commit 3", author=GitAuthor("Gigantum AutoCommit", "noreply@gigantum.io"),
                   committer=GitAuthor("Gigantum AutoCommit", "noreply@gigantum.io"))
        commit3 = git.repo.head.commit

        # write second line
        with open(os.path.join(working_dir, "test1.txt"), 'wt') as dt:
            dt.write("Write 1 by default\nEDIT 2 by default\nWrite 3 by default\nWrite 1 by U1\nWrite 4 by default\nWrite 5 by default\n")
        git.add(os.path.join(working_dir, "test1.txt"))
        git.commit("commit 4")
        commit4 = git.repo.head.commit

        blame_info = git.blame("test1.txt")

        assert len(blame_info) == 5
        assert blame_info[0]["commit"] == commit1.hexsha
        assert blame_info[1]["commit"] == commit4.hexsha
        assert blame_info[2]["commit"] == commit1.hexsha
        assert blame_info[3]["commit"] == commit2.hexsha
        assert blame_info[4]["commit"] == commit3.hexsha

        assert blame_info[0]["author"]["name"] == "Gigantum AutoCommit"
        assert blame_info[1]["author"]["name"] == "Gigantum AutoCommit"
        assert blame_info[2]["author"]["name"] == "Gigantum AutoCommit"
        assert blame_info[3]["author"]["name"] == "U1"
        assert blame_info[4]["author"]["name"] == "Gigantum AutoCommit"

        assert blame_info[4]["content"] == "Write 4 by default\nWrite 5 by default"

    def test_create_branch(self, mock_initialized):
        """Method to test creating a branch"""
        git = mock_initialized[0]
        working_dir = mock_initialized[1]

        branches = git.repo.heads

        assert len(branches) == 1
        assert branches[0].name == "master"

        git.create_branch("test_branch1")

        branches = git.repo.heads
        assert len(branches) == 2
        assert branches[0].name == "master"
        assert branches[1].name == "test_branch1"

    def test_rename_branch(self, mock_initialized):
        """Method to test deleting a branch"""
        git = mock_initialized[0]

        branches = git.repo.heads
        assert len(branches) == 1
        assert branches[0].name == "master"

        git.create_branch("test_branch1")
        git.create_branch("test_branch2")

        branches = git.repo.heads
        assert len(branches) == 3
        assert branches[0].name == "master"
        assert branches[1].name == "test_branch1"
        assert branches[2].name == "test_branch2"

        # Rename branch
        git.rename_branch("test_branch2", "my_new_branch")

        branches = git.repo.heads
        assert len(branches) == 3
        assert branches[0].name == "master"
        assert branches[1].name == "my_new_branch"
        assert branches[2].name == "test_branch1"

        # Make sure invalid branch names raise an exception
        with pytest.raises(ValueError):
            git.rename_branch("a;lskjdfas;lkjhdf", "test2")

        # Rename checked out branch
        git.rename_branch("master", "new_master")
        branches = git.repo.heads
        assert len(branches) == 3
        assert branches[0].name == "my_new_branch"
        assert branches[1].name == "new_master"
        assert branches[2].name == "test_branch1"

    def test_checkout_branch(self, mock_initialized):
        """Method to test checkout a branch"""
        git = mock_initialized[0]


        assert git.repo.head.ref.name == "master"

        git.create_branch("test_branch1")

        import pprint
        pprint.pprint(git.repo.head.ref.name)

        # BVB NOTE!! I changed behavior so "create_branch" also checks out that new branch
        #assert git.repo.head.ref.name == "master"  # <-- Original behavior

        assert git.repo.head.ref.name == "test_branch1" # <-- New behavior following BVB changes

        # Checkout branch
        git.checkout("test_branch1")

        assert git.repo.head.ref.name == "test_branch1"

        # Make sure invalid branch names raise an exception
        with pytest.raises(ValueError):
            git.checkout("a;lskjdfas;lkjhdf")

    def test_checkout_branch_context(self, mock_initialized):
        """Method to test checkout context ID file getting removed """
        git = mock_initialized[0]

        assert git.repo.head.ref.name == "master"

        git.create_branch("test_branch1")

        assert git.repo.head.ref.name == "test_branch1"

        # Write a checkout context file for this test
        os.makedirs(os.path.join(git.working_directory, '.gigantum'))
        checkout_file = os.path.join(git.working_directory, '.gigantum', '.checkout')

        with open(checkout_file, 'wt') as cf:
            cf.write("dummy_id")
        assert os.path.exists(checkout_file) is True

        # Checkout branch
        git.checkout("test_branch1")

        assert os.path.exists(checkout_file) is False

    def test_list_branches(self, mock_initialized_remote):
        """Method to test listing branches"""
        git = mock_initialized_remote[0]

        git.create_branch("test_remote_branch")
        git.publish_branch("test_remote_branch")
        git.create_branch("test_local_branch")
        branches = git.list_branches()

        assert len(branches["local"]) == 3
        assert len(branches["remote"]) == 4
        assert "test_local_branch" in branches["local"]
        assert "test_remote_branch" in branches["local"]
        assert "origin/test_local_branch" not in branches["remote"]
        assert "origin/test_remote_branch" in branches["remote"]

    def test_delete_branch(self, mock_initialized_remote):
        """Method to test deleting branches"""
        git = mock_initialized_remote[0]

        git.create_branch("test_remote_branch")
        git.publish_branch("test_remote_branch")
        git.create_branch("test_local_branch")
        branches = git.list_branches()

        assert len(branches["local"]) == 3
        assert len(branches["remote"]) == 4

        # Delete local branch
        git.checkout("master")   # <-- BVB Note, this was added for change in create_branch semantics.
        git.delete_branch("test_local_branch")
        branches = git.list_branches()
        assert len(branches["local"]) == 2
        assert len(branches["remote"]) == 4

        # Delete remote branch, locally only
        git.checkout("master")
        git.delete_branch("test_remote_branch")
        branches = git.list_branches()
        assert len(branches["local"]) == 1
        assert branches["local"][0] == "master"
        assert len(branches["remote"]) == 4

        # Delete remote branch on remote
        git.delete_branch("test_remote_branch", delete_remote=True)
        branches = git.list_branches()
        assert len(branches["local"]) == 1
        assert branches["local"][0] == "master"
        assert len(branches["remote"]) == 3

    def test_existing_tag_fail(self, mock_initialized):
        """Method to test creating an existing tag, should fail"""
        git = mock_initialized[0]

        git.create_tag("test_tag_1", "test tag 1")

        # Should fail on an existing tag
        with pytest.raises(GitCommandError):
            git.create_tag("test_tag_1", "test tag 1 should fail!")

    def test_tags(self, mock_initialized):
        """Method to test creating and listing tags"""
        git = mock_initialized[0]

        # Test creating a new tag
        git.create_tag("tag1", "test tag 1")

        write_file(git, "test1.txt", "content", commit_msg="Adding a file")

        git.create_tag("tag2", "test tag 2")

        tags = git.list_tags()

        assert len(tags) == 2
        assert tags[0]["name"] == "tag1"
        assert tags[0]["message"] == "test tag 1"
        assert tags[1]["name"] == "tag2"
        assert tags[1]["message"] == "test tag 2"

    def test_add_remove_remote(self, mock_initialized_remote):
        """Method to test creating and listing tags"""
        scratch_working_dir = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
        os.makedirs(scratch_working_dir)
        config = {"backend": get_backend(), "working_directory": scratch_working_dir}

        # Init the empty repo
        git = get_fs_class()(config)
        git.initialize()
        remote_dir = mock_initialized_remote[3]

        git.add_remote("origin", remote_dir)

        remotes = git.list_remotes()

        assert len(remotes) == 1
        assert remotes[0]["name"] == "origin"
        assert remotes[0]["url"] == remote_dir

        git.remove_remote("origin")
        assert len(git.list_remotes()) == 0

        # Delete temp dir
        shutil.rmtree(scratch_working_dir)

    def test_publish_branch(self, mock_initialized_remote):
        """Method to test creating and listing tags"""
        # Get a clone of the remote repo
        git = mock_initialized_remote[0]

        branches = git.repo.heads
        assert len(branches) == 1
        assert branches[0].name == "master"

        # Create a branch
        git.create_branch("test_branch1")
        # Publish the branch
        git.publish_branch("test_branch1", "origin")

        branches = git.repo.heads
        assert len(branches) == 2
        assert branches[0].name == "master"
        assert branches[1].name == "test_branch1"

        # Create a new clone and make sure you got your branches
        test_working_dir = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
        os.makedirs(test_working_dir)
        test_repo = Repo.clone_from(mock_initialized_remote[3], test_working_dir)
        assert len(test_repo.remotes["origin"].fetch()) == 3

    def test_fetch_pull(self, mock_initialized_remote):
        """Method to fetch, pull from remote"""
        cloned_working_dir = mock_initialized_remote[1]

        # Get a clone of the remote repo
        git = mock_initialized_remote[0]
        assert len(git.repo.heads) == 1
        assert len(git.repo.remotes["origin"].fetch()) == 2
        assert len(git.repo.refs) == 5

        # Make sure only master content
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test1.txt')) is True
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test2.txt')) is False

        # check out a branch and pull it
        git.checkout("test_branch")
        git.pull()
        assert len(git.repo.heads) == 2

        # Make sure it pulled content
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test1.txt')) is True
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test2.txt')) is True

        # Add a file
        scratch_working_dir = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
        os.makedirs(scratch_working_dir)
        config = {"backend": get_backend(), "working_directory": scratch_working_dir}

        # Init the empty repo
        git_updater = get_fs_class()(config)
        git_updater.clone(mock_initialized_remote[3])
        git_updater.checkout("test_branch")

        # Add a file to master and commit
        write_file(git_updater, "test3.txt", "adding a new file Content", commit_msg="add commit")
        git_updater.repo.remotes.origin.push()

        # Make sure it pulled content
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test1.txt')) is True
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test2.txt')) is True
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test3.txt')) is False
        git.pull()
        # Make sure it pulled content
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test1.txt')) is True
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test2.txt')) is True
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test3.txt')) is True

        # Delete temp dir
        shutil.rmtree(scratch_working_dir)

    def test_push(self, mock_initialized_remote):
        """Method to test pushing to a remote"""
        cloned_working_dir = mock_initialized_remote[1]

        # Get a clone of the remote repo
        git = mock_initialized_remote[0]
        assert len(git.repo.heads) == 1
        assert len(git.repo.remotes["origin"].fetch()) == 2
        assert len(git.repo.refs) == 5

        # Make sure only master content
        git.checkout("master")
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test1.txt')) is True
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test2.txt')) is False

        # Add a file to master and commit
        write_file(git, "test3.txt", "adding a new file Content", commit_msg="add commit")
        git.push()

        # Make sure it pushed by cloning again content
        scratch_working_dir = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
        os.makedirs(scratch_working_dir)
        config = {"backend": get_backend(), "working_directory": scratch_working_dir}

        # Init the empty repo
        git_updater = get_fs_class()(config)
        git_updater.clone(mock_initialized_remote[3])
        git_updater.checkout("master")

        # Make sure it pulled content
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test1.txt')) is True
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test2.txt')) is False
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test3.txt')) is True

        # Delete temp dir
        shutil.rmtree(scratch_working_dir)

    def test_push_tags(self, mock_initialized_remote):
        """Method to test pushing to a remote"""
        cloned_working_dir = mock_initialized_remote[1]

        # Get a clone of the remote repo
        git = mock_initialized_remote[0]
        assert len(git.repo.heads) == 1
        assert len(git.repo.remotes["origin"].fetch()) == 2
        assert len(git.repo.refs) == 5

        # Add a file to master and commit
        write_file(git, "test3.txt", "adding a new file Content", commit_msg="add commit")
        git.push()

        # Add a tag
        git.create_tag("new_tag_1", "this is my test tag")

        # Check, tag should not be pushed yet.
        scratch_working_dir = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
        os.makedirs(scratch_working_dir)
        config = {"backend": get_backend(), "working_directory": scratch_working_dir}

        # Init the empty repo
        git_updater = get_fs_class()(config)
        git_updater.clone(mock_initialized_remote[3])
        git_updater.checkout("master")

        # Make sure it pulled content
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test1.txt')) is True
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test2.txt')) is False
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test3.txt')) is True

        # Check tags
        assert len(git_updater.list_tags()) == 1
        assert git_updater.list_tags()[0]["name"] == "test_tag_1"

        # Push Tag
        git.push(tags=True)

        # Fetch and check tags
        git_updater.fetch()
        assert len(git_updater.list_tags()) == 2
        assert git_updater.list_tags()[0]["name"] == "new_tag_1"

        # Delete temp dir
        shutil.rmtree(scratch_working_dir)

    def test_merge(self, mock_initialized_remote):
        """Method to test pushing to a remote"""
        cloned_working_dir = mock_initialized_remote[1]

        # Get a clone of the remote repo
        git = mock_initialized_remote[0]

        # Create and checkout a new branch
        git.create_branch("future_branch")
        git.checkout("future_branch")

        # Add a file to future branch and commit
        write_file(git, "test3.txt", "adding a new file Content", commit_msg="add commit")

        # Make sure data is there
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test1.txt')) is True
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test2.txt')) is False
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test3.txt')) is True

        # Checkout master
        git.checkout("master")

        # New file shouldn't be there
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test1.txt')) is True
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test2.txt')) is False
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test3.txt')) is False

        # Merge future branch into master
        git.merge("future_branch")

        # New file should be there
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test1.txt')) is True
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test2.txt')) is False
        assert os.path.isfile(os.path.join(cloned_working_dir, 'test3.txt')) is True

    def test_discard_changes(self, mock_initialized):
        """Test discarding all changes in a repo"""
        git = mock_initialized[0]
        working_directory = mock_initialized[1]

        # Create file
        write_file(git, "test_add1.txt", "entry 1", commit_msg="adding file 1")
        write_file(git, "test_add2.txt", "entry 2", commit_msg="adding file 2")

        # Verify Clean
        status = git.status()
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 0

        # Edit both files
        write_file(git, "test_add1.txt", "entry 1 updated", add=False)
        write_file(git, "test_add2.txt", "entry 2 updated", add=False)

        # Verify Edits exist
        status = git.status()
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 2
        assert len(status["untracked"]) == 0

        # Discard Single file change changes
        git.discard_changes("test_add2.txt")

        # Verify Edits gone
        status = git.status()
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 1
        assert status["unstaged"][0][0] == "test_add1.txt"
        assert len(status["untracked"]) == 0

        # Edit both files again
        write_file(git, "test_add1.txt", "entry 1 updated", add=False)
        write_file(git, "test_add2.txt", "entry 2 updated", add=False)

        # Verify Edits exist
        status = git.status()
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 2
        assert len(status["untracked"]) == 0

        # Discard All changes
        git.discard_changes()

        # Verify Edits gone
        status = git.status()
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 0

    def test_add_submodule(self, mock_initialized_remote):
        """Method to test pushing to a remote"""
        remote_working_dir = mock_initialized_remote[3]

        # Create a new repo
        scratch_working_dir = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
        os.makedirs(scratch_working_dir)
        config = {"backend": get_backend(), "working_directory": scratch_working_dir}
        git = get_fs_class()(config)
        git.initialize()
        write_file(git, "blah.txt", "blaaah", commit_msg="First commit")

        # List submodules
        assert len(git.list_submodules()) == 0

        # Add a submodule
        git.add_submodule("test_sub", "test", remote_working_dir)

        # List submodules
        assert len(git.list_submodules()) == 1
        sm = git.list_submodules()[0]
        assert sm["name"] == "test_sub"
        assert sm["url"] == remote_working_dir
        assert sm["branch"] == "master"

        # Should be clean
        status = git.status()
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 0
        assert os.path.isfile(os.path.join(scratch_working_dir, "test", 'test1.txt')) is True

        # Delete temp dir
        shutil.rmtree(scratch_working_dir)

    def test_remove_submodule(self, mock_initialized_remote):
        """Method to test pushing to a remote"""
        remote_working_dir = mock_initialized_remote[3]

        # Create a new repo
        scratch_working_dir = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
        os.makedirs(scratch_working_dir)
        config = {"backend": get_backend(), "working_directory": scratch_working_dir}
        git = get_fs_class()(config)
        git.initialize()
        write_file(git, "blah.txt", "blaaah", commit_msg="First commit")

        # List submodules
        assert len(git.list_submodules()) == 0

        # Add a submodule
        git.add_submodule("test_sub", "test", remote_working_dir)

        # List submodules
        assert len(git.list_submodules()) == 1
        sm = git.list_submodules()[0]
        assert sm["name"] == "test_sub"
        assert sm["url"] == remote_working_dir
        assert sm["branch"] == "master"

        # Should be clean
        status = git.status()
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 0
        assert os.path.isfile(os.path.join(scratch_working_dir, "test", 'test1.txt')) is True

        # Delete the submodule reference
        git.remove_submodules("test_sub")

        # Should be clean and data should be gone
        status = git.status()
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 0
        assert os.path.isfile(os.path.join(scratch_working_dir, "test", 'test1.txt')) is False

        # Delete temp dir
        shutil.rmtree(scratch_working_dir)
