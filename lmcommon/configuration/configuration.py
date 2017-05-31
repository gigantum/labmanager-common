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
import yaml
from pkg_resources import resource_filename


class Configuration(object):
    """Class to interact with LabManager configuration files    
    """
    INSTALLED_LOCATION = "/etc/gigantum/labmanager.yaml"

    def __init__(self, config_file=None):
        """
        
        Args:
            config_file(str): Absolute path to the configuration file to load
        """
        if config_file:
            self.config_file = config_file
        else:
            self.config_file = self.find_default_config()

        self.config = self.load(self.config_file)

    @staticmethod
    def find_default_config():
        """Method to find the default configuration file
        
        Returns:
            (str): Absolute path to the file to load
        """
        # Check if file exists in the installed location
        if os.path.isfile(Configuration.INSTALLED_LOCATION):
            return Configuration.INSTALLED_LOCATION
        else:
            # Load default file out of python package
            return os.path.join(resource_filename("lmcommon", "configuration/config"), "labmanager.yaml.default")

    def load(self, config_file=None):
        """Method to load a config file
        
        Args:
            config_file(str): Absolute path to a configuration file
        
        Returns:
            (dict)
        """
        if not config_file:
            config_file = self.config_file

        with open(config_file, "rt") as cf:
            data = yaml.load(cf)

        return data

    def save(self, config_file=None):
        """Method to save a configuration to file
        
        Args:
            config_file(str): Absolute path to a configuration file

        Returns:
            None
        """
        if not config_file:
            config_file = self.config_file

        with open(config_file, "wt") as cf:
            cf.write(yaml.dump(self.config, default_flow_style=False))
