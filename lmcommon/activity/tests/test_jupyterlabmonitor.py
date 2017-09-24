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
import json
from pkg_resources import resource_filename
import os
import requests
from lmcommon.activity.tests.fixtures import get_redis_client_mock, redis_client, MockSessionsResponse

from lmcommon.activity.monitors.monitor_jupyterlab import JupyterLabMonitor


class TestJupyterLabMonitor(object):

    def mock_sessions_request(self):
        with open(os.path.join(resource_filename("lmcommon", "activity/tests"), "mock_session_data.json"), 'rt') as j:
            data = json.load(j)
        return data

    def test_supported_names(self, redis_client):
        """Test getting the supported names of the dev env monitor"""
        monitor = JupyterLabMonitor()

        assert len(monitor.get_dev_env_name()) == 1
        assert monitor.get_dev_env_name()[0] == 'jupyterlab-ubuntu1604'

    def test_get_sessions(self, redis_client, monkeypatch):
        """Test getting the session information from jupyterlab"""
        monkeypatch.setattr(requests, 'get', MockSessionsResponse)
        monitor = JupyterLabMonitor()

        sessions = monitor.get_sessions()

        assert sessions['6e529520-2a6d-4adb-a2a1-de10b85b86a6']['kernel_id'] == '6e529520-2a6d-4adb-a2a1-de10b85b86a6'
        assert sessions['6e529520-2a6d-4adb-a2a1-de10b85b86a6']['kernel_name'] == 'python3'
        assert sessions['6e529520-2a6d-4adb-a2a1-de10b85b86a6']['kernel_type'] == 'notebook'
        assert sessions['6e529520-2a6d-4adb-a2a1-de10b85b86a6']['path'] == 'Untitled2.ipynb'
        assert sessions['146444cd-b4ec-4c00-b29c-d8cef4a503b0']['kernel_id'] == '146444cd-b4ec-4c00-b29c-d8cef4a503b0'
        assert sessions['146444cd-b4ec-4c00-b29c-d8cef4a503b0']['kernel_name'] == 'python3'
        assert sessions['146444cd-b4ec-4c00-b29c-d8cef4a503b0']['kernel_type'] == 'notebook'
        assert sessions['146444cd-b4ec-4c00-b29c-d8cef4a503b0']['path'] == 'code/Untitled.ipynb'

    def test_run(self, redis_client, monkeypatch):
        """Test running the monitor process"""
        monkeypatch.setattr(requests, 'get', MockSessionsResponse)
        # TODO: Mock dispatch methods once added
        monitor = JupyterLabMonitor()

        dev_env_key = "dev_env_monitor:{}:{}:{}:{}".format('default',
                                                           'default',
                                                           'test-labbook',
                                                           'jupyterlab-ubuntu1604')

        monitor.run(dev_env_key)

        data = redis_client.hgetall('{}:activity_monitor:6e529520-2a6d-4adb-a2a1-de10b85b86a6'.format(dev_env_key))
        assert data[b'kernel_id'] == b'6e529520-2a6d-4adb-a2a1-de10b85b86a6'
        assert data[b'kernel_name'] == b'python3'
        assert data[b'kernel_type'] == b'notebook'
        assert data[b'path'] == b'Untitled2.ipynb'
        assert data[b'dev_env_monitor'].decode() == dev_env_key
        assert 'rq:job' in data[b'process_id'].decode()

        data = redis_client.hgetall('{}:activity_monitor:146444cd-b4ec-4c00-b29c-d8cef4a503b0'.format(dev_env_key))
        assert data[b'kernel_id'] == b'146444cd-b4ec-4c00-b29c-d8cef4a503b0'
        assert data[b'kernel_name'] == b'python3'
        assert data[b'kernel_type'] == b'notebook'
        assert data[b'path'] == b'code/Untitled.ipynb'
        assert data[b'dev_env_monitor'].decode() == dev_env_key
        assert 'rq:job' in data[b'process_id'].decode()
