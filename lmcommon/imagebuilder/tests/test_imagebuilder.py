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
import datetime
import pytest
import shutil
import tempfile
import getpass
import os
import uuid
import shutil
import yaml
import pickle


import docker
import git

from lmcommon.imagebuilder import ImageBuilder
from lmcommon.environment import ComponentManager, RepositoryManager
from lmcommon.labbook import LabBook

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

@pytest.fixture()
def labbook_dir_tree():
    with tempfile.TemporaryDirectory() as tempdir:

        subdirs = [['.gigantum'],
                   ['.gigantum', 'env'],
                   ['.gigantum', 'env', 'base_image'],
                   ['.gigantum', 'env', 'dev_env'],
                   ['.gigantum', 'env', 'custom'],
                   ['.gigantum', 'env', 'package_manager']]

        for subdir in subdirs:
            os.makedirs(os.path.join(tempdir, "my-temp-labbook", *subdir), exist_ok=True)

        with tempfile.TemporaryDirectory() as checkoutdir:
            repo = git.Repo.clone_from("https://github.com/gig-dev/environment-components-dev.git", checkoutdir)
            shutil.copy(os.path.join(checkoutdir, "base_image/gigantum/ubuntu1604-python3/ubuntu1604-python3-v0_4.yaml"),
                        os.path.join(tempdir, "my-temp-labbook", ".gigantum", "env", "base_image"))
            shutil.copy(os.path.join(checkoutdir, "dev_env/gigantum/jupyter-ubuntu/jupyter-ubuntu-v0_0.yaml"),
                        os.path.join(tempdir, "my-temp-labbook", ".gigantum", "env", "dev_env"))
            shutil.copy(os.path.join(checkoutdir, "custom/gigantum/ubuntu-python3-pillow/ubuntu-python3-pillow-v0_3.yaml"),
                        os.path.join(tempdir, "my-temp-labbook", ".gigantum", "env", "custom"))

        yield os.path.join(tempdir, 'my-temp-labbook')


