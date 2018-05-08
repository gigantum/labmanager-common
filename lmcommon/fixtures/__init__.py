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

from .fixtures import (labbook_dir_tree, mock_config_file, mock_config_with_repo,
                       mock_config_file_team, mock_config_file_with_auth, mock_labbook, mock_duplicate_labbook,
                       mock_config_with_activitystore, mock_config_lfs_disabled,
                       mock_config_with_detaildb, remote_labbook_repo, remote_bare_repo, sample_src_file,
                       _MOCK_create_remote_repo2, setup_index, build_lb_image_for_jupyterlab,
                       mock_config_file_with_auth_browser, mock_labbook_lfs_disabled,
                       mock_config_file_with_auth_first_login,cleanup_auto_import)

from .fixtures import ENV_UNIT_TEST_BASE, ENV_UNIT_TEST_REV, ENV_UNIT_TEST_REPO
