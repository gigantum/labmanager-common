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
import yaml
import pickle

import docker
import git

from lmcommon.imagebuilder import ImageBuidler
from lmcommon.environment import EnvironmentRepositoryManager


@pytest.fixture()
def clone_env_repo():
    with tempfile.TemporaryDirectory() as tempdir:
        repo = git.Repo()
        repo.clone_from("https://github.com/gig-dev/environment-components-dev.git", tempdir)
        yield tempdir


@pytest.fixture()
def mock_config_file():
    """A pytest fixture that creates a temporary directory and a config file to match. Deletes directory after test"""
    # Create a temporary working directory
    temp_dir = os.path.join(tempfile.tempdir, uuid.uuid4().hex)
    os.makedirs(temp_dir)

    with tempfile.NamedTemporaryFile(mode="wt") as fp:
        # Write a temporary config file
        fp.write("""core:
  team_mode: false 

environment:
  repo_url:
    - "https://github.com/gig-dev/environment-components.git"

git:
  backend: 'filesystem'
  working_directory: '{}'""".format(temp_dir))
        fp.seek(0)

        yield fp.name, temp_dir  # provide the fixture value

    # Remove the temp_dir
    shutil.rmtree(temp_dir)


class TestImageBuilder(object):
    def test_checkout_successful(self, clone_env_repo):
        assert os.path.exists(
            os.path.join(clone_env_repo, "base_image/gigantum/ubuntu1604-python3/ubuntu1604-python3-v0_1_0.yaml"))

    def test_indexing(self, mock_config_file):
        erm = EnvironmentRepositoryManager(mock_config_file[0])
        erm.update_repositories()
        erm.index_repositories()

        # Verify index file contents
        with open(os.path.join(erm.local_repo_directory, "base_image_index.pickle"), 'rb') as fh:
            data = pickle.load(fh)

        assert "7a7c" in data["gig-dev_environment-components"]["gigantum"]["ubuntu1604-python3"]["0.1.0"] \
            ["image"]["tag"]

    def test_match_dockerfile(self, mock_config_file):
        erm = EnvironmentRepositoryManager(mock_config_file[0])
        erm.update_repositories()
        erm.index_repositories()

        # Verify index file contents
        with open(os.path.join(erm.local_repo_directory, "base_image_index.pickle"), 'rb') as fh:
            data = pickle.load(fh)

        ib = ImageBuidler(data)
        assert "FROM gigdev/ubuntu1604-python3:7a7c9d41-2017-08-03" in ib.assemble_dockerfile()

    def test_build_with_docker(self, mock_config_file):
        erm = EnvironmentRepositoryManager(mock_config_file[0])
        erm.update_repositories()
        erm.index_repositories()

        # Verify index file contents
        with open(os.path.join(erm.local_repo_directory, "base_image_index.pickle"), 'rb') as fh:
            data = pickle.load(fh)

        ib = ImageBuidler(data)

        with tempfile.TemporaryDirectory() as tempd:
            with open(os.path.join(tempd, "Dockerfile"), "w") as dockerfile:
                dockerfile.write(ib.assemble_dockerfile())
            #import pprint; pprint.pprint(dockerfile.read())
            client = docker.from_env()
            client.images.build(path=tempd)
