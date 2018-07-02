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
import os
import pprint
import tempfile
import git
import shutil

from lmcommon.imagebuilder import ImageBuilder
from lmcommon.environment import ComponentManager, RepositoryManager
from lmcommon.fixtures import labbook_dir_tree, mock_config_file, setup_index, mock_config_with_repo, mock_labbook, \
    ENV_UNIT_TEST_BASE, ENV_UNIT_TEST_REPO, ENV_UNIT_TEST_REV
import lmcommon.fixtures
from lmcommon.labbook import LabBook
from lmcommon.configuration import get_docker_client


def populate_with_pkgs(lb):
    with tempfile.TemporaryDirectory() as checkoutdir:
        repo = git.Repo.clone_from("https://github.com/gig-dev/components2.git", checkoutdir)
        shutil.copy(os.path.join(checkoutdir, "base/quickstart-jupyterlab/quickstart-jupyterlab_r0.yaml"),
                    os.path.join(lb.root_dir, ".gigantum", "env", "base"))
        shutil.copy(os.path.join(checkoutdir, "custom/pillow/pillow_r0.yaml"),
                    os.path.join(lb.root_dir, ".gigantum", "env", "custom"))


class TestImageBuilder(object):

    def test_temp_labbook_dir(self, mock_labbook):
        """Make sure that the labbook_dir_tree is created properly and loads into the ImageBuilder. """
        lb = mock_labbook[2]
        ib = ImageBuilder(lb)

    def test_load_baseimage(self, mock_labbook):
        """Ensure the FROM line exists in the _load_baseimage function. """
        lb = mock_labbook[2]
        populate_with_pkgs(lb)
        ib = ImageBuilder(lb)
        docker_lines = ib._load_baseimage()
        assert any(["FROM gigdev/gm-quickstart" in l for l in docker_lines])

    def test_load_baseimage_only_from(self, mock_labbook):
        """Ensure that _load_baseimage ONLY sets the FROM line, all others are comments or empty"""
        lb = mock_labbook[2]
        populate_with_pkgs(lb)
        ib = ImageBuilder(lb)
        assert len([l for l in ib._load_baseimage() if len(l) > 0 and l[0] != '#']) == 1

    def test_package_apt(self, mock_labbook):
        lb = mock_labbook[2]
        package_manager_dir = os.path.join(lb.root_dir, '.gigantum', 'env', 'package_manager')
        with open(os.path.join(package_manager_dir, 'apt_docker.yaml'), 'w') as apt_dep:
            content = os.linesep.join([
                'manager: apt',
                'package: docker',
                'version: 1.2.3',
                'from_base: false'
            ])
            apt_dep.write(content)

        ib = ImageBuilder(lb)
        pkg_lines = [l for l in ib._load_packages() if 'RUN' in l]
        assert 'RUN apt-get -y install docker' in pkg_lines

    def test_package_pip(self, mock_labbook):
        lb = mock_labbook[2]
        package_manager_dir = os.path.join(lb.root_dir, '.gigantum', 'env', 'package_manager')
        with open(os.path.join(package_manager_dir, 'pip3_docker.yaml'), 'w') as apt_dep:
            content = os.linesep.join([
                'manager: pip3',
                'package: docker',
                'version: "2.0.1"',
                'from_base: false'
            ])
            apt_dep.write(content)

        ib = ImageBuilder(lb)
        pkg_lines = [l for l in ib._load_packages() if 'RUN' in l]
        assert 'RUN pip install docker==2.0.1' in pkg_lines

        with open(os.path.join(package_manager_dir, 'pip3_docker.yaml'), 'w') as apt_dep:
            content = os.linesep.join([
                'manager: pip',
                'package: docker',
                'version: "2.0.1"',
                'from_base: true'
            ])
            apt_dep.write(content)

        ib = ImageBuilder(lb)
        pkg_lines = [l for l in ib._load_packages() if 'RUN' in l]
        assert 'RUN pip install docker==2.0.1' not in pkg_lines

    def test_validate_dockerfile(self, mock_labbook):
        """Test if the Dockerfile builds and can launch the image. """
        lb = mock_labbook[2]
        populate_with_pkgs(lb)
        package_manager_dir = os.path.join(lb.root_dir, '.gigantum', 'env', 'package_manager')
        with open(os.path.join(package_manager_dir, 'pip3_docker.yaml'), 'w') as apt_dep:
            content = os.linesep.join([
                'manager: pip3',
                'package: docker',
                'version: 2.0.1',
                'from_base: false'
            ])
            apt_dep.write(content)

        with open(os.path.join(package_manager_dir, 'apt_docker.yaml'), 'w') as apt_dep:
            content = os.linesep.join([
                'manager: apt',
                'package: docker',
                'version: 1.2.3',
                'from_base: false'
            ])
            apt_dep.write(content)

        with open(os.path.join(package_manager_dir, 'pip3_requests.yaml'), 'w') as apt_dep:
            content = os.linesep.join([
                'manager: pip3',
                'package: requests',
                'version: "2.18.4"',
                'from_base: false'
            ])
            apt_dep.write(content)

        ib = ImageBuilder(lb)
        n = ib.assemble_dockerfile(write=False)
        with open(os.path.join(lb.root_dir, ".gigantum", "env", "Dockerfile"), "w") as dockerfile:
            dockerfile_text = ib.assemble_dockerfile(write=False)
            dockerfile.write(dockerfile_text)

        test_lines = ['## Adding individual packages',
                      'RUN apt-get -y install docker',
                      'RUN pip install docker==2.0.1',
                      'RUN pip install requests==2.18.4']

        for line in test_lines:
            assert line in dockerfile_text.split(os.linesep)

    def test_custom_package(self, mock_labbook):
        lb = mock_labbook[2]
        populate_with_pkgs(lb)

        ib = ImageBuilder(lb)
        pkg_lines = [l.strip() for l in ib._load_custom() if 'RUN' in l]

        assert 'RUN apt-get -y install libjpeg-dev libtiff5-dev zlib1g-dev libfreetype6-dev liblcms2-dev libopenjpeg-dev' in pkg_lines
        assert 'RUN pip3 install Pillow==4.2.1' in pkg_lines

    def test_docker_snippet(self, mock_labbook):
        lb = mock_labbook[2]
        package_manager_dir = os.path.join(lb.root_dir, '.gigantum', 'env', 'custom')
        erm = RepositoryManager(mock_labbook[0])
        erm.update_repositories()
        erm.index_repositories()
        cm = ComponentManager(lb)
        custom = ['RUN true', 'RUN touch /tmp/cat', 'RUN rm /tmp/cat']
        cm.add_component("base", ENV_UNIT_TEST_REPO, ENV_UNIT_TEST_BASE, ENV_UNIT_TEST_REV)
        cm.add_packages("pip", [{"manager": "pip", "package": "requests", "version": "2.18.4"}])
        cm.add_docker_snippet('test-docker', custom, description="Apostrophe's and wėįrd çhårāčtêrś")
        ib = ImageBuilder(lb)
        l = ib.assemble_dockerfile()
        assert all([any([i in l for i in custom]) for n in custom])
