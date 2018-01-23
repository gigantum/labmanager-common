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
import pprint


import docker
import git

from lmcommon.imagebuilder import ImageBuilder
from lmcommon.environment import ComponentManager, RepositoryManager
from lmcommon.fixtures import labbook_dir_tree, mock_config_file, setup_index, mock_config_with_repo
import lmcommon.fixtures
from lmcommon.labbook import LabBook
from lmcommon.configuration import get_docker_client


class TestImageBuilder(object):

    def test_temp_labbook_dir(self, labbook_dir_tree):
        """Make sure that the labbook_dir_tree is created properly and loads into the ImageBuilder. """
        ib = ImageBuilder(labbook_dir_tree)

    def test_load_baseimage(self, labbook_dir_tree):
        """Ensure the FROM line exists in the _load_baseimage function. """
        ib = ImageBuilder(labbook_dir_tree)
        docker_lines = ib._load_baseimage()
        assert any(["FROM gigdev/gm-quickstart" in l for l in docker_lines])

    def test_load_baseimage_only_from(self, labbook_dir_tree):
        """Ensure that _load_baseimage ONLY sets the FROM line, all others are comments or empty"""
        ib = ImageBuilder(labbook_dir_tree)
        assert len([l for l in ib._load_baseimage() if len(l) > 0 and l[0] != '#']) == 1

    def test_package_apt(self, labbook_dir_tree):
        package_manager_dir = os.path.join(labbook_dir_tree, '.gigantum', 'env', 'package_manager')
        with open(os.path.join(package_manager_dir, 'apt_docker.yaml'), 'w') as apt_dep:
            content = os.linesep.join([
                'manager: apt',
                'package: docker',
                'version: null',
                'from_base: true'
            ])
            apt_dep.write(content)

        ib = ImageBuilder(labbook_dir_tree)
        pkg_lines = [l for l in ib._load_packages() if 'RUN' in l]
        assert 'RUN apt-get -y install docker' in pkg_lines

    def test_package_pip3(self, labbook_dir_tree):
        package_manager_dir = os.path.join(labbook_dir_tree, '.gigantum', 'env', 'package_manager')
        with open(os.path.join(package_manager_dir, 'pip3_docker.yaml'), 'w') as apt_dep:
            content = os.linesep.join([
                'manager: pip3',
                'package: docker',
                'version: "2.0.1"',
                'from_base: true'
            ])
            apt_dep.write(content)

        ib = ImageBuilder(labbook_dir_tree)
        pkg_lines = [l for l in ib._load_packages() if 'RUN' in l]
        assert 'RUN pip3 install docker==2.0.1' in pkg_lines

    def test_validate_dockerfile(self, labbook_dir_tree):
        """Test if the Dockerfile builds and can launch the image. """
        package_manager_dir = os.path.join(labbook_dir_tree, '.gigantum', 'env', 'package_manager')
        with open(os.path.join(package_manager_dir, 'pip3_docker.yaml'), 'w') as apt_dep:
            content = os.linesep.join([
                'manager: pip3',
                'package: docker',
                'version: null',
                'from_base: true'
            ])
            apt_dep.write(content)

        with open(os.path.join(package_manager_dir, 'apt_docker.yaml'), 'w') as apt_dep:
            content = os.linesep.join([
                'manager: apt',
                'package: docker',
                'version: null',
                'from_base: true'
            ])
            apt_dep.write(content)

        with open(os.path.join(package_manager_dir, 'pip3_requests.yaml'), 'w') as apt_dep:
            content = os.linesep.join([
                'manager: pip3',
                'package: requests',
                'version: "2.18.4"',
                'from_base: true'
            ])
            apt_dep.write(content)

        ib = ImageBuilder(labbook_dir_tree)
        n = ib.assemble_dockerfile(write=False)
        pprint.pprint(n)
        with open(os.path.join(labbook_dir_tree, ".gigantum", "env", "Dockerfile"), "w") \
            as dockerfile:
            dockerfile_text = ib.assemble_dockerfile(write=False)
            dockerfile.write(dockerfile_text)

        test_lines = ['## Adding individual packages',
                      'RUN apt-get -y install docker',
                      'RUN pip3 install docker',
                      'RUN pip3 install requests==2.18.4']

        for line in test_lines:
            assert line in dockerfile_text.split(os.linesep)

    def test_custom_package(self, labbook_dir_tree):
        package_manager_dir = os.path.join(labbook_dir_tree, '.gigantum', 'env', 'custom')

        ib = ImageBuilder(labbook_dir_tree)
        pkg_lines = [l.strip() for l in ib._load_custom() if 'RUN' in l]

        assert 'RUN apt-get -y install libjpeg-dev libtiff5-dev zlib1g-dev libfreetype6-dev liblcms2-dev libopenjpeg-dev' in pkg_lines
        assert 'RUN pip3 install Pillow==4.2.1' in pkg_lines

    def test_build_docker_image(self, mock_config_with_repo):
        # Create a labook
        lb = LabBook(mock_config_with_repo[0])
        labbook_dir = lb.new(name="catbook-test-dockerbuild", description="Testing docker building.",
                             owner={"username": "test"})
        # Create Component Manager
        cm = ComponentManager(lb)
        # Add a component
        cm.add_component("base", lmcommon.fixtures.ENV_UNIT_TEST_REPO, lmcommon.fixtures.ENV_UNIT_TEST_BASE,
                         lmcommon.fixtures.ENV_UNIT_TEST_REV)
        n = cm.add_package("pip3", "requests", "2.18.4")

        ib = ImageBuilder(lb.root_dir)
        docker_lines = ib.assemble_dockerfile(write=True)
        pprint.pprint(docker_lines)
        assert 'RUN pip3 install requests==2.18.4' in docker_lines
        assert all(['==None' not in l for l in docker_lines.split()])
        unit_test_tag = "unit-test-please-delete"
        client = get_docker_client()

        # NOTE: DO NOT run these following lines on CircleCI
        if getpass.getuser() != 'circleci':
            # Right now assume username is "default"
            assert os.path.exists(os.path.join(lb.root_dir, '.gigantum', 'env', 'entrypoint.sh'))
            with open(os.path.join(lb.root_dir, '.gigantum', 'env', 'Dockerfile')) as f:
                print(''.join(f.readlines()))
            docker_image_id = ib.build_image(docker_client=client, image_tag=unit_test_tag,
                                             nocache=True, username='default')['docker_image_id']
            client.images.remove(docker_image_id, force=True, noprune=False)

    @pytest.mark.skipif(getpass.getuser() == 'circleci', reason="Cannot build images on CircleCI")
    def test_rebuild_docker_image(self, mock_config_file, labbook_dir_tree):
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
        cm.add_component("base", lmcommon.fixtures.ENV_UNIT_TEST_REPO, lmcommon.fixtures.ENV_UNIT_TEST_BASE,
                         lmcommon.fixtures.ENV_UNIT_TEST_REV)
        n = cm.add_package("pip3", "requests", "2.18.4")

        ib = ImageBuilder(lb.root_dir)
        ib.assemble_dockerfile()
        unit_test_tag = "unit-test-please-delete"
        client = get_docker_client()

        # Build image once
        # Right now assume username is "default"
        ib.build_image(docker_client=client, image_tag=unit_test_tag, username='default')

        # Start container
        docker_container = client.containers.run(unit_test_tag, detach=True, name=unit_test_tag)

        # Try to build it again
        # Right now assume username is "default"
        docker_image_id = ib.build_image(docker_client=client, image_tag=unit_test_tag,
                                         username='default')['docker_image_id']

        # Clean up
        client.images.remove(docker_image_id, force=True, noprune=False)
