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
import os
import queue
import json
from typing import (Any, Dict, List, Optional)
import time

import jupyter_client
import redis
import requests

from lmcommon.activity.processors.processor import ExecutionData
from lmcommon.configuration import get_docker_client
from lmcommon.container.utils import infer_docker_image_name
from lmcommon.activity.monitors.devenv import DevEnvMonitor
from lmcommon.activity.monitors.activity import ActivityMonitor
from lmcommon.activity.processors.jupyterlab import JupyterLabCodeProcessor, JupyterLabFileChangeProcessor, \
    JupyterLabPlaintextProcessor, JupyterLabImageExtractorProcessor
from lmcommon.activity.processors.core import ActivityShowBasicProcessor
from lmcommon.activity import ActivityType
from lmcommon.dispatcher import Dispatcher, jobs
from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()


class JupyterLabMonitor(DevEnvMonitor):
    """Class to monitor JupyterLab for the need to start Activity Monitor Instances"""

    @staticmethod
    def get_dev_env_name() -> List[str]:
        """Method to return a list of names of the development environments that this class interfaces with.
        Should be the value used in the `name` attribute of the Dev Env Environment Component"""
        return ["jupyterlab"]

    @staticmethod
    def get_container_ip(container_name: str) -> str:
        """Method to get a container IP address

        Args:
            container_name(str): Name of the container to query

        Returns:
            str
        """
        client = get_docker_client()
        container = client.containers.get(container_name)
        return container.attrs['NetworkSettings']['Networks']['bridge']['IPAddress']

    @staticmethod
    def get_sessions(key: str, redis_conn: redis.Redis) -> Dict[str, Any]:
        """Method to get and reformat session info from JupyterLab

        Args:
            key(str): The unique string used as the key in redis to track this DevEnvMonitor instance
            redis_conn(redis.Redis): A redis client

        Returns:
            dict
        """

        _, username, owner, labbook_name, _ = key.split(':')
        lb_key = infer_docker_image_name(labbook_name, owner, username)
        token = redis_conn.get(f"{lb_key}-jupyter-token").decode()
        url = redis_conn.hget(key, "url").decode()

        # Get List of active sessions
        path = f'{url}/api/sessions?token={token}'
        r = requests.get(path)
        if r.status_code != 200:
            raise IOError(f"Failed to get session listing from JupyterLab {path}")
        sessions = r.json()

        data = {}
        for session in sessions:
            data[session['kernel']['id']] = {"kernel_id": session['kernel']['id'],
                                             "kernel_name": session['kernel']['name'],
                                             "kernel_type": session['type'],
                                             "path": session['path']}
        return data

    def run(self, key: str, database=1) -> None:
        """Method called in a periodically scheduled async worker that should check the dev env and manage Activity
        Monitor Instances as needed Args:
            key(str): The unique string used as the key in redis to track this DevEnvMonitor instance
        """
        # Check if the runtime directory exists, and if not create it
        if not os.path.exists(os.environ['JUPYTER_RUNTIME_DIR']):
            os.makedirs(os.environ['JUPYTER_RUNTIME_DIR'])
            logger.info("Created Jupyter shared runtime dir: {}".format(os.environ['JUPYTER_RUNTIME_DIR']))

        # Get list of active Activity Monitor Instances from redis
        redis_conn = redis.Redis(db=database)
        activity_monitors = redis_conn.keys('{}:activity_monitor:*'.format(key))
        activity_monitors = [x.decode('utf-8') for x in activity_monitors]

        # Get author info
        author_name = redis_conn.hget(key, "author_name").decode()
        author_email = redis_conn.hget(key, "author_email").decode()

        # Get session info from Jupyter API
        sessions = self.get_sessions(key, redis_conn)

        # Check for exited kernels
        for am in activity_monitors:
            kernel_id = redis_conn.hget(am, "kernel_id").decode()
            if kernel_id not in sessions:
                logger.info("Detected exited JupyterLab kernel. Stopping monitoring for kernel id {}".format(kernel_id))
                # Kernel isn't running anymore. Clean up by setting run flag to `False` so worker exits
                redis_conn.hset(am, 'run', False)

        # Check for new kernels
        for s in sessions:
            if sessions[s]['kernel_type'] == 'notebook':
                # Monitor a notebook
                activity_monitor_key = '{}:activity_monitor:{}'.format(key, sessions[s]['kernel_id'])
                if activity_monitor_key not in activity_monitors:
                    logger.info("Detected new JupyterLab kernel. Starting monitoring for kernel id {}".format(sessions[s]['kernel_id']))

                    # Start new Activity Monitor
                    _ , user, owner, labbook_name, dev_env_name = key.split(':')

                    args = {"module_name": "lmcommon.activity.monitors.monitor_jupyterlab",
                            "class_name": "JupyterLabNotebookMonitor",
                            "user": user,
                            "owner": owner,
                            "labbook_name": labbook_name,
                            "monitor_key": activity_monitor_key,
                            "author_name": author_name,
                            "author_email": author_email,
                            "session_metadata": sessions[s]}
                    d = Dispatcher()
                    process_id = d.dispatch_task(jobs.start_and_run_activity_monitor, kwargs=args, persist=True)
                    logger.info("Started Jupyter Notebook Activity Monitor: {}".format(process_id))

                    # Update redis
                    redis_conn.hset(activity_monitor_key, "dev_env_monitor", key)
                    redis_conn.hset(activity_monitor_key, "process_id", process_id)
                    redis_conn.hset(activity_monitor_key, "path", sessions[s]["path"])
                    redis_conn.hset(activity_monitor_key, "kernel_type", sessions[s]["kernel_type"])
                    redis_conn.hset(activity_monitor_key, "kernel_name", sessions[s]["kernel_name"])
                    redis_conn.hset(activity_monitor_key, "kernel_id", sessions[s]["kernel_id"])
                    redis_conn.hset(activity_monitor_key, "run", True)


