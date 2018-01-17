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
from lmcommon.fixtures import mock_config_file, mock_config_with_repo
from lmcommon.environment import ComponentManager,  RepositoryManager
from lmcommon.labbook import LabBook


class TestJobs(object):
    def test_success_import_export_zip(self, mock_config_with_repo):

        # Create new LabBook to be exported
        lb = LabBook(mock_config_with_repo[0])
        labbook_dir = lb.new(name="lb-for-export-import-test", description="Testing import-export.",
                             owner={"username": "test"})
        cm = ComponentManager(lb)
        cm.add_component("base_image", "gig-dev_environment-components", "gigantum", "ubuntu1604-python3", "0.4")
        cm.add_component("dev_env", "gig-dev_environment-components", "gigantum", "jupyter-ubuntu", "0.1")

        lb_root = lb.root_dir
        with tempfile.TemporaryDirectory() as temp_dir_path:
            # Export the labbook
            export_dir = os.path.join(mock_config_with_repo[1], "export")
            exported_archive_path = jobs.export_labbook_as_zip(lb.root_dir, export_dir)

            # Delete the labbook
            shutil.rmtree(lb.root_dir)
            assert not os.path.exists(lb_root), f"LabBook at {lb_root} should not exist."

            # Now import the labbook as a new user, validating that the change of namespace works properly.
            imported_lb_path = jobs.import_labboook_from_zip(archive_path=exported_archive_path, username="cat",
                                                             owner="cat", config_file=mock_config_with_repo[0])

            # New path should reflect username of new owner and user.
            assert imported_lb_path == lb_root.replace('/test/test/', '/cat/cat/')
            import_lb = LabBook(mock_config_with_repo[0])
            import_lb.from_directory(imported_lb_path)
            assert import_lb.data['owner']['username'] == 'cat'
            # After importing, the new user (in this case "cat") should be the current, active workspace.
            # And be created, if necessary.
            assert import_lb.active_branch == "gm.workspace-cat"
            assert not import_lb.has_remote

            # Repeat the above, except with the original user (e.g., re-importing their own labbook)
            user_import_lb = jobs.import_labboook_from_zip(archive_path=exported_archive_path, username="test",
                                                             owner="test", config_file=mock_config_with_repo[0])

            # New path should reflect username of new owner and user.
            assert user_import_lb
            import_lb2 = LabBook(mock_config_with_repo[0])
            import_lb2.from_directory(user_import_lb)
            assert import_lb2.data['owner']['username'] == 'test'
            # After importing, the new user (in this case "cat") should be the current, active workspace.
            # And be created, if necessary.
            assert import_lb2.active_branch == "gm.workspace-test"
            assert not import_lb2.has_remote

            # Do not build image in CircleCI, just return now.
            if getpass.getuser() == 'circleci':
                return

            docker_image_id = jobs.build_docker_image(os.path.join(imported_lb_path, '.gigantum', 'env'),
                                                      "import-export-test-delete-this", True, True)
            try:
                client = get_docker_client()
                client.images.remove("import-export-test-delete-this")
            except Exception as e:
                pprint.pprint(e)
                raise

    def test_fail_import_export_zip(self, mock_config_with_repo):

        # Create new LabBook to be exported
        lb = LabBook(mock_config_with_repo[0])
        labbook_dir = lb.new(name="lb-fail-export-import-test", description="Failing import-export.",
                             owner={"username": "test"})
        cm = ComponentManager(lb)
        cm.add_component("base_image", "gig-dev_environment-components", "gigantum", "ubuntu1604-python3", "0.4")
        cm.add_component("dev_env", "gig-dev_environment-components", "gigantum", "jupyter-ubuntu", "0.1")

        lb_root = lb.root_dir
        with tempfile.TemporaryDirectory() as temp_dir_path:
            # Export the labbook
            export_dir = os.path.join(mock_config_with_repo[1], "export")
            try:
                exported_archive_path = jobs.export_labbook_as_zip("/tmp", export_dir)
                assert False, "Exporting /tmp should fail"
            except ValueError as e:
                pass

            # Export the labbook, then remove before re-importing
            exported_archive_path = jobs.export_labbook_as_zip(lb.root_dir, export_dir)

            try:
                imported_lb_path = jobs.import_labboook_from_zip(archive_path=exported_archive_path, username="test",
                                                                 owner="test", config_file=mock_config_with_repo[0])
                assert False, f"Should not be able to import LabBook because it already exited at {lb_root}"
            except ValueError as e:
                pass

            try:
                imported_lb_path = jobs.import_labboook_from_zip(archive_path="/t", username="test",
                                                                 owner="test", config_file=mock_config_with_repo[0])
                assert False, f"Should not be able to import LabBook from strange directory /t"
            except ValueError as e:
                pass

            shutil.rmtree(lb.root_dir)
            assert not os.path.exists(lb_root), f"LabBook at {lb_root} should not exist."
            imported_lb_path = jobs.import_labboook_from_zip(archive_path=exported_archive_path, username="test",
                                                             owner="test", config_file=mock_config_with_repo[0])
