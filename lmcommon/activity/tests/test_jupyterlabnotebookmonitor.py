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

from lmcommon.activity.monitors.monitor_jupyterlab import JupyterLabNotebookMonitor, BasicJupyterLabProcessor,\
    JupyterLabImageExtractorProcessor
from lmcommon.activity.processors.core import ActivityShowBasicProcessor
from lmcommon.activity import ActivityStore, ActivityType, ActivityDetailType


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

        assert len(monitor.processors) == 3
        assert type(monitor.processors[0]) == BasicJupyterLabProcessor
        assert type(monitor.processors[1]) == JupyterLabImageExtractorProcessor
        assert type(monitor.processors[2]) == ActivityShowBasicProcessor

    def test_start(self, redis_client, mock_labbook, mock_kernel):
        """Test processing notebook activity"""
        dummy_file = os.path.join(mock_labbook[2].root_dir, 'code', 'Test.ipynb')
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
                    "path": 'code/Test.ipynb'}

        # Perform an action
        mock_kernel[0].execute("print('Hello, World')")

        # Check lab book repo state
        status = mock_labbook[2].git.status()
        assert len(status["untracked"]) == 1
        assert status["untracked"][0] == 'code/Test.ipynb'

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
        assert status["untracked"][0] == 'code/Test.ipynb'

        # Process final state change message
        monitor.handle_message(msg4, metadata)
        assert monitor.kernel_status == 'idle'

        # Check lab book repo state
        status = mock_labbook[2].git.status()
        assert len(status["untracked"]) == 0
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 0

        # Check activity entry
        log = mock_labbook[2].git.log()
        assert len(log) == 3
        assert 'code/Test.ipynb' in log[0]['message']

        a_store = ActivityStore(mock_labbook[2])
        record = a_store.get_activity_record(log[0]['commit'])
        assert record.type == ActivityType.CODE
        assert record.show is True
        assert record.importance == 0
        assert record.tags is None
        assert record.message == 'Executed cell in notebook code/Test.ipynb'
        assert len(record.detail_objects) == 3
        assert record.detail_objects[0][0] is True
        assert record.detail_objects[0][1] == ActivityDetailType.RESULT.value
        assert record.detail_objects[0][2] == 200
        assert record.detail_objects[1][0] is False
        assert record.detail_objects[1][1] == ActivityDetailType.CODE.value
        assert record.detail_objects[1][2] == 100
        assert record.detail_objects[2][0] is False
        assert record.detail_objects[2][1] == ActivityDetailType.CODE_EXECUTED.value
        assert record.detail_objects[2][2] == 128

    def test_start_modify(self, redis_client, mock_labbook, mock_kernel):
        """Test processing notebook activity and have it modify an existing file & create some files"""
        dummy_file = os.path.join(mock_labbook[2].root_dir, 'code', 'Test.ipynb')
        dummy_output = os.path.join(mock_labbook[2].root_dir, 'output', 'result.bin')
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
                    "path": 'code/Test.ipynb'}

        # Perform an action
        mock_kernel[0].execute("print('Hello, World')")

        # Check lab book repo state
        status = mock_labbook[2].git.status()
        assert len(status["untracked"]) == 1
        assert status["untracked"][0] == 'code/Test.ipynb'

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
        assert status["untracked"][0] == 'code/Test.ipynb'

        # Process final state change message
        monitor.handle_message(msg4, metadata)
        assert monitor.kernel_status == 'idle'

        # Check lab book repo state
        status = mock_labbook[2].git.status()
        assert len(status["untracked"]) == 0
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 0

        # Check activity entry
        log = mock_labbook[2].git.log()
        assert len(log) == 3
        assert 'code/Test.ipynb' in log[0]['message']

        # Mock Performing an action AGAIN, faking editing the file and generating some output files
        mock_kernel[0].execute("a=100\nprint('Hello, World 2')")
        with open(dummy_file, 'wt') as tf:
            tf.write("change the fake notebook")

        with open(dummy_output, 'wt') as tf:
            tf.write("some result data")
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
        assert len(status["staged"]) == 0
        assert len(status["untracked"]) == 1
        assert len(status["unstaged"]) == 1
        assert status["unstaged"][0][0] == 'code/Test.ipynb'
        assert status["unstaged"][0][1] == 'modified'

        # Process final state change message
        monitor.handle_message(msg4, metadata)
        assert monitor.kernel_status == 'idle'

        # Check lab book repo state
        status = mock_labbook[2].git.status()
        assert len(status["untracked"]) == 0
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 0

        # Check activity entry
        log = mock_labbook[2].git.log()
        assert len(log) == 5
        assert 'code/Test.ipynb' in log[0]['message']

        a_store = ActivityStore(mock_labbook[2])
        record = a_store.get_activity_record(log[0]['commit'])
        assert record.type == ActivityType.CODE
        assert record.show is True
        assert record.importance == 0
        assert record.tags is None
        assert record.message == 'Executed cell in notebook code/Test.ipynb'
        assert len(record.detail_objects) == 4
        assert record.detail_objects[0][0] is True
        assert record.detail_objects[0][1] == ActivityDetailType.RESULT.value
        assert record.detail_objects[0][2] == 200
        assert record.detail_objects[1][0] is False
        assert record.detail_objects[1][1] == ActivityDetailType.CODE.value
        assert record.detail_objects[1][2] == 0
        assert record.detail_objects[2][0] is False
        assert record.detail_objects[2][1] == ActivityDetailType.CODE_EXECUTED.value
        assert record.detail_objects[2][2] == 128
        assert record.detail_objects[3][0] is False
        assert record.detail_objects[3][1] == ActivityDetailType.OUTPUT_DATA.value
        assert record.detail_objects[3][2] == 100

        detail = a_store.get_detail_record(record.detail_objects[3][3].key)
        assert len(detail.data) == 1
        assert detail.data['text/markdown'] == 'Created new Output Data file `output/result.bin`'

        detail = a_store.get_detail_record(record.detail_objects[1][3].key)
        assert len(detail.data) == 1
        assert detail.data['text/markdown'] == 'Modified Code file `code/Test.ipynb`'

    def test_no_show(self, redis_client, mock_labbook, mock_kernel):
        """Test processing notebook activity that doesn't have any important detail items"""
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
                    "path": 'code/Test.ipynb'}

        # Perform an action
        mock_kernel[0].execute("a=1")

        # Check lab book repo state
        status = mock_labbook[2].git.status()
        assert len(status["untracked"]) == 0

        # Process messages
        msg1 = mock_kernel[0].get_iopub_msg()
        msg2 = mock_kernel[0].get_iopub_msg()
        msg3 = mock_kernel[0].get_iopub_msg()

        # Process first state change message
        assert monitor.kernel_status == 'idle'
        monitor.handle_message(msg1, metadata)
        assert monitor.kernel_status == 'busy'

        # Process input message
        monitor.handle_message(msg2, metadata)
        assert len(monitor.code) > 0

        # Process output message
        monitor.handle_message(msg3, metadata)

        # Check activity entry
        log = mock_labbook[2].git.log()
        assert len(log) == 3
        assert 'code/Test.ipynb' in log[0]['message']

        a_store = ActivityStore(mock_labbook[2])
        record = a_store.get_activity_record(log[0]['commit'])
        assert record.type == ActivityType.CODE
        assert record.show is False
        assert record.importance == 0
        assert record.tags is None
        assert record.message == 'Executed cell in notebook code/Test.ipynb'
        assert len(record.detail_objects) == 1
        assert record.detail_objects[0][0] is False
        assert record.detail_objects[0][1] == ActivityDetailType.CODE_EXECUTED.value
        assert record.detail_objects[0][2] == 128

    def test_add_many_files(self, redis_client, mock_labbook, mock_kernel):
        """Test processing notebook activity when lots of output files have been created"""
        for file_number in range(0, 200):
            with open(os.path.join(mock_labbook[2].root_dir, 'output', f"{file_number}.dat"), 'wt') as tf:
                tf.write("blah")

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
                    "path": 'code/Test.ipynb'}

        # Perform an action
        mock_kernel[0].execute("print('Generated 200 output files')")

        # Check lab book repo state
        status = mock_labbook[2].git.status()
        assert len(status["untracked"]) == 200

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

        # Process final state change message
        monitor.handle_message(msg4, metadata)
        assert monitor.kernel_status == 'idle'

        # Check lab book repo state
        status = mock_labbook[2].git.status()
        assert len(status["untracked"]) == 0
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 0

        # Check activity entry
        log = mock_labbook[2].git.log()
        assert len(log) == 3
        assert 'code/Test.ipynb' in log[0]['message']

        a_store = ActivityStore(mock_labbook[2])
        record = a_store.get_activity_record(log[0]['commit'])
        assert record.type == ActivityType.CODE
        assert record.show is True
        assert record.importance == 0
        assert record.tags is None
        assert record.message == 'Executed cell in notebook code/Test.ipynb'
        assert len(record.detail_objects) == 202
        assert record.detail_objects[0][0] is True
        assert record.detail_objects[0][1] == ActivityDetailType.RESULT.value
        assert record.detail_objects[0][2] == 200
        assert record.detail_objects[1][0] is False
        assert record.detail_objects[1][1] == ActivityDetailType.CODE_EXECUTED.value
        assert record.detail_objects[1][2] == 128
        assert record.detail_objects[2][0] is False
        assert record.detail_objects[2][1] == ActivityDetailType.OUTPUT_DATA.value
        assert record.detail_objects[2][2] == 255
        assert record.detail_objects[3][0] is False
        assert record.detail_objects[3][1] == ActivityDetailType.OUTPUT_DATA.value
        assert record.detail_objects[3][2] == 255
        assert record.detail_objects[47][0] is False
        assert record.detail_objects[47][1] == ActivityDetailType.OUTPUT_DATA.value
        assert record.detail_objects[47][2] == 254
        assert record.detail_objects[201][0] is False
        assert record.detail_objects[201][1] == ActivityDetailType.OUTPUT_DATA.value
        assert record.detail_objects[201][2] == 100

    def test_no_record_on_error(self, redis_client, mock_labbook, mock_kernel):
        """Test processing notebook activity that didn't execute successfully"""
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
                    "path": 'code/Test.ipynb'}

        # Perform an action
        mock_kernel[0].execute("1/0")

        # Check lab book repo state
        status = mock_labbook[2].git.status()
        assert len(status["untracked"]) == 0

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
        monitor.handle_message(msg4, metadata)

        # Check activity entry
        log = mock_labbook[2].git.log()

        # log should increment by only 1, not 2 because of error and not be an Activity Record.
        assert len(log) == 2
        assert 'GTM' not in log[0]['message']
