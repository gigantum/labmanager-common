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
import datetime
from ...gitlib import GitFilesystem, GitAuthor
from git import Repo


# Required Fixtures:
#   - mock_config: a standard config with an empty working dir
#   - mock_initialized: a gitlib instance initialized with an empty repo

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


@pytest.fixture()
def mock_initialized_filesystem():
    """Create an initialized git lib instance

    Returns:
        (gitlib.git.GitRepoInterface, str): the instance, the working dir
    """
    # Create temporary working directory
    working_dir = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
    os.makedirs(working_dir)

    config = {"backend": "filesystem", "working_directory": working_dir}

    # Init the empty repo
    create_dummy_repo(working_dir)
    git = GitFilesystem(config)

    yield git, working_dir  # provide the fixture value

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
        assert git.author == git.committer
        assert git.author.name == "Gigantum AutoCommit"
        assert git.author.email == "noreply@gigantum.io"
        assert git.committer.name == "Gigantum AutoCommit"
        assert git.committer.email == "noreply@gigantum.io"

        # Test updating just author
        git.update_author(GitAuthor("New Name", "test@test.com"))
        assert git.author.name == "New Name"
        assert git.author.email == "test@test.com"
        assert git.committer.name == "New Name"
        assert git.committer.email == "test@test.com"

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

        # Create file
        with open(os.path.join(working_directory, "add.txt"), 'wt') as dt:
            dt.write("entry asdf")

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

    def test_remove_staged_file(self, mock_initialized):
        """Test removing files from a repository"""
        git = mock_initialized[0]
        working_directory = mock_initialized[1]

        # Create file
        with open(os.path.join(working_directory, "staged.txt"), 'wt') as dt:
            dt.write("entry asdf")
        git.add(os.path.join(working_directory, "staged.txt"))

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
        with open(os.path.join(working_directory, "staged.txt"), 'wt') as dt:
            dt.write("entry asdf")
        git.add(os.path.join(working_directory, "staged.txt"))
        git.repo.index.commit("Test commit")

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
        with open(os.path.join(working_directory, "staged.txt"), 'wt') as dt:
            dt.write("entry asdf")
        git.add(os.path.join(working_directory, "staged.txt"))
        git.repo.index.commit("Test commit")

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
        with open(os.path.join(working_directory, "test1.txt"), 'wt') as dt:
            dt.write("File number 1\n")
        with open(os.path.join(working_directory, "test2.txt"), 'wt') as dt:
            dt.write("File number 2\n")
        git.add(os.path.join(working_directory, "test1.txt"))
        git.add(os.path.join(working_directory, "test2.txt"))
        git.repo.index.commit("commit 1")
        commit1 = git.repo.head.commit

        # Edit file 1 - Add a line
        with open(os.path.join(working_directory, "test1.txt"), 'wt') as dt:
            dt.write("File 1 has changed\n")
        git.add(os.path.join(working_directory, "test1.txt"))
        git.repo.index.commit("commit 2")
        commit2 = git.repo.head.commit

        # Edit file 2
        with open(os.path.join(working_directory, "test2.txt"), 'wt') as dt:
            dt.write("File number 2 changed\n")
        git.add(os.path.join(working_directory, "test2.txt"))
        git.repo.index.commit("commit 3")
        commit3 = git.repo.head.commit

        # Create another file
        with open(os.path.join(working_directory, "test3.txt"), 'wt') as dt:
            dt.write("File number 3\n")
        git.add(os.path.join(working_directory, "test3.txt"))
        git.repo.index.commit("commit 4")
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
        with open(os.path.join(working_directory, "test1.txt"), 'wt') as dt:
            dt.write("File number 1\n")
        subdir = os.path.join(working_directory, "subdir")
        os.makedirs(subdir)
        with open(os.path.join(subdir, "subdir_file.txt"), 'wt') as dt:
            dt.write("entry subdir")
        git.add("test1.txt")
        git.add(os.path.join("subdir", "subdir_file.txt"))
        with open(os.path.join(working_directory, "untracked.txt"), 'wt') as dt:
            dt.write("Untracked File\n")

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
        working_directory = mock_initialized[1]

        # Create files
        with open(os.path.join(working_directory, "test1.txt"), 'wt') as dt:
            dt.write("File number 1\n")
        git.add("test1.txt")

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
        working_directory = mock_initialized[1]

        # Create files
        commit_list = []
        with open(os.path.join(working_directory, "test1.txt"), 'wt') as dt:
            dt.write("File number 1\n")
        git.add(os.path.join(working_directory, "test1.txt"))
        git.repo.index.commit("commit 1")
        commit_list.append(git.repo.head.commit)

        with open(os.path.join(working_directory, "test2.txt"), 'wt') as dt:
            dt.write("File number 2\n")
        git.add(os.path.join(working_directory, "test2.txt"))
        git.repo.index.commit("commit 2")
        commit_list.append(git.repo.head.commit)

        # Edit file 1 - Add a line
        with open(os.path.join(working_directory, "test1.txt"), 'wt') as dt:
            dt.write("File 1 has changed\n")
        git.add(os.path.join(working_directory, "test1.txt"))
        git.repo.index.commit("commit 3")
        commit_list.append(git.repo.head.commit)

        # Edit file 2
        with open(os.path.join(working_directory, "test2.txt"), 'wt') as dt:
            dt.write("File number 2 changed\n")
        git.add(os.path.join(working_directory, "test2.txt"))
        git.repo.index.commit("commit 4")
        commit_list.append(git.repo.head.commit)

        # Create another file
        with open(os.path.join(working_directory, "test3.txt"), 'wt') as dt:
            dt.write("File number 3\n")
        git.add(os.path.join(working_directory, "test3.txt"))
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

    def test_log_filter(self, mock_initialized):
        """Test getting commit history with some filtering"""
        git = mock_initialized[0]
        working_directory = mock_initialized[1]

        # Create files
        commit_list = []
        with open(os.path.join(working_directory, "test1.txt"), 'wt') as dt:
            dt.write("File number 1\n")
        git.add(os.path.join(working_directory, "test1.txt"))
        git.repo.index.commit("commit 1")
        commit_list.append(git.repo.head.commit)

        with open(os.path.join(working_directory, "test2.txt"), 'wt') as dt:
            dt.write("File number 2\n")
        git.add(os.path.join(working_directory, "test2.txt"))
        git.repo.index.commit("commit 2")
        commit_list.append(git.repo.head.commit)

        # Edit file 1 - Add a line
        with open(os.path.join(working_directory, "test1.txt"), 'wt') as dt:
            dt.write("File 1 has changed\n")
        git.add(os.path.join(working_directory, "test1.txt"))
        git.repo.index.commit("commit 3")
        commit_list.append(git.repo.head.commit)

        # Edit file 2
        with open(os.path.join(working_directory, "test2.txt"), 'wt') as dt:
            dt.write("File number 2 changed\n")
        git.add(os.path.join(working_directory, "test2.txt"))
        git.repo.index.commit("commit 4")
        commit_list.append(git.repo.head.commit)

        # Create another file
        with open(os.path.join(working_directory, "test3.txt"), 'wt') as dt:
            dt.write("File number 3\n")
        git.add(os.path.join(working_directory, "test3.txt"))
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
