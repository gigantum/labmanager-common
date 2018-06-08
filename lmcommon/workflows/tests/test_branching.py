import pytest

import mock
import os


from lmcommon.labbook import LabBook
from lmcommon.workflows import (GitWorkflow, MergeError, BranchManager, InvalidBranchName, BranchWorkflowViolation,
    BranchException)
from lmcommon.files import FileOperations
from lmcommon.fixtures import (mock_config_file, mock_labbook, mock_labbook_lfs_disabled,
                               mock_duplicate_labbook, remote_bare_repo, sample_src_file,
                               _MOCK_create_remote_repo2 as _MOCK_create_remote_repo)

# If importing from remote, does new user's branch get created and does it push properly?


@pytest.fixture(scope="session")
def pause_wait_for_redis():
    import time
    time.sleep(3)

TEST_USER = 'test'

class TestBranching(object):

    def test_init_and_active_branch(self, mock_labbook_lfs_disabled):
        bm = BranchManager(mock_labbook_lfs_disabled[2], username=TEST_USER)
        assert bm.active_branch == f'gm.workspace-{TEST_USER}'
        assert bm.workspace_branch == f'gm.workspace-{TEST_USER}'
        assert len(bm.branches) == 1 and bm.branches[0] == f'gm.workspace-{TEST_USER}'

    def test_is_branch_name_valid(self):
        bad_strings = ['inval!id', '', '-', '---', '-' * 99, 'cats_' * 12, 'no--no', '-no-no-', 'yikes-' * 50 + 'a',
                       'bad!-bad!', 'no_way-*99', '`cat-99', "nope's-branch", 'nope"s-branch','No-Caps-Or-Anything',
                       'NO-CAPS-AT-ALL-99', 'Violà', 'Güten-Tag']
        for b in bad_strings:
            assert not BranchManager.is_branch_name_valid(b)
        good_strings = ['a', 'hello-there', 'yep-yep-yep', '99', 'hello-99-test', '2-33-44-55-66', 'experiment4',
                        'experiment-4', 'über-weird-name-should-this-work-hmm']
        for g in good_strings:
            assert BranchManager.is_branch_name_valid(g)

    def test_create_branch(self, mock_labbook_lfs_disabled):
        t = "my-first-feature-branch"
        lb = mock_labbook_lfs_disabled[2]
        bm = BranchManager(lb, username=TEST_USER)
        assert bm.active_branch == f'gm.workspace-{TEST_USER}'
        bm.create_branch(title=t)
        assert bm.active_branch == f'gm.workspace-{TEST_USER}.{t}'
        assert len(bm.branches) == 2

        # Now that we're on the feature bramch, we inhibit creating new branches off this
        with pytest.raises(BranchWorkflowViolation):
            bm.create_branch('innocent-enough-feature')

        with pytest.raises(BranchWorkflowViolation):
            bm.create_branch(t)

        # Make sure no new branch was created
        assert bm.active_branch == f'gm.workspace-{TEST_USER}.{t}'
        assert len(bm.branches) == 2
        assert lb.is_repo_clean is True

    def test_create_branch_fails_bad_name(self, mock_labbook_lfs_disabled):
        bm = BranchManager(mock_labbook_lfs_disabled[2], username=TEST_USER)
        with pytest.raises(InvalidBranchName):
            bm.create_branch('poop-branch-')

    def test_workon_branch_without_any_changes(self, mock_labbook_lfs_disabled):
        t = 'my-new-example-feature'
        lb = mock_labbook_lfs_disabled[2]
        bm = BranchManager(lb, username=TEST_USER)
        assert bm.active_branch == f'gm.workspace-{TEST_USER}'
        full_branch = bm.create_branch(title=t)
        assert lb.is_repo_clean

        bm.workon_branch(bm.workspace_branch)
        assert bm.active_branch == f'gm.workspace-{TEST_USER}'
        assert lb.active_branch == f'gm.workspace-{TEST_USER}'
        assert lb.is_repo_clean

        bm.workon_branch(full_branch)
        assert bm.active_branch == full_branch
        assert lb.active_branch == full_branch
        assert lb.is_repo_clean

        with pytest.raises(InvalidBranchName):
            bm.workon_branch('no-way-josé')

    def test_workon_branch_with_changes(self, mock_labbook_lfs_disabled):
        t = 'my-new-example-feature'
        lb = mock_labbook_lfs_disabled[2]
        bm = BranchManager(lb, username=TEST_USER)
        assert bm.active_branch == f'gm.workspace-{TEST_USER}'
        full_branch = bm.create_branch(title=t)
        assert lb.is_repo_clean

        # Make some changes to the upstream main branch
        #lb = LabBook(mock_labbook_lfs_disabled[0])
        #lb.from_name("test", "test", "labbook1")
        bm = BranchManager(lb, username=TEST_USER)
        bm.workon_branch(bm.workspace_branch)
        lb.makedir('code/sillyfolder', create_activity_record=True)
        assert lb.is_repo_clean
        lb.makedir('input/newfolder', create_activity_record=True)
        assert lb.is_repo_clean

        #lb = LabBook(mock_labbook_lfs_disabled[0])
        #lb.from_name("test", "test", "labbook1")
        bm.workon_branch(full_branch)
        lb.makedir('output/otherdir', create_activity_record=True)
        assert lb.is_repo_clean
        bm.merge_from(bm.workspace_branch)
        assert os.path.isdir(os.path.join(lb.root_dir, 'code/sillyfolder'))
        assert os.path.isdir(os.path.join(lb.root_dir, 'input/newfolder'))
        assert os.path.isdir(os.path.join(lb.root_dir, 'output/otherdir'))
        assert lb.is_repo_clean

        bm.workon_branch(bm.workspace_branch)
        assert lb.is_repo_clean
        bm.remove_branch(full_branch)
        assert not full_branch in bm.branches
        assert lb.is_repo_clean

    def test_merge_conflics_1(self, mock_labbook_lfs_disabled):

        # In the main branch, make some file
        with open('/tmp/s1.txt', 'w') as s1:
            s1.write('original-file\ndata')
        test_user_lb = mock_labbook_lfs_disabled[2]
        FileOperations.insert_file(test_user_lb, section='code', src_file=s1.name)

        # Create a new branch and make a change to s1.txt
        bm = BranchManager(test_user_lb, username=TEST_USER)
        new_b = bm.create_branch("example-feature-branch")
        with open('/tmp/s1.txt', 'w') as s1:
            s1.write('new-changes-in\nfeature-branch')
        FileOperations.insert_file(test_user_lb, section='code', src_file=s1.name)
        with open(os.path.join(test_user_lb.root_dir, 'output/sample'), 'w') as f:
            f.write('sample data in a file not explicity added - this should be swept up.')
        assert not test_user_lb.is_repo_clean

        # Switch back to the main branch
        bm.workon_branch(bm.workspace_branch)
        assert test_user_lb.is_repo_clean
        assert not os.path.exists(os.path.join(test_user_lb.root_dir, 'output/sample'))
        with open('/tmp/s1.txt', 'w') as s1:
            s1.write('upstream-changes-from-workspace')
        FileOperations.insert_file(test_user_lb, section='code', src_file=s1.name, dst_path='')

        # Switch back to feature branch -- make sure that failed merges rollback to state before merge.
        bm.workon_branch(new_b)
        assert test_user_lb.is_repo_clean
        with pytest.raises(BranchException):
            bm.merge_from(bm.workspace_branch)
        assert test_user_lb.is_repo_clean

        bm.merge_from(bm.workspace_branch, force=True)
        assert open(os.path.join(test_user_lb.root_dir, 'code', 's1.txt')).read(1000) == \
            'upstream-changes-from-workspace'
        assert test_user_lb.is_repo_clean

        # Finally remove that feature branch.
        with pytest.raises(BranchWorkflowViolation):
            bm.remove_branch(bm.workspace_branch)

        with pytest.raises(BranchWorkflowViolation):
            bm.remove_branch(new_b)

        bm.workon_branch(bm.workspace_branch)
        assert test_user_lb.is_repo_clean
        bm.remove_branch(new_b)
        assert not new_b in bm.branches

    def test_create_a_rollback_branch(self, mock_labbook_lfs_disabled):
        test_user_lb = mock_labbook_lfs_disabled[2]

        test_user_lb.makedir(relative_path='code/folder1', create_activity_record=True)
        commit = test_user_lb.git.commit_hash
        test_user_lb.makedir(relative_path='code/folder2', create_activity_record=True)
        test_user_lb.makedir(relative_path='code/folder3', create_activity_record=True)

        bm = BranchManager(test_user_lb, username=TEST_USER)
        new_b = bm.create_branch('rollback-from-folder-1', revision=commit)
        test_user_lb.makedir(relative_path='input/branch-folder', create_activity_record=True)
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'code/folder1'))
        assert not os.path.exists(os.path.join(test_user_lb.root_dir, 'code/folder2'))
        assert not os.path.exists(os.path.join(test_user_lb.root_dir, 'code/folder3'))

        assert new_b == bm.active_branch
        test_user_lb.makedir(relative_path='input/branch-1', create_activity_record=True)
        test_user_lb.makedir(relative_path='input/branch-2', create_activity_record=True)
        test_user_lb.makedir(relative_path='input/branch-3', create_activity_record=True)
        assert test_user_lb.is_repo_clean

        # Now try pulling upstream changes back into the rollback branch
        bm.merge_from(bm.workspace_branch)
        assert test_user_lb.is_repo_clean
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'code/folder2'))
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'code/folder3'))
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'input/branch-1'))
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'input/branch-2'))
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'input/branch-3'))
        assert test_user_lb.is_repo_clean

        bm.workon_branch(bm.workspace_branch)
        assert test_user_lb.is_repo_clean
        bm.merge_from(new_b)
        assert test_user_lb.is_repo_clean

    def test_create_rollback_to_invalid_revision(self, mock_labbook_lfs_disabled):
        test_user_lb = mock_labbook_lfs_disabled[2]
        test_user_lb.makedir(relative_path='code/folder1', create_activity_record=True)
        commit = test_user_lb.git.commit_hash
        test_user_lb.makedir(relative_path='code/folder2', create_activity_record=True)
        test_user_lb.makedir(relative_path='code/folder3', create_activity_record=True)

        bm = BranchManager(test_user_lb, username=TEST_USER)
        with pytest.raises(InvalidBranchName):
            bm.create_branch('should-fail', revision='invalidrevision')
