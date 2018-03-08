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
from lmcommon.labbook import LabBook
from typing import Optional
import time
import redis
from docker.errors import NotFound

from lmcommon.logging import LMLogger
from lmcommon.configuration import get_docker_client
from lmcommon.environment import ComponentManager
from lmcommon.gitlib.git import GitAuthor
from lmcommon.activity.monitors import DevEnvMonitorManager

from lmcommon.dispatcher import Dispatcher, JobKey
from lmcommon.dispatcher.jobs import run_dev_env_monitor
from lmcommon.container.utils import infer_docker_image_name


logger = LMLogger.get_logger()


# NOTE: Redis is used to track all Activity Monitoring processes in database 1. Keys:
#
# dev_env_monitor:<user>:<owner>:<labbook name>:<dev env name> -> Hash
#       container_name: <name of the lab book container>
#       labbook_root: <absolute path to the lab book root>
#       process_id: <id for the background task>
#        ... custom fields for the specific dev env monitor class
#
# dev_env_monitor:<user>:<owner>:<labbook name>:<dev env name>:activity_monitor:<UUID> -> Hash
#       dev_env_monitor: <dev_env_monitor key>
#       process_id: <id for the background task>
#        ... custom fields for the specific activity monitor class

def start_labbook_monitor(labbook: LabBook, username: str, dev_tool: str, database: int = 1,
                          author: Optional[GitAuthor] = None) -> None:
    """Method to start Development Environment Monitors for a given Lab Book if available

    Args:
        labbook(LabBook): A populated LabBook instance to start monitoring
        username(str): The username of the logged in user
        dev_tool(str): The name of the development tool to monitor
        database(int): The redis database ID to use for key storage. Default should be 1
        author(GitAuthor): A GitAuthor instance for the current logged in user starting the monitor

    Returns:
        None
    """
    # Connect to redis
    redis_conn = redis.Redis(db=database)

    # Get all dev env monitors currently running
    dev_env_monitors = redis_conn.keys("dev_env_monitor:*")

    # Clean up after Lab Books that have "closed" by checking if the container is running
    docker_client = get_docker_client()
    for key in dev_env_monitors:
        if "activity_monitor" in key.decode():
            # Ignore all associated activity monitors, as they'll get cleaned up with the dev env monitor
            continue

        container_name = redis_conn.hget(key, 'container_name')
        try:
            docker_client.containers.get(container_name.decode())
        except NotFound:
            # Container isn't running, clean up
            logger.warn("Shutting down zombie Activity Monitoring for {}.".format(key.decode()))
            stop_dev_env_monitors(key.decode(), redis_conn, labbook.name)

    # Check if Dev Env is supported and then start Dev Env Monitor
    dev_env_mgr = DevEnvMonitorManager(database=database)

    if dev_env_mgr.is_available(dev_tool):
        # Add record to redis for Dev Env Monitor
        dev_env_monitor_key = "dev_env_monitor:{}:{}:{}:{}".format(username,
                                                                   labbook.owner['username'],
                                                                   labbook.name,
                                                                   dev_tool)

        # Schedule dev env
        d = Dispatcher()
        kwargs = {'dev_env_name': dev_tool,
                  'key': dev_env_monitor_key}
        job_key = d.schedule_task(run_dev_env_monitor, kwargs=kwargs, repeat=None, interval=3)

        redis_conn.hset(dev_env_monitor_key, "container_name", infer_docker_image_name(labbook.name,
                                                                                       labbook.owner['username'],
                                                                                       username))
        redis_conn.hset(dev_env_monitor_key, "process_id", job_key.key_str)
        redis_conn.hset(dev_env_monitor_key, "labbook_root", labbook.root_dir)

        # Set author information so activity records can be committed on behalf of the user
        if author:
            redis_conn.hset(dev_env_monitor_key, "author_name", author.name)
            redis_conn.hset(dev_env_monitor_key, "author_email", author.email)

        logger.info("Started `{}` dev env monitor for lab book `{}`".format(dev_tool, labbook.name))
    else:
        raise ValueError(f"{dev_tool} Developer Tool does not support monitoring")


def stop_dev_env_monitors(dev_env_key: str, redis_conn: redis.Redis, labbook_name: str) -> None:
    """Method to stop a dev env monitor and all related activity monitors

    Args:
        dev_env_key(str): Key in redis containing the dev env monitor info
        redis_conn(redis.Redis): The redis instance to the state db
        labbook_name(str): The name of the related lab book

    Returns:

    """
    # Unschedule dev env monitor
    d = Dispatcher()
    process_id = redis_conn.hget(dev_env_key, "process_id")
    if process_id:
        logger.info("Dev Tool process id to stop: `{}` ".format(process_id))
        d.unschedule_task(JobKey(process_id.decode()))

        _, dev_env_name = dev_env_key.rsplit(":", 1)
        logger.info("Stopped dev tool monitor `{}` for lab book `{}`. PID {}".format(dev_env_name, labbook_name,
                                                                                    process_id))
        # Remove dev env monitor key
        redis_conn.delete(dev_env_key)

        # Make sure the monitor is unscheduled so it doesn't start activity monitors again
        time.sleep(2)
    else:
        logger.info("Shutting down container with no Dev Tool monitoring processes to stop.")

    # Get all related activity monitor keys
    activity_monitor_keys = redis_conn.keys("{}:activity_monitor*".format(dev_env_key))

    # Signal all activity monitors to exit
    for am in activity_monitor_keys:
        # Set run flag in redis
        redis_conn.hset(am.decode(), "run", False)

        logger.info("Signaled activity monitor for lab book `{}` to stop".format(labbook_name))


def stop_labbook_monitor(labbook: LabBook, username: str, database: int = 1) -> None:
    """Method to stop a Development Environment Monitors for a given Lab Book

    Args:
        labbook(LabBook): A populated LabBook instance to start monitoring
        username(str): Username of the logged in user
        database(int): The redis database ID to use for key storage. Default should be 1

    Returns:
        None

    """
    # Connect to redis
    redis_conn = redis.Redis(db=database)

    # Get Dev envs in the lab book
    cm = ComponentManager(labbook)
    base_data = cm.base_fields

    for dt in base_data['development_tools']:
        dev_env_monitor_key = "dev_env_monitor:{}:{}:{}:{}".format(username,
                                                                   labbook.owner['username'],
                                                                   labbook.name,
                                                                   dt)

        stop_dev_env_monitors(dev_env_monitor_key, redis_conn, labbook.name)
