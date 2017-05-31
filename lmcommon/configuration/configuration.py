# Copyright 2017 FlashX, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
