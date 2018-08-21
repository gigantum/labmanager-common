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
import os


from lmcommon.labbook import LabBook, LabbookException
from lmcommon.files import FileOperations
from lmcommon.fixtures import (mock_config_file, mock_labbook_lfs_disabled, remote_labbook_repo)

# Note, I believe most of these tests are deprecated and OBE.

@pytest.fixture(scope="session")
def pause_wait_for_redis():
    import time
    time.sleep(3)


class TestLabBook(object):

    def test_checkout_basics(self, mock_config_file, mock_labbook_lfs_disabled):
        lb = mock_labbook_lfs_disabled[2]
        assert lb.active_branch == "gm.workspace-test"
        lb.checkout_branch("test-branch", new=True)
        assert lb.active_branch == "test-branch"
        lb.checkout_branch("gm.workspace-test")
        assert lb.active_branch == "gm.workspace-test"
        assert lb.has_remote is False

    def test_checkout_not_allowed_to_create_duplicate_branch(self, mock_config_file, mock_labbook_lfs_disabled):
        lb = mock_labbook_lfs_disabled[2]
        assert lb.active_branch == "gm.workspace-test"
        lb.checkout_branch("test-branch", new=True)
        assert lb.active_branch == "test-branch"
        lb.checkout_branch("gm.workspace-test")
        assert lb.active_branch == "gm.workspace-test"
        with pytest.raises(LabbookException):
            lb.checkout_branch("test-branch", new=True)
            assert lb.active_branch == "test-branch"

    def test_is_labbook_clean(self, mock_config_file, mock_labbook_lfs_disabled):
        lb = mock_labbook_lfs_disabled[2]
        assert lb.is_repo_clean
        # Make a new file in the input directory, but do not add/commit it.
        with open(os.path.join(lb.root_dir, 'input', 'catfile'), 'wb') as f:
            f.write(b"data.")
        assert not lb.is_repo_clean
        # Now, make sure that new file is added and tracked, and then try making the new branch again.
        lb.git.add(os.path.join(lb.root_dir, 'input', 'catfile'))
        lb.git.commit("Added file")
        assert lb.is_repo_clean

    def test_checkout_not_allowed_when_there_are_uncomitted_changes(self, mock_config_file, mock_labbook_lfs_disabled):
        lb = mock_labbook_lfs_disabled[2]

        # Make a new file in the input directory, but do not add/commit it.
        with open(os.path.join(lb.root_dir, 'input', 'catfile'), 'wb') as f:
            f.write(b"data.")

        with pytest.raises(LabbookException):
            # We should not be allowed to switch branches when there are uncommitted changes
            lb.checkout_branch("branchy", new=True)
        assert lb.active_branch == "gm.workspace-test"
        # Now, make sure that new file is added and tracked, and then try making the new branch again.
        lb.git.add(os.path.join(lb.root_dir, 'input', 'catfile'))
        lb.git.commit("Added file")
        lb.checkout_branch("branchy", new=True)
        assert lb.active_branch == "branchy"

    def test_checkout_just_double_check_that_files_from_other_branches_go_away(self, mock_config_file,
                                                                               mock_labbook_lfs_disabled):
        lb = mock_labbook_lfs_disabled[2]
        lb.checkout_branch("has-catfile", new=True)
        # Make a new file in the input directory, but do not add/commit it.
        with open(os.path.join(lb.root_dir, 'input', 'catfile'), 'wb') as f:
            f.write(b"data.")
        lb.git.add(os.path.join(lb.root_dir, 'input', 'catfile'))
        lb.git.commit("Added file")
        assert lb.active_branch == "has-catfile"
        lb.checkout_branch("gm.workspace-test")
        # Just make sure that with doing the checkout the file created in the other branch doesn't exist.
        assert not os.path.exists(os.path.join(lb.root_dir, 'input', 'catfile'))

    def test_checkout_make_sure_new_must_be_true_when_making_new_branch(self, mock_labbook_lfs_disabled):
        lb = mock_labbook_lfs_disabled[2]
        with pytest.raises(LabbookException):
            lb.checkout_branch("new-branch", new=False)
        assert lb.active_branch == 'gm.workspace-test'

    def test_checkout_and_track_a_remote_branch(self, remote_labbook_repo, mock_labbook_lfs_disabled):
        # Do the equivalent of a "git checkoub -b mybranch". Checkout from remote only.
        lb = mock_labbook_lfs_disabled[2]
        lb.add_remote("origin", remote_labbook_repo)
        lb.checkout_branch(branch_name="testing-branch")

    def test_list_branches(self, remote_labbook_repo, mock_labbook_lfs_disabled):
        # We need to test we can see remote branches with a "get_branches()" call
        # Even if it hasn't been pulled.
        lb = mock_labbook_lfs_disabled[2]
        lb.add_remote("origin", remote_labbook_repo)
        assert 'origin/testing-branch' in lb.get_branches()['remote']

    def test_count_commits_behind_remote(self, mock_config_file, remote_labbook_repo, mock_labbook_lfs_disabled):
        # Check that we're behind when changes happen at remote.
        lb = mock_labbook_lfs_disabled[2]
        lb.add_remote("origin", remote_labbook_repo)
        lb.checkout_branch("testing-branch")

        r = lb.get_commits_behind_remote("origin")
        assert r[0] == 'testing-branch'
        # This is 2, in order to account for the activity entry.
        assert r[1] == 0


        remote_lb = LabBook(mock_config_file[0])
        remote_lb.from_directory(remote_labbook_repo)
        remote_lb.checkout_branch("testing-branch")
        FileOperations.delete_file(remote_lb, "code", "codefile.c")

        r = lb.get_commits_behind_remote("origin")
        assert r[0] == 'testing-branch'
        # This is 2, in order to account for the notes entry.
        assert r[1] == 2

    def test_count_commits_behind_remote_when_no_change(self, mock_config_file, remote_labbook_repo,
                                                        mock_labbook_lfs_disabled):
        # When the branch is up to date, ensure it doesn't report being behind.
        lb = mock_labbook_lfs_disabled[2]
        lb.add_remote("origin", remote_labbook_repo)
        lb.checkout_branch("testing-branch")

        r = lb.get_commits_behind_remote("origin")
        assert r[0] == 'testing-branch'
        # Should be up-to-date.
        assert r[1] == 0

    def test_count_commits_behind_for_local_branch(self, mock_config_file, remote_labbook_repo,
                                                   mock_labbook_lfs_disabled):
        # When we're using a local branch, by definition it is never behind.
        lb = mock_labbook_lfs_disabled[2]
        lb.add_remote("origin", remote_labbook_repo)
        lb.checkout_branch("super-local-branch", new=True)

        r = lb.get_commits_behind_remote("origin")
        assert r[0] == 'super-local-branch'
        # Should be up-to-date.
        assert r[1] == 0
