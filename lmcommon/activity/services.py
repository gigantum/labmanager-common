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
import redis
from docker.errors import NotFound

from lmcommon.logging import LMLogger
from lmcommon.configuration import get_docker_client
from lmcommon.environment import ComponentManager
from lmcommon.activity.monitors import DevEnvMonitorManager

from lmcommon.dispatcher import Dispatcher, JobKey
from lmcommon.dispatcher.jobs import run_dev_env_monitor


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

def start_labbook_monitor(labbook: LabBook, database: int = 1) -> None:
    """Method to start Development Environment Monitors for a given Lab Book if available

    Args:
        labbook(LabBook): A populated LabBook instance to start monitoring
        database(int): The redis database ID to use for key storage. Default should be 1

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

    # Check Lab Book for Development Environments
    cm = ComponentManager(labbook)
    dev_envs = cm.get_component_list('dev_env')

    # Check if Dev Env is supported and then start Dev Env Monitor
    dev_env_mgr = DevEnvMonitorManager(database=database)
    for de in dev_envs:
        try:
            if dev_env_mgr.is_available(de['info']['name']):
                # Add record to redis for Dev Env Monitor
                dev_env_monitor_key = "dev_env_monitor:{}:{}:{}:{}".format("default",
                                                                           labbook.owner['username'],
                                                                           labbook.name,
                                                                           de['info']['name'])

                # Schedule dev env
                d = Dispatcher()
                kwargs = {'dev_env_name': de['info']['name'],
                          'key': dev_env_monitor_key}
                job_key = d.schedule_task(run_dev_env_monitor, kwargs=kwargs, repeat=None, interval=5)

                redis_conn.hset(dev_env_monitor_key, "container_name", "{}-{}-{}".format("default",
                                                                                         labbook.owner['username'],
                                                                                         labbook.name))
                redis_conn.hset(dev_env_monitor_key, "process_id", job_key.key_str)
                redis_conn.hset(dev_env_monitor_key, "labbook_root", labbook.root_dir)
                logger.info("Started `{}` dev env monitor for lab book `{}`".format(de['info']['name'], labbook.name))

        except Exception as e:
            logger.error(e)


def stop_dev_env_monitors(dev_env_key: str, redis_conn: redis.Redis, labbook_name: str) -> None:
    """Method to stop a dev env monitor and all related activity monitors

    Args:
        dev_env_key(str): Key in redis containing the dev env monitor info
        redis_conn(redis.Redis): The redis instance to the state db
        labbook_name(str): The name of the related lab book

    Returns:

    """
    # Get all related activity monitor keys
    activity_monitor_keys = redis_conn.keys("{}:activity_monitor".format(dev_env_key))

    # Signal all activity monitors to exit
    for am in activity_monitor_keys:
        # Set run flag in redis
        redis_conn.hset(am, "run", False)

        logger.info("Signaled activity monitor for lab book `{}` to stop".format(labbook_name))

    # Unschedule dev env monitor
    d = Dispatcher()
    process_id = redis_conn.hget(dev_env_key, "process_id")
    logger.info("Dev env process id to stop: `{}` ".format(process_id))
    d.unschedule_task(JobKey(process_id.decode()))

    _, dev_env_name = dev_env_key.rsplit(":", 1)
    logger.info("Stopped dev env monitor `{}` for lab book `{}`. PID {}".format(dev_env_name, labbook_name,
                                                                                process_id))


def stop_labbook_monitor(labbook: LabBook, database: int = 1) -> None:
    """Method to stop a Development Environment Monitors for a given Lab Book

    Args:
        labbook(LabBook): A populated LabBook instance to start monitoring
        database(int): The redis database ID to use for key storage. Default should be 1

    Returns:
        None

    """
    # Connect to redis
    redis_conn = redis.Redis(db=database)

    # Get Dev envs in the lab book
    cm = ComponentManager(labbook)
    dev_envs = cm.get_component_list('dev_env')

    for de in dev_envs:
        # TODO: Fix username once auth implemented properly
        dev_env_monitor_key = "dev_env_monitor:{}:{}:{}:{}".format("default",
                                                                   labbook.owner['username'],
                                                                   labbook.name,
                                                                   de['info']['name'])

        stop_dev_env_monitors(dev_env_monitor_key, redis_conn, labbook.name)

