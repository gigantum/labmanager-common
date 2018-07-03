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
import lmcommon.fixtures
from lmcommon.fixtures import mock_config_file, mock_config_with_repo
from lmcommon.environment import ComponentManager,  RepositoryManager
from lmcommon.labbook import LabBook
from lmcommon.imagebuilder import ImageBuilder


class TestJobs(object):
    def test_success_import_export_zip(self, mock_config_with_repo):

        # Create new LabBook to be exported
        lb = LabBook(mock_config_with_repo[0])
        labbook_dir = lb.new(name="unittest-lb-for-export-import-test", description="Testing import-export.",
                             owner={"username": 'unittester'})
        cm = ComponentManager(lb)
        cm.add_component("base", lmcommon.fixtures.ENV_UNIT_TEST_REPO, lmcommon.fixtures.ENV_UNIT_TEST_BASE,
                         lmcommon.fixtures.ENV_UNIT_TEST_REV)

        ib = ImageBuilder(lb)
        ib.assemble_dockerfile()

        # Make sure the destination user exists locally
        working_dir = lb.labmanager_config.config['git']['working_directory']
        os.makedirs(os.path.join(working_dir, 'unittester2', 'unittester2', 'labbooks'), exist_ok=True)

        lb_root = lb.root_dir
        with tempfile.TemporaryDirectory() as temp_dir_path:
            # Export the labbook
            export_dir = os.path.join(mock_config_with_repo[1], "export")
            exported_archive_path = jobs.export_labbook_as_zip(lb.root_dir, export_dir)
            tmp_archive_path = shutil.copy(exported_archive_path, '/tmp')

            # Delete the labbook
            shutil.rmtree(lb.root_dir)
            assert not os.path.exists(lb_root), f"LabBook at {lb_root} should not exist."

            assert os.path.exists(tmp_archive_path)
            # Now import the labbook as a new user, validating that the change of namespace works properly.
            imported_lb_path = jobs.import_labboook_from_zip(archive_path=tmp_archive_path, username='unittester2',
                                                             owner='unittester2', config_file=mock_config_with_repo[0])

            assert not os.path.exists(tmp_archive_path)
            tmp_archive_path = shutil.copy(exported_archive_path, '/tmp')
            assert os.path.exists(tmp_archive_path)

            # New path should reflect username of new owner and user.
            assert imported_lb_path == lb_root.replace('/unittester/unittester/', '/unittester2/unittester2/')
            import_lb = LabBook(mock_config_with_repo[0])
            import_lb.from_directory(imported_lb_path)

            ib = ImageBuilder(import_lb)
            ib.assemble_dockerfile(write=True)
            assert os.path.exists(os.path.join(imported_lb_path, '.gigantum', 'env', 'Dockerfile'))

            assert import_lb.data['owner']['username'] == 'unittester2'

            # After importing, the new user (in this case "cat") should be the current, active workspace.
            # And be created, if necessary.
            assert import_lb.active_branch == "gm.workspace-unittester2"
            assert not import_lb.has_remote

            # Repeat the above, except with the original user (e.g., re-importing their own labbook)
            user_import_lb = jobs.import_labboook_from_zip(archive_path=tmp_archive_path, username="unittester",
                                                           owner="unittester", config_file=mock_config_with_repo[0])
            assert not os.path.exists(tmp_archive_path)

            # New path should reflect username of new owner and user.
            assert user_import_lb
            import_lb2 = LabBook(mock_config_with_repo[0])
            import_lb2.from_directory(user_import_lb)
            assert import_lb2.data['owner']['username'] == 'unittester'
            # After importing, the new user (in this case "cat") should be the current, active workspace.
            # And be created, if necessary.
            assert import_lb2.active_branch == "gm.workspace-unittester"
            assert not import_lb2.has_remote

            build_kwargs = {
                'path': labbook_dir,
                'username': 'unittester',
                'nocache': True
            }
            docker_image_id = jobs.build_labbook_image(**build_kwargs)
            try:
                client = get_docker_client()
                client.images.remove(docker_image_id)
            except Exception as e:
                pprint.pprint(e)
                raise

    def test_success_import_export_lbk(self, mock_config_with_repo):
        """Test legacy .lbk extension still works"""
        # Create new LabBook to be exported
        lb = LabBook(mock_config_with_repo[0])
        labbook_dir = lb.new(name="unittest-lb-for-export-import-test-lbk", description="Testing import-export.",
                             owner={"username": 'unittester'})
        cm = ComponentManager(lb)
        cm.add_component("base", lmcommon.fixtures.ENV_UNIT_TEST_REPO, lmcommon.fixtures.ENV_UNIT_TEST_BASE,
                         lmcommon.fixtures.ENV_UNIT_TEST_REV)

        ib = ImageBuilder(lb)
        ib.assemble_dockerfile()

        # Make sure the destination user exists locally
        working_dir = lb.labmanager_config.config['git']['working_directory']
        os.makedirs(os.path.join(working_dir, 'unittester2', 'unittester2', 'labbooks'), exist_ok=True)

        lb_root = lb.root_dir
        with tempfile.TemporaryDirectory() as temp_dir_path:
            # Export the labbook
            export_dir = os.path.join(mock_config_with_repo[1], "export")
            exported_archive_path = jobs.export_labbook_as_zip(lb.root_dir, export_dir)
            tmp_archive_path = shutil.copy(exported_archive_path, '/tmp')

            lbk_archive_path = tmp_archive_path.replace(".zip", ".lbk")
            lbk_archive_path = shutil.copy(tmp_archive_path, lbk_archive_path)
            print(lbk_archive_path)

            # Delete the labbook
            shutil.rmtree(lb.root_dir)
            assert not os.path.exists(lb_root), f"LabBook at {lb_root} should not exist."

            assert os.path.exists(tmp_archive_path)
            # Now import the labbook as a new user, validating that the change of namespace works properly.
            imported_lb_path = jobs.import_labboook_from_zip(archive_path=lbk_archive_path, username='unittester2',
                                                             owner='unittester2', config_file=mock_config_with_repo[0])

            assert not os.path.exists(lbk_archive_path)
            tmp_archive_path = shutil.copy(exported_archive_path, '/tmp')
            assert os.path.exists(tmp_archive_path)

            # New path should reflect username of new owner and user.
            assert imported_lb_path == lb_root.replace('/unittester/unittester/', '/unittester2/unittester2/')
            import_lb = LabBook(mock_config_with_repo[0])
            import_lb.from_directory(imported_lb_path)

            ib = ImageBuilder(import_lb)
            ib.assemble_dockerfile(write=True)
            assert os.path.exists(os.path.join(imported_lb_path, '.gigantum', 'env', 'Dockerfile'))

            assert import_lb.data['owner']['username'] == 'unittester2'

            # After importing, the new user (in this case "cat") should be the current, active workspace.
            # And be created, if necessary.
            assert import_lb.active_branch == "gm.workspace-unittester2"
            assert not import_lb.has_remote

    def test_fail_import_export_zip(self, mock_config_with_repo):

        # Create new LabBook to be exported
        lb = LabBook(mock_config_with_repo[0])
        labbook_dir = lb.new(name="lb-fail-export-import-test", description="Failing import-export.",
                             owner={"username": "test"})
        cm = ComponentManager(lb)
        cm.add_component("base", lmcommon.fixtures.ENV_UNIT_TEST_REPO, lmcommon.fixtures.ENV_UNIT_TEST_BASE,
                         lmcommon.fixtures.ENV_UNIT_TEST_REV)

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
