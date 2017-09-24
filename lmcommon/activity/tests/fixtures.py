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
import mockredis
import redis
from unittest.mock import patch
import os
from lmcommon.labbook import LabBook
import tempfile
import uuid
import shutil
from jupyter_client.manager import start_new_kernel
import json
from pkg_resources import resource_filename


REDIS_TEST_CLIENT = None


@patch('redis.Redis', mockredis.mock_redis_client)
def get_redis_client_mock(db=1):
    global REDIS_TEST_CLIENT

    if not REDIS_TEST_CLIENT:
        REDIS_TEST_CLIENT = redis.Redis(db=db)
    return REDIS_TEST_CLIENT


@pytest.fixture()
def redis_client(monkeypatch):
    """A pytest fixture to manage getting a redis client for test purposes"""
    monkeypatch.setattr(redis, 'Redis', get_redis_client_mock)

    redis_conn = redis.Redis(db=1)

    yield redis_conn

    redis_conn.flushdb()


@pytest.fixture()
def mock_labbook():
    """A pytest fixture that creates a temporary directory, config file and lab book"""
    # Create a temporary working directory
    temp_dir = os.path.join(tempfile.tempdir, uuid.uuid4().hex)
    os.makedirs(temp_dir)

    with tempfile.NamedTemporaryFile(mode="wt") as fp:
        # Write a temporary config file
        fp.write("""core:
  team_mode: false 
  
git:
  backend: 'filesystem'
  working_directory: '{}'""".format(temp_dir))
        fp.seek(0)

        # Create labbook
        lb = LabBook(fp.name)
        lb.new(owner={"username": "default"}, name="test-labbook", description="my first labbook")

        # Create dummy file in lab book
        dummy_file = os.path.join(lb.root_dir, 'Test.ipynb')
        with open(dummy_file, 'wt') as tf:
            tf.write("Dummy file")

        yield lb, fp.name, dummy_file

    # Remove the temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture()
def mock_kernel():
    """A pytest fixture that creates a jupyter kernel"""
    km, kc = start_new_kernel(kernel_name='python3')

    yield kc, km

    km.shutdown_kernel(now=True)


class MockSessionsResponse(object):
    """A mock for the session query request call in monitor_juptyerlab.py"""
    def __init__(self, url):
        self.status_code = 200

    def json(self):
        with open(os.path.join(resource_filename("lmcommon", "activity/tests"), "mock_session_data.json"), 'rt') as j:
            data = json.load(j)
        return data
