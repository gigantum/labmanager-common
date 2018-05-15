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
from pkg_resources import resource_filename
import json
import logging
import logging.config
import os
import time
import tempfile

from typing import (Any, Dict, Tuple)


class LMLogger(object):
    """Class for getting a configured logging instance"""
    CONFIG_INSTALLED_LOCATION = '/etc/gigantum/logging.json'

    def __init__(self, config_file=None) -> None:
        is_default = False
        if config_file:
            self.config_file = config_file
        else:
            self.config_file, is_default = self.find_default_config()

        with open(self.config_file) as cf:
            data = json.load(cf)

        if is_default:
            # Patch the log file to a tempfile, assuming you are in testing or local development mode
            with tempfile.NamedTemporaryFile(mode='at', delete=False, suffix=".log") as temp_log_file:
                data['handlers']['fileHandler']['filename'] = temp_log_file.name

        self.log_file = data['handlers']['fileHandler']['filename']
        self._make_log_dir(os.path.dirname(self.log_file))

        # Configure logging
        logging.config.dictConfig(data)

        # Get the logger
        self.logger = logging.getLogger('labmanager')

    @classmethod
    def get_logger(cls, config_file=None):
        # Note: Python does not allow forward declarations, so unless we find a
        # workaround, this method will have to remain untyped.
        logger = cls(config_file)
        return logger.logger

    @staticmethod
    def _make_log_dir(log_file_dir: str) -> str:
      """Create directory tree to log file if it does not exist. """
      if not os.path.exists(log_file_dir):
        os.makedirs(log_file_dir, exist_ok=True)
      return log_file_dir

    @staticmethod
    def find_default_config() -> Tuple[str, bool]:
        """Method to find the default configuration file

        Returns:
            (str, bool): Absolute path to the file to load, flag indicating if the Default file was loaded
        """
        # Check if file exists in the installed location
        if os.path.isfile(LMLogger.CONFIG_INSTALLED_LOCATION):
            return LMLogger.CONFIG_INSTALLED_LOCATION, False
        else:
            # Load default file out of python package
            return os.path.join(resource_filename("lmcommon", "logging"), "logging.json.default"), True


class time_profiler(object):
    def __init__(self, logger: LMLogger):
        self.logger = logger

    def __call__(self, f):
        def profiler(*args, **kwargs):
            t0 = time.time()
            try:
                r = f(*args, **kwargs)
                tfinish = time.time()
                self.logger.info(f"(method={f.__name__},time={tfinish-t0},exception=None)")
                return r
            except Exception as e:
                tfail = time.time()
                self.logger.info(f"(method={f.__name__},time={tfail-t0},exception={str(type(e))})")
                raise
        return profiler