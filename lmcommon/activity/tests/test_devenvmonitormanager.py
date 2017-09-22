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
from lmcommon.activity.tests.fixtures import get_redis_client_mock, redis_client

from lmcommon.activity.monitors.devenv import DevEnvMonitorManager
from lmcommon.activity.monitors.monitor_jupyterlab import JupyterLabMonitor


class TestDevEnvMonitorManager(object):
    def test_load_monitors(self, redis_client):
        """Test loading monitors from the filesystem"""
        assert redis_client.keys('##AVAILABLE_DEV_ENV_MONITOR_CLASSES##') == []

        demm = DevEnvMonitorManager()

        assert type(demm.available_monitors['jupyterlab-ubuntu1604']()) == JupyterLabMonitor
        assert redis_client.keys('##AVAILABLE_DEV_ENV_MONITOR_CLASSES##') is not None
        data = redis_client.hgetall('##AVAILABLE_DEV_ENV_MONITOR_CLASSES##')
        assert b'jupyterlab-ubuntu1604' in data

    def test_load_monitors_precached(self, redis_client):
        """Test loading monitors from redis"""
        demm = DevEnvMonitorManager()

        assert type(demm.available_monitors['jupyterlab-ubuntu1604']()) == JupyterLabMonitor
        assert redis_client.keys('##AVAILABLE_DEV_ENV_MONITOR_CLASSES##') is not None
        data = redis_client.hgetall('##AVAILABLE_DEV_ENV_MONITOR_CLASSES##')
        assert b'jupyterlab-ubuntu1604' in data

        demm2 = DevEnvMonitorManager()

        assert demm.available_monitors == demm2.available_monitors
        assert type(demm2.available_monitors['jupyterlab-ubuntu1604']()) == JupyterLabMonitor
        assert redis_client.keys('##AVAILABLE_DEV_ENV_MONITOR_CLASSES##') is not None
        data = redis_client.hgetall('##AVAILABLE_DEV_ENV_MONITOR_CLASSES##')
        assert b'jupyterlab-ubuntu1604' in data

    def test_is_available(self, redis_client):
        """Test if a dev env has a monitor available"""
        demm = DevEnvMonitorManager()

        assert demm.is_available("jupyterlab-ubuntu1604") is True
        assert demm.is_available("jsadfasdf") is False

    def test_get_monitor_instance(self, redis_client):
        """Test getting a monitor instance"""
        demm = DevEnvMonitorManager()

        monitor = demm.get_monitor_instance("jupyterlab-ubuntu1604")
        assert type(monitor) is JupyterLabMonitor


