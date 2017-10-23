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
import os
import tempfile
import uuid
import shutil
from pkg_resources import resource_filename
import json


@pytest.fixture()
def mock_config_file():
    """A pytest fixture that creates a temporary directory and a config file to match. Deletes directory after test"""
    # Create a temporary working directory
    temp_dir = os.path.join(tempfile.tempdir, uuid.uuid4().hex)
    os.makedirs(temp_dir)

    # Load auth config for testing
    test_auth_file = os.path.join(resource_filename('lmcommon',
                                                    'auth{}tests'.format(os.path.sep)), 'auth_config.json')
    if not os.path.exists(test_auth_file):
        test_auth_file = f"{test_auth_file}.example"

    with open(test_auth_file, 'rt') as conf:
        auth_data = json.load(conf)

    with tempfile.NamedTemporaryFile(mode="wt") as fp:
        # Write a temporary config file
        fp.write("""core:
  team_mode: false 
git:
  backend: 'filesystem'
  working_directory: '{}'
auth:
  provider_domain: gigantum.auth0.com
  signing_algorithm: RS256
  audience: {}
  identity_manager: local  

  """.format(temp_dir, auth_data['audience']))
        fp.seek(0)

        yield fp.name, temp_dir, auth_data  # provide the fixture value

    # Remove the temp_dir
    shutil.rmtree(temp_dir)