class JupyterLabNotebookMonitor(ActivityMonitor):
    """Class to monitor a notebook kernel for activity to be processed."""

    def __init__(self, user: str, owner: str, labbook_name: str, monitor_key: str, config_file: str = None,
                 author_name: Optional[str] = None, author_email: Optional[str] = None) -> None:
        """Constructor requires info to load the lab book

        Args:
            user(str): current logged in user
            owner(str): owner of the lab book
            labbook_name(str): name of the lab book
            monitor_key(str): Unique key for the activity monitor in redis
            author_name(str): Name of the user starting this activity monitor
            author_email(str): Email of the user starting this activity monitor
        """
        # Call super constructor
        ActivityMonitor.__init__(self, user, owner, labbook_name, monitor_key, config_file,
                                 author_name=author_name, author_email=author_email)

        # For now, register processors by default
        self.register_processors()

        # Tracking variables during message processing
        self.kernel_status = 'idle'
        self.current_cell = ExecutionData()
        self.cell_data: List[ExecutionData] = list()
        self.execution_count = 0

    def register_processors(self) -> None:
        """Method to register processors

        Returns:
            None
        """
        self.add_processor(JupyterLabCodeProcessor())
        self.add_processor(JupyterLabFileChangeProcessor())
        self.add_processor(JupyterLabPlaintextProcessor())
        self.add_processor(JupyterLabImageExtractorProcessor())
        self.add_processor(ActivityShowBasicProcessor())

    def handle_message(self, msg: Dict[str, Dict]):
        """Method to handle processing an IOPub Message from a JupyterLab kernel

        Args:
            msg(dict): An IOPub message


        Returns:
            None
        """
        # Initialize can_process to False. This variable is used to indicate if the cell data should be processed into
        # an ActivityRecord and saved
        if msg['msg_type'] == 'status':
            # If status was busy and transitions to idle store cell since execution has completed
            if self.kernel_status == 'busy' and msg['content']['execution_state'] == 'idle':
                if self.current_cell.cell_error is False and self.current_cell.is_empty() is False:
                    # Current cell did not error and has content
                    # Add current cell to collection of cells ready to process
                    self.cell_data.append(self.current_cell)

                # Reset current_cell attribute for next execution
                self.current_cell = ExecutionData()

                # Indicate record COULD be processed if timeout occurs
                self.can_store_activity_record = True

            elif self.kernel_status == 'idle' and msg['content']['execution_state'] == 'busy':
                # Starting to process new cell execution
                self.can_store_activity_record = False

            # Update status
            self.kernel_status = msg['content']['execution_state']

        elif msg['msg_type'] == 'execute_input':
            # A message containing the input to kernel has been received
            self.current_cell.code.append({'code': msg['content']['code']})
            self.execution_count = msg['content']['execution_count']
            self.current_cell.tags.append(f"ex:{msg['content']['execution_count']}")

        elif msg['msg_type'] == 'execute_result':
            # A message containing the output of a cell execution has been received
            if self.execution_count != msg['content']['execution_count']:
                logger.error("Execution count mismatch detected {},{}".format(self.execution_count,
                                                                              msg['content']['execution_count']))

            self.current_cell.result.append({'data': msg['content']['data'], 'metadata': msg['content']['metadata']})

        elif msg['msg_type'] == 'stream':
            # A message containing plaintext output of a cell execution has been received
            self.current_cell.result.append({'data': {"text/plain": msg['content']['text']},
                                             'metadata': {'source': 'stream'}})

        elif msg['msg_type'] == 'display_data':
            # A message containing rich output of a cell execution has been received
            self.current_cell.result.append({'data': msg['content']['data'], 'metadata': {'source': 'display_data'}})

        elif msg['msg_type'] == 'error':
            # An error occurred, so don't save this cell by resetting the current cell attribute.
            self.current_cell.cell_error = True

        else:
            logger.info("Received and ignored IOPUB Message of type {}".format(msg['msg_type']))

    def store_record(self, metadata: Dict[str, str]) -> None:
        """Method to create and store an activity record

        Args:
            metadata(dict): A dictionary of data to start the activity monitor

        Returns:
            None
        """
        if len(self.cell_data) > 0:
            t_start = time.time()

            # Process collected data and create an activity record
            activity_record = self.process(ActivityType.CODE, list(reversed(self.cell_data)), {"path": metadata["path"]})

            # Commit changes to the related Notebook file
            commit = self.commit_labbook()

            # Create note record
            activity_commit = self.store_activity_record(commit, activity_record)

            logger.info(f"Created auto-generated activity record {activity_commit} in {time.time() - t_start} seconds")

        # Reset for next execution
        self.can_store_activity_record = False
        self.cell_data = list()
        self.current_cell = ExecutionData()

    def start(self, metadata: Dict[str, str], database: int = 1) -> None:
        """Method called in a periodically scheduled async worker that should check the dev env and manage Activity
        Monitor Instances as needed

        Args:
            metadata(dict): A dictionary of data to start the activity monitor
            database(int): The database ID to use

        Returns:
            None
        """
        # Connect to the kernel
        cf = jupyter_client.find_connection_file(metadata["kernel_id"], path=os.environ['JUPYTER_RUNTIME_DIR'])
        km = jupyter_client.BlockingKernelClient()

        with open(cf, 'rt') as cf_file:
            cf_data = json.load(cf_file)

        # Get IP address of lab book container on the bridge network
        container_ip = self.get_container_ip()

        if not container_ip:
            raise ValueError("Failed to find LabBook container IP address.")
        cf_data['ip'] = container_ip

        km.load_connection_info(cf_data)

        # Get connection to the DB
        redis_conn = redis.Redis(db=database)

        try:
            while True:
                try:
                    # Check for messages, waiting up to 1 second. This is the rate that records will be merged
                    msg = km.get_iopub_msg(timeout=1)
                    self.handle_message(msg)

                except queue.Empty:
                    # if queue is empty and the record is ready to store, save it!
                    if self.can_store_activity_record is True:
                        self.store_record(metadata)

                # Check if you should exit
                if redis_conn.hget(self.monitor_key, "run").decode() == "False":
                    logger.info("Received Activity Monitor Shutdown Message for {}".format(metadata["kernel_id"]))
                    break

        except Exception as err:
            logger.error("Error in JupyterLab Activity Monitor: {}".format(err))
        finally:
            # Delete the kernel monitor key so the dev env monitor will spin up a new process
            # You may lose some activity if this happens, but the next action will sweep up changes
            redis_conn.delete(self.monitor_key)
