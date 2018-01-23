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
import uuid
import shutil
import pprint
import pickle
import yaml

from lmcommon.environment import RepositoryManager
from lmcommon.fixtures import mock_config_file, setup_index, ENV_UNIT_TEST_BASE, ENV_UNIT_TEST_REPO, ENV_UNIT_TEST_REV


class TestEnvironmentRepositoryManager(object):
    def test_update_repositories(self, setup_index):
        """Test building the index"""
        assert os.path.exists(os.path.join(setup_index[1], ".labmanager")) is True
        assert os.path.exists(os.path.join(setup_index[1], ".labmanager", "environment_repositories")) is True
        assert os.path.exists(os.path.join(setup_index[1], ".labmanager", "environment_repositories",
                                           ENV_UNIT_TEST_REPO)) is True
        assert os.path.exists(os.path.join(setup_index[1], ".labmanager", "environment_repositories",
                                           ENV_UNIT_TEST_REPO, "README.md")) is True

    def test_index_repositories_base_image(self, setup_index):
        """Test creating and accessing the detail version of the base image index"""
        # Verify index file contents
        with open(os.path.join(setup_index[0].local_repo_directory, "base_index.pickle"), 'rb') as fh:
            data = pickle.load(fh)

        pprint.pprint(data)
        assert ENV_UNIT_TEST_REPO in data
        assert ENV_UNIT_TEST_BASE in data[ENV_UNIT_TEST_REPO]
        assert ENV_UNIT_TEST_REV in data[ENV_UNIT_TEST_REPO][ENV_UNIT_TEST_BASE]
        assert "image" in data[ENV_UNIT_TEST_REPO][ENV_UNIT_TEST_BASE][ENV_UNIT_TEST_REV]
        assert "server" in data[ENV_UNIT_TEST_REPO][ENV_UNIT_TEST_BASE][ENV_UNIT_TEST_REV]['image']
        assert "package_managers" in data[ENV_UNIT_TEST_REPO][ENV_UNIT_TEST_BASE][ENV_UNIT_TEST_REV]
        assert "###repository###" in data[ENV_UNIT_TEST_REPO][ENV_UNIT_TEST_BASE][ENV_UNIT_TEST_REV]

    def test_index_repositories_custom(self, setup_index):
        """Test creating and accessing the detail version of the dev env index"""
        # Verify index file contents
        with open(os.path.join(setup_index[0].local_repo_directory, "custom_index.pickle"), 'rb') as fh:
            data = pickle.load(fh)

        assert ENV_UNIT_TEST_REPO in data
        assert "pillow" in data[ENV_UNIT_TEST_REPO]
        assert 0 in data[ENV_UNIT_TEST_REPO]["pillow"]
        assert "docker" in data[ENV_UNIT_TEST_REPO]["pillow"][0]
        assert "Pillow==4.2.1" in data[ENV_UNIT_TEST_REPO]["pillow"][0]["docker"]
        assert "###repository###" in data[ENV_UNIT_TEST_REPO]["pillow"][0]

    def test_index_repositories_base_image_list(self, setup_index):
        """Test accessing the list version of the base image index"""
        # Verify index file contents
        with open(os.path.join(setup_index[0].local_repo_directory, "base_list_index.pickle"), 'rb') as fh:
            data = pickle.load(fh)

        assert len(data) >= 2
        assert any(n.get('id') == ENV_UNIT_TEST_BASE for n in data)
        #assert data[1]['id'] == ENV_UNIT_TEST_BASE

    def test_index_repositories_custom_list(self, setup_index):
        """Test accessing the list version of the dev env index"""
        # Verify index file contents
        with open(os.path.join(setup_index[0].local_repo_directory, "custom_list_index.pickle"), 'rb') as fh:
            data = pickle.load(fh)

        assert len(data) >= 1
        assert any(d['id'] == 'pillow' for d in data)

