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
import getpass
import os
import pprint
import pytest
import shutil
import tempfile
import uuid

import docker

from lmcommon.configuration import get_docker_client
from lmcommon.dispatcher import jobs
from lmcommon.environment import ComponentManager,  RepositoryManager
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

        erm = RepositoryManager(fp.name)
        erm.update_repositories()
        erm.index_repositories()

        yield fp.name, temp_dir  # provide the fixture value

    # Remove the temp_dir
    shutil.rmtree(temp_dir)


class TestJobs(object):
    def test_success_import_export_zip(self, mock_config_file):

        # Create new LabBook to be exported
        lb = LabBook(mock_config_file[0])
        labbook_dir = lb.new(name="lb-for-export-import-test", description="Testing import-export.",
                             owner={"username": "test"})
        cm = ComponentManager(lb)
        cm.add_component("base_image", "gig-dev_environment-components", "gigantum", "ubuntu1604-python3", "0.4")
        cm.add_component("dev_env", "gig-dev_environment-components", "gigantum", "jupyter-ubuntu", "0.1")

        lb_root = lb.root_dir
        with tempfile.TemporaryDirectory() as temp_dir_path:
            # Export the labbook
            exported_archive_path = jobs.export_labbook_as_zip(lb.root_dir)

            # Delete the labbook
            shutil.rmtree(lb.root_dir)
            assert not os.path.exists(lb_root), f"LabBook at {lb_root} should not exist."

            imported_lb_path = jobs.import_labboook_from_zip(archive_path=exported_archive_path, username="test",
                                                             owner="test", config_file=mock_config_file[0])

            assert imported_lb_path == lb_root, "Imported labbook directory should be same as the one exported."

            # Do not build image in CircleCI, just return now.
            if getpass.getuser() == 'circleci':
                return

            docker_image_id = jobs.build_docker_image(os.path.join(lb_root, '.gigantum', 'env'),
                                                      "import-export-test-delete-this", True, True)

            try:
                client = get_docker_client()
                client.images.remove("import-export-test-delete-this")
            except Exception as e:
                pprint.pprint(e)
                raise

    def test_fail_import_export_zip(self, mock_config_file):

        # Create new LabBook to be exported
        lb = LabBook(mock_config_file[0])
        labbook_dir = lb.new(name="lb-fail-export-import-test", description="Failing import-export.",
                             owner={"username": "test"})
        cm = ComponentManager(lb)
        cm.add_component("base_image", "gig-dev_environment-components", "gigantum", "ubuntu1604-python3", "0.4")
        cm.add_component("dev_env", "gig-dev_environment-components", "gigantum", "jupyter-ubuntu", "0.1")

        lb_root = lb.root_dir
        with tempfile.TemporaryDirectory() as temp_dir_path:
            # Export the labbook
            try:
                exported_archive_path = jobs.export_labbook_as_zip("/tmp")
                assert False, "Exporting /tmp should fail"
            except ValueError as e:
                pass

            # Export the labbook, then remove before re-importing
            exported_archive_path = jobs.export_labbook_as_zip(lb.root_dir)

            try:
                imported_lb_path = jobs.import_labboook_from_zip(archive_path=exported_archive_path, username="test",
                                                                 owner="test", config_file=mock_config_file[0])
                assert False, f"Should not be able to import LabBook because it already exited at {lb_root}"
            except ValueError as e:
                pass

            try:
                imported_lb_path = jobs.import_labboook_from_zip(archive_path="/t", username="test",
                                                                 owner="test", config_file=mock_config_file[0])
                assert False, f"Should not be able to import LabBook from strange directory /t"
            except ValueError as e:
                pass

            shutil.rmtree(lb.root_dir)
            assert not os.path.exists(lb_root), f"LabBook at {lb_root} should not exist."
            imported_lb_path = jobs.import_labboook_from_zip(archive_path=exported_archive_path, username="test",
                                                             owner="test", config_file=mock_config_file[0])
