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
import abc
import glob
import os
from typing import (Any, Dict, List, Optional)

import importlib
import redis
from pkg_resources import resource_filename

from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()


class DevEnvMonitor(metaclass=abc.ABCMeta):
    """Class to monitor a development environments for the need to start Activity Monitor Instances"""

    @staticmethod
    def get_dev_env_name() -> List[str]:
        """Method to return a list of name(s) of the development environment that this class interfaces with.
        Should be the value used in the `name` attribute of the Dev Env Environment Component"""
        raise NotImplemented

    def run(self, key: str) -> None:
        """Method called in a periodically scheduled async worker that should check the dev env and manage Activity
        Monitor Instances as needed

        Args:
            key(str): The unique string used as the key in redis to track this DevEnvMonitor instance
        """
        raise NotImplemented


class DevEnvMonitorManager(object):
    """Class to manage creating DevEnvMonitor instances"""

    def __init__(self, database=1) -> None:
        # Get available monitor classes from redis or register available classes
        # Redis is used to store this information to reduce the overhead of re-registering all classes every time
        # DevEnvMonitorManager is instantiated, which happens often, both in the LabManager API and in async workers
        redis_conn = redis.Redis(db=database)
        data = redis_conn.hgetall('##AVAILABLE_DEV_ENV_MONITOR_CLASSES##')
        if data:
            # Load the class info from redis
            # TODO: verify if loading from imports is actually faster than using this redis cache implementation
            result_dict = {}
            for key in data:
                # Decode from bytes to strings if needed
                value = data[key]
                if type(key) == bytes:
                    key = key.decode('utf-8')
                if type(value) == bytes:
                    value = value.decode('utf-8')

                module_name, class_name = value.rsplit('.', 1)
                # load the module
                m = importlib.import_module(module_name)
                # get the class and store
                result_dict[key] = getattr(m, class_name)

            self.available_monitors = result_dict
        else:
            self.available_monitors = self._register_monitor_classes()
            for key in self.available_monitors:
                logger.info("Registering DevEnvMonitor Class: {} for {}".format(self.available_monitors[key], key))
                redis_conn.hset('##AVAILABLE_DEV_ENV_MONITOR_CLASSES##', key,
                                "{}.{}".format(self.available_monitors[key].__module__,
                                               self.available_monitors[key].__name__))

    def _register_monitor_classes(self) -> Dict[str, Any]:
        """Private method to register all available Dev Env Monitor classes

        Creates a dictionary of the form {development environment name: monitor class name, ...}

        Returns:
            dict
        """
        # Dynamically find files to import that start with monitor_*
        monitor_dir = os.path.join(resource_filename('lmcommon', 'activity'), 'monitors')
        for module_name in glob.glob('{}{}monitor_*'.format(monitor_dir, os.path.sep)):
            filename = os.path.basename(module_name)
            importlib.import_module("lmcommon.activity.monitors.{}".format(filename.split(".py")[0]))

        all_monitor_classes = [cls for cls in DevEnvMonitor.__subclasses__()]

        register_data: Dict[str, Any] = {}
        for cls in all_monitor_classes:
            dev_env_name = cls.get_dev_env_name()
            if any([(name in register_data) for name in dev_env_name]):
                msg = "Two Development Environment Monitors attempting to register for a single Dev Env:"
                msg = "{}\n Dev Env: {}".format(msg, dev_env_name)
                msg = "{}\n Class 1: {}".format(msg, [register_data[n] for n in dev_env_name])
                msg = "{}\n Class 2: {}".format(msg, cls)
                raise ValueError(msg)

            # New Dev Env. Register it for all supported dev envs
            for name in dev_env_name:
                register_data[name] = cls

        return register_data

    def is_available(self, dev_env_name: str) -> bool:
        """Method to test if a dev env monitor is available for a given development environment name

        Args:
            dev_env_name(str): Name of a development environment to monitor

        Returns:
            bool
        """
        return dev_env_name in self.available_monitors

    def get_monitor_instance(self, dev_env_name: str) -> Optional[DevEnvMonitor]:
        """Method to get a Dev Env Monitor instance based on the Dev Env name

        Args:
            dev_env_name(str): Name of a development environment to monitor

        Returns:
            DevEnvMonitor
        """
        if self.is_available(dev_env_name):
            return self.available_monitors[dev_env_name]()
        else:
            return None