class TestImageBuilder(object):

    def test_temp_labbook_dir(self, labbook_dir_tree):
        """Make sure that the labbook_dir_tree is created properly and loads into the ImageBuilder. """
        ib = ImageBuilder(labbook_dir_tree)

    def test_load_baseimage(self, labbook_dir_tree):
        """Ensure the FROM line exists in the _load_baseimage function. """
        ib = ImageBuilder(labbook_dir_tree)
        docker_lines = ib._load_baseimage()
        assert any(["FROM gigdev/ubuntu1604-python3:7a7c9d41-2017-08-03" in l for l in docker_lines])

    def test_load_baseimage_only_from(self, labbook_dir_tree):
        """Ensure that _load_baseimage ONLY sets the FROM line, all others are comments or empty"""
        ib = ImageBuilder(labbook_dir_tree)
        assert len([l for l in ib._load_baseimage() if len(l) > 0 and l[0] != '#']) == 1

    def test_package_apt(self, labbook_dir_tree):
        package_manager_dir = os.path.join(labbook_dir_tree, '.gigantum', 'env', 'package_manager')
        with open(os.path.join(package_manager_dir, 'apt_docker.yaml'), 'w') as apt_dep:
            content = os.linesep.join([
                'package_manager: apt-get',
                'name: docker',
                'version: 0.0 this is ignored'
            ])
            apt_dep.write(content)

        ib = ImageBuilder(labbook_dir_tree)
        pkg_lines = [l for l in ib._load_packages() if 'RUN' in l]
        assert 'RUN apt-get -y install docker' in pkg_lines

    def test_package_pip3(self, labbook_dir_tree):
        package_manager_dir = os.path.join(labbook_dir_tree, '.gigantum', 'env', 'package_manager')
        with open(os.path.join(package_manager_dir, 'pip3_docker.yaml'), 'w') as apt_dep:
            content = os.linesep.join([
                'package_manager: pip3',
                'name: docker',
                'version: 0.0 this is ignored'
            ])
            apt_dep.write(content)

        ib = ImageBuilder(labbook_dir_tree)
        pkg_lines = [l for l in ib._load_packages() if 'RUN' in l]
        assert 'RUN pip3 install docker' in pkg_lines

    def test_development_environment_loaded(self, labbook_dir_tree):
        ib = ImageBuilder(labbook_dir_tree)
        docker_lines = ib.assemble_dockerfile().split(os.linesep)

        # Ensure only one ENTRYPOINT
        assert len([l for l in docker_lines if 'ENTRYPOINT' in l and l[0] != '#']) == 1
        # Ensure only one WORKDIR
        assert len([l for l in docker_lines if 'WORKDIR' in l and l[0] != '#']) == 1
        # Ensure only one CMD
        assert len([l for l in docker_lines if 'CMD' in l and l[0] != '#']) == 1

    def test_validate_dockerfile(self, labbook_dir_tree):
        """Test if the Dockerfile builds and can launch the image. """
        package_manager_dir = os.path.join(labbook_dir_tree, '.gigantum', 'env', 'package_manager')
        with open(os.path.join(package_manager_dir, 'pip3_docker.yaml'), 'w') as apt_dep:
            content = os.linesep.join([
                'package_manager: pip3',
                'name: docker',
                'version: 0.0 this is ignored'
            ])
            apt_dep.write(content)

        with open(os.path.join(package_manager_dir, 'apt_docker.yaml'), 'w') as apt_dep:
            content = os.linesep.join([
                'package_manager: apt-get',
                'name: docker',
                'version: 0.0 this is ignored'
            ])
            apt_dep.write(content)

        with open(os.path.join(package_manager_dir, 'pip3_requests.yaml'), 'w') as apt_dep:
            content = os.linesep.join([
                'package_manager: pip3',
                'name: requests',
                'version: 0.0 this is ignored'
            ])
            apt_dep.write(content)

        ib = ImageBuilder(labbook_dir_tree)
        with open(os.path.join(labbook_dir_tree, ".gigantum", "env", "Dockerfile"),
                  "w") as dockerfile:
            dockerfile_text = ib.assemble_dockerfile()
            print(dockerfile_text)
            dockerfile.write(dockerfile_text)

        test_lines = ['## Adding individual packages',
                      'RUN apt-get -y install docker',
                      'RUN pip3 install docker',
                      'RUN pip3 install requests']

        for line in test_lines:
            assert line in dockerfile_text

    def test_custom_package(self, labbook_dir_tree):
        package_manager_dir = os.path.join(labbook_dir_tree, '.gigantum', 'env', 'custom')

        ib = ImageBuilder(labbook_dir_tree)
        pkg_lines = [l.strip() for l in ib._load_custom() if 'RUN' in l]

        assert 'RUN apt-get -y install libjpeg-dev libtiff5-dev zlib1g-dev libfreetype6-dev liblcms2-dev libopenjpeg-dev' in pkg_lines
        assert 'RUN pip3 install Pillow==4.2.1' in pkg_lines

    def test_build_docker_image(self, mock_config_file): # , labbook_dir_tree):
        # Build the environment component repo
        # Build the environment component repo
        erm = RepositoryManager(mock_config_file[0])
        erm.update_repositories()
        erm.index_repositories()

        # Create a labook
        lb = LabBook(mock_config_file[0])

        labbook_dir = lb.new(name="catbook-test-dockerbuild", description="Testing docker building.",
                             owner={"username": "test"})

        # Create Component Manager
        cm = ComponentManager(lb)

        # Add a component
        cm.add_component("base_image", "gig-dev_environment-components", "gigantum", "ubuntu1604-python3", "0.4")
        cm.add_component("dev_env", "gig-dev_environment-components", "gigantum", "jupyter-ubuntu", "0.1")

        ib = ImageBuilder(lb.root_dir)
        unit_test_tag = "unit-test-please-delete"
        client = docker.from_env()

        if getpass.getuser() != 'circleci':
            # NOTE: DO NOT run these following lines on CircleCI
            docker_image = ib.build_image(docker_client=client, image_tag=unit_test_tag, nocache=True)
            client.images.remove(docker_image.id, force=True, noprune=False)

    @pytest.mark.skipif(getpass.getuser() == 'circleci', reason="Cannot build images on CircleCI")
    def test_rebuild_docker_image(self, mock_config_file):
        # NOTE: DO NOT run test on CircleCI
        # Build the environment component repo
        erm = RepositoryManager(mock_config_file[0])
        erm.update_repositories()
        erm.index_repositories()

        # Create a labook
        lb = LabBook(mock_config_file[0])

        labbook_dir = lb.new(name="catbook-test-dockerbuild", description="Testing docker building.",
                             owner={"username": "test"})

        # Create Component Manager
        cm = ComponentManager(lb)

        # Add a component
        cm.add_component("base_image", "gig-dev_environment-components", "gigantum", "ubuntu1604-python3", "0.4")
        cm.add_component("dev_env", "gig-dev_environment-components", "gigantum", "jupyter-ubuntu", "0.1")

        ib = ImageBuilder(lb.root_dir)
        unit_test_tag = "unit-test-please-delete"
        client = docker.from_env()

        # Build image once
        ib.build_image(docker_client=client, image_tag=unit_test_tag)

        # Start container
        docker_container = client.containers.run(unit_test_tag, detach=True, name=unit_test_tag)

        # Try to build it again
        docker_image = ib.build_image(docker_client=client, image_tag=unit_test_tag)

        # Clean up
        client.images.remove(docker_image.id, force=True, noprune=False)
