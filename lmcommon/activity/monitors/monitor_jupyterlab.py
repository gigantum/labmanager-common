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
import traceback
from typing import (Any, Dict, List, Optional)

import jupyter_client
import redis
import requests

from lmcommon.activity.monitors.devenv import DevEnvMonitor
from lmcommon.activity.monitors.activity import ActivityMonitor
from lmcommon.activity.processors.processor import StopProcessingException
from lmcommon.activity.processors.jupyterlab import BasicJupyterLabProcessor
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
        return ["jupyterlab-ubuntu1604"]

    @staticmethod
    def get_sessions() -> Dict[str, Any]:
        """Method to get and reformat session info from JupyterLab

        Returns:
            dict
        """
        # Get List of active sessions
        r = requests.get('http://172.17.0.1:8888/api/sessions')
        if r.status_code != 200:
            raise IOError("Failed to get session listing from JupyterLab")
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

        # Get session info from Jupyter API
        sessions = self.get_sessions()

        # Get list of active Activity Monitor Instances from redis
        redis_conn = redis.Redis(db=database)
        activity_monitors = redis_conn.keys('{}:activity_monitor:*'.format(key))
        activity_monitors = [x.decode('utf-8') for x in activity_monitors]

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

    def __init__(self, user: str, owner: str, labbook_name: str, monitor_key: str, config_file: str = None) -> None:
        """Constructor requires info to load the lab book

        Args:
            user(str): current logged in user
            owner(str): owner of the lab book
            labbook_name(str): name of the lab book
            monitor_key(str): Unique key for the activity monitor in redis
        """
        # Call super constructor
        ActivityMonitor.__init__(self, user, owner, labbook_name, monitor_key, config_file)

        # For now, register python processors by default
        self.register_python_processors()

        # Tracking variables during message processing
        self.kernel_status = 'idle'
        self.code: Dict[str, Any] = {}
        self.result: Dict[str, Any] = {}
        self.execution_count = 0

    def register_python_processors(self) -> None:
        """Method to register python3 processors

        Returns:
            None
        """
        self.add_processor(BasicJupyterLabProcessor())

    def handle_message(self, msg: Dict[str, Dict], metadata: Dict[str, str]) -> None:
        """Method to handle processing an IOPub Message from a JupyterLab kernel

        Args:
            msg(dict): An IOPub message
            metadata(dict): A dictionary of data to start the activity monitor


        Returns:
            None
        """
        if msg['msg_type'] == 'status':
            # If status -> busy get messages until status -> idle
            if self.kernel_status == 'busy' and msg['content']['execution_state'] == 'idle':

                try:
                    # Process activity data to generate a note record
                    activity_record = self.process(ActivityType.CODE,
                                                   self.code, self.result, {"path": metadata["path"]})

                    # Commit changes to the related Notebook file
                    # commit = self.commit_file(metadata["path"])
                    commit = self.commit_labbook()

                    # Create note record
                    actvity_commit = self.create_activity_record(commit, activity_record)

                    # Successfully committed changes. Clear out state
                    self.result = {}
                    self.code = {}

                    logger.info("Created auto-generated note based on kernel activity: {}".format(actvity_commit))

                except StopProcessingException:
                    # Don't want to save changes. Move along.
                    self.result = {}
                    self.code = {}
                    pass

            # Update status
            self.kernel_status = msg['content']['execution_state']

        elif msg['msg_type'] == 'execute_input':
            # input sent
            self.code = {'code': msg['content']['code']}
            self.execution_count = msg['content']['execution_count']

        elif msg['msg_type'] == 'execute_result':
            # result received
            if self.execution_count != msg['content']['execution_count']:
                logger.error("Execution count mismatch detected {},{}".format(self.execution_count,
                                                                              msg['content']['execution_count']))
            self.result = {'data': msg['content']['data'], 'metadata': msg['content']['metadata']}

        elif msg['msg_type'] == 'stream':
            # result received
            self.result = {'data': {"text/plain": msg['content']['text']}, 'metadata': {}}

        else:
            logger.debug("Received and ignored IOPUB Message of type {}".format(msg['msg_type']))

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
            loop = True
            while loop:
                # get message
                # TODO: Restructure using timeout kwarg to pack together a bunch of cells run at once
                try:
                    msg = km.get_iopub_msg(timeout=4)
                    logger.debug("Received IOPUB Message from {}:\n{}".format(metadata["kernel_id"], msg))
                    self.handle_message(msg, metadata)
                except queue.Empty:
                    # if queue is empty, continue
                    pass

                # Check if you should exit
                if redis_conn.hget(self.monitor_key, "run").decode() == "False":
                    loop = False
                    logger.info("Received Activity Monitor Shutdown Message for {}".format(metadata["kernel_id"]))

        except Exception:
            tb = traceback.format_exc()
            logger.error("Error in JupyterLab Activity Monitor: {}".format(tb))
        finally:
            # Cleanup after activity manager by removing key from redis
            redis_conn.delete(self.monitor_key)



