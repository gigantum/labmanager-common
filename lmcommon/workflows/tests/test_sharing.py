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
import pprint

from lmcommon.workflows import GitWorkflow, MergeError, core, WorkflowsException
from lmcommon.fixtures import (mock_config_file, mock_labbook_lfs_disabled, mock_duplicate_labbook, remote_bare_repo,
                               sample_src_file, remote_labbook_repo, _MOCK_create_remote_repo2)


@pytest.fixture(scope="session")
def pause_wait_for_redis():
    import time
    time.sleep(3)

class TestWorkflowsSharing(object):

    def test_push_to_remote_repo_with_new_branch(self, remote_labbook_repo, mock_config_file,
                                                 mock_labbook_lfs_disabled):
        # Tests pushing a local branch to the remote.

        lb = mock_labbook_lfs_disabled[2]
        wf = GitWorkflow(lb)
        lb.checkout_branch("distinct-branch", new=True)
        lb.add_remote("origin", remote_labbook_repo)
        core.push(lb, "origin")

    def test_push_to_remote_repo_with_same_branch_should_be_error(self, remote_labbook_repo, mock_config_file,
                                                                  mock_labbook_lfs_disabled):
        # Make sure you cannot clobber a remote branch with your local branch of the same name.
        lb = mock_labbook_lfs_disabled[2]
        wf = GitWorkflow(lb)
        lb.add_remote("origin", remote_labbook_repo)
        with pytest.raises(WorkflowsException):
            # Since we'd be clobbering master in another repo, can't do this.
            core.push(lb, "origin")
