# Copyright (c) 2018 FlashX, LLC
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
# OUT OF OR IN CO

import pytest

import mock
import os


from lmcommon.labbook import LabBook
from lmcommon.workflows import GitWorkflow, MergeError
from lmcommon.files import FileOperations
from lmcommon.fixtures import (mock_config_file, mock_labbook_lfs_disabled, mock_duplicate_labbook, remote_bare_repo,
                               sample_src_file, _MOCK_create_remote_repo2 as _MOCK_create_remote_repo,
                               mock_config_lfs_disabled)

# If importing from remote, does new user's branch get created and does it push properly?


@pytest.fixture(scope="session")
def pause_wait_for_redis():
    import time
    time.sleep(3)


class TestLabbookShareProtocol(object):

    @mock.patch('lmcommon.workflows.core.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_simple_publish_new_one_user(self, pause_wait_for_redis, remote_bare_repo, mock_labbook_lfs_disabled):
        # Make sure you cannot clobber a remote branch with your local branch of the same name.

        ## 1 - Make initial set of contributions to Labbook.
        lb = mock_labbook_lfs_disabled[2]

        assert lb.active_branch == "gm.workspace-test"
        lb.makedir(relative_path='code/testy-tacked-dir', create_activity_record=True)

        wf = GitWorkflow(lb)
        # Now publish to remote (creating it in the process).
        wf.publish(username='test')

        assert lb.active_branch == "gm.workspace-test"
        b = lb.get_branches()
        assert len(b['local']) == 2
        #assert len(b['remote']) == 2

        assert any(['gm.workspace' in str(x) for x in b['remote']])

        # Local branch should not be manifested in remote (FOR NOW)
        assert not any(['gm.workspace-test' in str(x) for x in b['remote']])

        ## 2 - Now make more updates and do it again
        lb.delete_file(section="code", relative_path="testy-tacked-dir", directory=True)
        assert not os.path.exists(os.path.join(lb.root_dir, 'code', 'testy-tacked-dir'))
        lb.makedir(relative_path='input/new-input-dir', create_activity_record=True)
        assert lb.active_branch == "gm.workspace-test"
        wf.sync('test')
        assert lb.active_branch == "gm.workspace-test"

        lb.checkout_branch('gm.workspace')
        assert os.path.exists(os.path.join(lb.root_dir, 'input', 'new-input-dir'))
        assert not os.path.exists(os.path.join(lb.root_dir, 'code', 'testy-tacked-dir'))

    @mock.patch('lmcommon.workflows.core.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_simple_single_user_two_instances(self, pause_wait_for_redis, remote_bare_repo, mock_labbook_lfs_disabled,
                                              mock_config_file, mock_config_lfs_disabled):
        """This mocks up a single user using a single labbook at two locations (i.e., home and work). """

        ## 1 - Make initial set of contributions to Labbook.
        workplace_lb = mock_labbook_lfs_disabled[2]
        workplace_lb.makedir(relative_path='code/testy-tracked-dir', create_activity_record=True)
        wf = GitWorkflow(workplace_lb)
        wf.publish('test')

        workplace_lb.makedir(relative_path='code/dir-created-after-publish', create_activity_record=True)
        wf.sync('test')
        assert os.path.exists(os.path.join(workplace_lb.root_dir, 'code', 'dir-created-after-publish'))

        repo_location = workplace_lb.remote

        ## "home_lb" represents the user's home computer -- same Labbook, just in a different LM instance.
        home_lb = LabBook(mock_config_lfs_disabled[0])
        home_lb.from_remote(repo_location, username="test", owner="test", labbook_name="labbook1")
        assert home_lb.active_branch == "gm.workspace-test"
        assert os.path.exists(os.path.join(home_lb.root_dir, 'code', 'testy-tracked-dir'))
        assert os.path.exists(os.path.join(home_lb.root_dir, 'code', 'dir-created-after-publish'))

        home_lb.makedir(relative_path='output/sample-output-dir', create_activity_record=True)
        home_lb.makedir(relative_path='input/stuff-for-inputs', create_activity_record=True)
        home_wf = GitWorkflow(home_lb)
        home_wf.sync('test')

        wf.sync('test')
        assert os.path.exists(os.path.join(workplace_lb.root_dir, 'output/sample-output-dir'))
        assert os.path.exists(os.path.join(workplace_lb.root_dir, 'input/stuff-for-inputs'))

    @mock.patch('lmcommon.workflows.core.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_two_users_alternate_changes(self, pause_wait_for_redis, remote_bare_repo, mock_labbook_lfs_disabled,
                                         mock_config_file, mock_config_lfs_disabled):
        ## 1 - Make initial set of contributions to Labbook.
        test_user_lb = mock_labbook_lfs_disabled[2]
        test_user_lb.makedir(relative_path='code/testy-tracked-dir', create_activity_record=True)
        test_wf = GitWorkflow(test_user_lb)
        test_wf.publish('test')

        remote_repo = test_user_lb.remote
        assert remote_repo is not None

        bob_user_lb = LabBook(mock_config_lfs_disabled[0])
        bob_user_lb.from_remote(remote_repo, username="bob", owner="test", labbook_name="labbook1")
        bob_wf = GitWorkflow(bob_user_lb)
        assert bob_user_lb.active_branch == "gm.workspace-bob"
        bob_user_lb.makedir(relative_path='output/sample-output-dir-xxx', create_activity_record=True)
        bob_user_lb.makedir(relative_path='input/stuff-for-inputs-yyy', create_activity_record=True)
        bob_wf.sync('bob')

        test_wf.sync('test')
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'output/sample-output-dir-xxx'))
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'input/stuff-for-inputs-yyy'))
        assert test_user_lb.active_branch == "gm.workspace-test"

    @mock.patch('lmcommon.workflows.core.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_two_users_attempt_conflict(self, pause_wait_for_redis, mock_labbook_lfs_disabled, mock_config_file,
                                        sample_src_file, mock_config_lfs_disabled):
        test_user_lb = mock_labbook_lfs_disabled[2]
        test_user_lb.makedir(relative_path='code/testy-tracked-dir', create_activity_record=True)
        test_wf = GitWorkflow(test_user_lb)
        test_wf.publish('test')

        remote_repo = test_user_lb.remote

        bob_user_lb = LabBook(mock_config_lfs_disabled[0])
        bob_wf = GitWorkflow(bob_user_lb)
        bob_user_lb.from_remote(remote_repo, username="bob", owner="test", labbook_name="labbook1")
        assert bob_user_lb.active_branch == "gm.workspace-bob"
        bob_user_lb.makedir(relative_path='output/sample-output-dir-xxx', create_activity_record=True)
        bob_user_lb.makedir(relative_path='input/stuff-for-inputs-yyy', create_activity_record=True)
        bob_user_lb.delete_file(section="code", relative_path='testy-tracked-dir', directory=True)
        assert not os.path.exists(os.path.join(bob_user_lb.root_dir, 'code', 'testy-tracked-dir'))
        bob_wf.sync('bob')

        FileOperations.insert_file(test_user_lb, "code", sample_src_file, 'testy-tracked-dir')
        test_wf.sync('test')
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'code', 'testy-tracked-dir'))

        bob_wf.sync('bob')
        assert os.path.exists(os.path.join(bob_user_lb.root_dir, 'code', 'testy-tracked-dir'))

    @mock.patch('lmcommon.workflows.core.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_attempt_another_conflict(self, pause_wait_for_redis, mock_labbook_lfs_disabled,
                                      mock_config_file, sample_src_file, mock_config_lfs_disabled):
        with open('/tmp/s1.txt', 'w') as s1:
            s1.write('aaaaa\nbbbbbb\nccccc')
        test_user_lb = mock_labbook_lfs_disabled[2]
        FileOperations.insert_file(test_user_lb, section='code', src_file=s1.name)
        wf_test_user = GitWorkflow(test_user_lb)
        wf_test_user.publish('test')


        remote_repo = test_user_lb.remote

        bob_user_lb = LabBook(mock_config_lfs_disabled[0])
        bob_user_lb.from_remote(remote_repo, username="bob", owner="test", labbook_name="labbook1")
        wf_bob_user = GitWorkflow(bob_user_lb)
        assert bob_user_lb.active_branch == "gm.workspace-bob"
        with open(os.path.join(bob_user_lb.root_dir, 'code', 's1.txt'), 'w') as f:
            f.write('aaaaa\nzzzzzzz\nccccc')
        wf_bob_user.sync('bob')

        # Now orignal user makes some changes without having synced first
        with open(os.path.join(test_user_lb.root_dir, 'code', 's1.txt'), 'w') as f:
            f.write('aaaaa\nqqqqqqq\nccccc')

        with pytest.raises(MergeError):
            # There's a conflict - cannot merge
            wf_test_user.sync(username='test')
        assert test_user_lb.is_repo_clean

        # Now after we have a conflict and the merge is aborted. Let's try it again with force=True
        wf_test_user.sync(username='test', force=True)
        assert test_user_lb.is_repo_clean

        # Now check no untracked changes
        status = test_user_lb.git.status()
        for k in status:
            assert not status[k]
        assert test_user_lb.is_repo_clean
        lines = ''.join(open(os.path.join(test_user_lb.root_dir, 'code', 's1.txt')).readlines())

        wf_test_user.sync(username='test')

        # Make sure the test user's file was overwritten with most recent from upstream
        assert 'zzzzz' in lines

    @mock.patch('lmcommon.workflows.core.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_two_users_have_one_remove_a_file(self, pause_wait_for_redis, remote_bare_repo, mock_labbook_lfs_disabled,
                                         mock_config_file, mock_config_lfs_disabled):
        ## 1 - Make initial set of contributions to Labbook.
        test_user_lb = mock_labbook_lfs_disabled[2]
        test_user_lb.makedir(relative_path='code/testy-tracked-dir', create_activity_record=True)
        test_wf = GitWorkflow(test_user_lb)
        test_wf.publish('test')

        remote_repo = test_user_lb.remote

        bob_user_lb = LabBook(mock_config_lfs_disabled[0])
        bob_user_lb.from_remote(remote_repo, username="bob", owner="test", labbook_name="labbook1")
        bob_wf = GitWorkflow(bob_user_lb)
        assert bob_user_lb.active_branch == "gm.workspace-bob"
        bob_user_lb.delete_file(section='code', relative_path='testy-tracked-dir', directory=True)
        assert not os.path.exists(os.path.join(bob_user_lb.root_dir, 'code', 'testy-tracked-dir'))
        bob_user_lb.makedir(relative_path='input/stuff-for-inputs-yyy', create_activity_record=True)
        bob_wf.sync('bob')

        test_wf.sync('test')
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'input/stuff-for-inputs-yyy'))
        assert not os.path.exists(os.path.join(test_user_lb.root_dir, 'code', 'testy-tracked-dir'))
        assert test_user_lb.active_branch == "gm.workspace-test"