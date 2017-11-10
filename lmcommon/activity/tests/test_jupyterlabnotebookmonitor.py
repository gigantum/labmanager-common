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
from lmcommon.activity.tests.fixtures import redis_client, mock_kernel
from lmcommon.fixtures import mock_labbook
import uuid
import os

from lmcommon.activity.monitors.monitor_jupyterlab import JupyterLabNotebookMonitor, BasicJupyterLabProcessor


class TestJupyterLabNotebookMonitor(object):

    def test_init(self, redis_client, mock_labbook):
        """Test getting the supported names of the dev env monitor"""
        # Create dummy file in lab book
        dummy_file = os.path.join(mock_labbook[2].root_dir, 'Test.ipynb')
        with open(dummy_file, 'wt') as tf:
            tf.write("Dummy file")

        monitor_key = "dev_env_monitor:{}:{}:{}:{}:activity_monitor:{}".format('test',
                                                                               'test',
                                                                               'labbook1',
                                                                               'jupyterlab-ubuntu1604',
                                                                               uuid.uuid4())

        monitor = JupyterLabNotebookMonitor("test", "test", mock_labbook[2].name,
                                            monitor_key, config_file=mock_labbook[0])

        assert len(monitor.processors) == 1
        assert type(monitor.processors[0]) == BasicJupyterLabProcessor

    def test_start(self, redis_client, mock_labbook, mock_kernel):
        """Test processing notebook activity"""
        dummy_file = os.path.join(mock_labbook[2].root_dir, 'Test.ipynb')
        with open(dummy_file, 'wt') as tf:
            tf.write("Dummy file")

        monitor_key = "dev_env_monitor:{}:{}:{}:{}:activity_monitor:{}".format('test',
                                                                               'test',
                                                                               'labbook1',
                                                                               'jupyterlab-ubuntu1604',
                                                                               uuid.uuid4())

        monitor = JupyterLabNotebookMonitor("test", "test", mock_labbook[2].name,
                                            monitor_key, config_file=mock_labbook[0])

        # Setup monitoring metadata
        metadata = {"kernel_id": "XXXX",
                    "kernel_name": 'python',
                    "kernel_type": 'notebook',
                    "path": 'Test.ipynb'}

        # Perform an action
        mock_kernel[0].execute("print('Hello, World')")

        # Check lab book repo state
        status = mock_labbook[2].git.status()
        assert len(status["untracked"]) == 1
        assert status["untracked"][0] == 'Test.ipynb'

        # Process messages
        msg1 = mock_kernel[0].get_iopub_msg()
        msg2 = mock_kernel[0].get_iopub_msg()
        msg3 = mock_kernel[0].get_iopub_msg()
        msg4 = mock_kernel[0].get_iopub_msg()

        # Process first state change message
        assert monitor.kernel_status == 'idle'
        monitor.handle_message(msg1, metadata)
        assert monitor.kernel_status == 'busy'

        # Process input message
        monitor.handle_message(msg2, metadata)
        assert len(monitor.code) > 0

        # Process output message
        monitor.handle_message(msg3, metadata)
        assert len(monitor.result) > 0

        # Check lab book repo state
        status = mock_labbook[2].git.status()
        assert len(status["untracked"]) == 1
        assert status["untracked"][0] == 'Test.ipynb'

        # Process final state change message
        monitor.handle_message(msg4, metadata)
        assert monitor.kernel_status == 'idle'

        # Check lab book repo state
        status = mock_labbook[2].git.status()
        assert len(status["untracked"]) == 0
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 0

        # Check note entry
        log = mock_labbook[2].git.log()
        assert len(log) == 3
        assert 'Test.ipynb' in log[0]['message']
