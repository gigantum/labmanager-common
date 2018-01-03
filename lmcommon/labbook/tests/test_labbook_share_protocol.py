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
import mock
import os
import shutil
import yaml
import pprint

import git

from lmcommon.labbook import LabBook, LabbookException
from lmcommon.fixtures import (mock_config_file, mock_labbook, mock_duplicate_labbook, remote_bare_repo,
                               sample_src_file, _MOCK_create_remote_repo)

# If importing from remote, does new user's branch get created and does it push properly?


@pytest.fixture(scope="session")
def pause_wait_for_redis():
    import time
    time.sleep(3)


class TestLabbookShareProtocol(object):

    @mock.patch('lmcommon.labbook.LabBook._create_remote_repo', new=_MOCK_create_remote_repo)
    def test_simple_publish_new_one_user(self, pause_wait_for_redis, remote_bare_repo, mock_labbook):
        # Make sure you cannot clobber a remote branch with your local branch of the same name.

        ## 1 - Make initial set of contributions to Labbook.
        lb = mock_labbook[2]

        assert lb.active_branch == "gm.workspace-test"
        lb.makedir(relative_path='code/testy-tacked-dir', create_activity_record=True)

        # Now publish to remote (creating it in the process).
        lb.publish(username='test')

        assert lb.active_branch == "gm.workspace-test"
        b = lb.get_branches()
        assert len(b['local']) == 2
        assert len(b['remote']) == 2

        # Make sure the branches are manifested in the remote repository.
        assert any(['gm.workspace' in str(x) for x in b['remote']])
        assert any(['gm.workspace-test' in str(x) for x in b['remote']])

        ## 2 - Now make more updates and do it again
        lb.delete_file(section="code", relative_path="testy-tacked-dir", directory=True)
        lb.makedir(relative_path='input/new-input-dir', create_activity_record=True)
        assert lb.active_branch == "gm.workspace-test"
        lb.sync('test')
        assert lb.active_branch == "gm.workspace-test"
        lb.checkout_branch('gm.workspace')
        assert os.path.exists(os.path.join(lb.root_dir, 'input', 'new-input-dir'))

    @mock.patch('lmcommon.labbook.LabBook._create_remote_repo', new=_MOCK_create_remote_repo)
    def test_simple_single_user_two_instances(self, pause_wait_for_redis, remote_bare_repo, mock_labbook, mock_config_file):
        """This mocks up a single user using a single labbook at two locations (i.e., home and work). """

        ## 1 - Make initial set of contributions to Labbook.
        workplace_lb = mock_labbook[2]
        workplace_lb.makedir(relative_path='code/testy-tracked-dir', create_activity_record=True)
        workplace_lb.publish('test')
        workplace_lb.makedir(relative_path='code/second-silly-dir', create_activity_record=True)
        workplace_lb.sync('test')

        repo_location = workplace_lb.remote

        ## "home_lb" represents the user's home computer -- same Labbook, just in a different LM instance.
        home_lb = LabBook(mock_config_file[0])
        home_lb.from_remote(repo_location, username="test", owner="test", labbook_name="labbook1")
        assert home_lb.active_branch == "gm.workspace-test"
        assert os.path.exists(os.path.join(home_lb.root_dir, 'code', 'testy-tracked-dir'))

        home_lb.makedir(relative_path='output/sample-output-dir', create_activity_record=True)
        home_lb.makedir(relative_path='input/stuff-for-inputs', create_activity_record=True)
        home_lb.sync('test')

        workplace_lb.sync('test')
        assert os.path.exists(os.path.join(workplace_lb.root_dir, 'output/sample-output-dir'))
        assert os.path.exists(os.path.join(workplace_lb.root_dir, 'input/stuff-for-inputs'))

    @mock.patch('lmcommon.labbook.LabBook._create_remote_repo', new=_MOCK_create_remote_repo)
    def test_two_users_alternate_changes(self, pause_wait_for_redis, remote_bare_repo, mock_labbook, mock_config_file):
        ## 1 - Make initial set of contributions to Labbook.
        test_user_lb = mock_labbook[2]
        test_user_lb.makedir(relative_path='code/testy-tracked-dir', create_activity_record=True)
        test_user_lb.publish('test')

        remote_repo = test_user_lb.remote

        bob_user_lb = LabBook(mock_config_file[0])
        bob_user_lb.from_remote(remote_repo, username="bob", owner="test", labbook_name="labbook1")
        assert bob_user_lb.active_branch == "gm.workspace-bob"
        bob_user_lb.makedir(relative_path='output/sample-output-dir-xxx', create_activity_record=True)
        bob_user_lb.makedir(relative_path='input/stuff-for-inputs-yyy', create_activity_record=True)
        bob_user_lb.sync('bob')

        test_user_lb.sync('test')
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'output/sample-output-dir-xxx'))
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'input/stuff-for-inputs-yyy'))
        assert test_user_lb.active_branch == "gm.workspace-test"

    @mock.patch('lmcommon.labbook.LabBook._create_remote_repo', new=_MOCK_create_remote_repo)
    def test_two_users_attempt_conflict(self, pause_wait_for_redis, mock_labbook, mock_config_file, sample_src_file):
        test_user_lb = mock_labbook[2]
        test_user_lb.makedir(relative_path='code/testy-tracked-dir', create_activity_record=True)
        test_user_lb.publish('test')

        remote_repo = test_user_lb.remote

        bob_user_lb = LabBook(mock_config_file[0])
        bob_user_lb.from_remote(remote_repo, username="bob", owner="test", labbook_name="labbook1")
        assert bob_user_lb.active_branch == "gm.workspace-bob"
        bob_user_lb.makedir(relative_path='output/sample-output-dir-xxx', create_activity_record=True)
        bob_user_lb.makedir(relative_path='input/stuff-for-inputs-yyy', create_activity_record=True)
        bob_user_lb.delete_file(section="code", relative_path='testy-tracked-dir', directory=True)
        assert not os.path.exists(os.path.join(bob_user_lb.root_dir, 'code', 'testy-tracked-dir'))
        bob_user_lb.sync('bob')

        test_user_lb.insert_file("code", sample_src_file, 'testy-tracked-dir')
        test_user_lb.sync('test')
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'code', 'testy-tracked-dir'))

        bob_user_lb.sync('bob')
        assert os.path.exists(os.path.join(bob_user_lb.root_dir, 'code', 'testy-tracked-dir'))