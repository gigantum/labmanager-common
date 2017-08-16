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
import datetime
import os
import yaml
import typing

import glob
from collections import OrderedDict
import operator

from lmcommon.labbook import LabBook
from lmcommon.environment import ComponentRepository
from lmcommon.notes import NoteStore, NoteLogLevel
from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()


class ComponentManager(object):
    """Class to manage the Environment Components of a given LabBook
    """

    def __init__(self, labbook: LabBook):
        """Constructor

        Args:
            labbook(LabBook): A lmcommon.labbook.LabBook instance for the LabBook you wish to manage
        """
        # Save labbook instance
        self.labbook = labbook
        # Create a component repo instance using the same config file
        self.components = ComponentRepository(config_file=self.labbook.labmanager_config.config_file)
        # Make sure the LabBook's environment directory is ready to go
        self._initialize_env_dir()

    @property
    def env_dir(self):
        """The environment directory in the given labbook"""
        return os.path.join(self.labbook.root_dir, '.gigantum', 'env')

    def _initialize_env_dir(self):
        """Method to populate the environment directory if any content is missing

        Returns:
            None
        """
        # Create/validate directory structure
        subdirs = ['base_image',
                   'dev_env',
                   'package_manager',
                   'custom']

        for subdir in subdirs:
            if not os.path.exists(os.path.join(self.env_dir, subdir)):
                os.mkdir(os.path.join(self.env_dir, subdir))

        # Add entrypoint.sh file if missing
        entrypoint_file = os.path.join(self.env_dir, 'entrypoint.sh')
        if os.path.exists(entrypoint_file) is False:
            with open(entrypoint_file, 'wt') as ef:
                ef.write("""#!/bin/bash

USER_ID=${LOCAL_USER_ID:-9001}

echo "Starting with UID: $USER_ID"
useradd --shell /bin/bash -u $USER_ID -o -c "" -m lbuser
export HOME=/home/lbuser

# Setup /mnt/ as a safe place to put user runnable code
mkdir /mnt/labbook
chown -R lbuser:root /mnt/labbook

# Setup docker sock to run as the user
chown lbuser:root /run/docker.sock
chmod 777 /var/run/docker.sock

# Run the Docker Command
exec gosu lbuser "$@"      
""")

            short_message = "Adding missing entrypoint.sh, required for container automation"
            self.labbook.git.add(entrypoint_file)
            self.labbook.git.commit(short_message)

    def add_package(self, package_manager: str, package_name: str, package_version: str=None, force=False):
        """Add a new yaml file describing the new package and its context to the labbook.

        Args:
            package_manager(str): The package manager (eg., "apt" or "pip3")
            package_name(str): Name of package (e.g., "docker" or "requests")
            package_version(str): Unique indentifier or version, for now, can be None
            force(bool): Force overwriting a component if it already exists (e.g. you want to update the version)

        Returns:
            None
        """
        if not package_manager:
            raise ValueError('Argument package_manager cannot be None or empty')

        if not package_name:
            raise ValueError('Argument package_name cannot be None or empty')

        yaml_lines = ['# Generated on: {}'.format(str(datetime.datetime.now())),
                      'package_manager: {}'.format(package_manager),
                      'name: {}'.format(package_name),
                      'version: {}'.format(package_version or 'null')]

        version_s = '_{}'.format(package_version) if package_version else ''
        yaml_filename = '{}_{}{}.yaml'.format(package_manager, package_name, version_s)
        package_yaml_path = os.path.join(self.env_dir, 'package_manager', yaml_filename)

        # Write the YAML to the file
        with open(package_yaml_path, 'w') as package_yaml_file:
            package_yaml_file.write(os.linesep.join(yaml_lines))

        # Validate that the written YAML is valid and parseable.
        with open(package_yaml_path) as package_read_file:
            yaml.load(package_read_file)

        logger.info("Added package {} to labbook at {}".format(package_name, self.labbook.root_dir))

        # Add to git
        short_message = "Add {} managed package: {} v{}".format(package_manager, package_name,
                                                                package_version or 'Latest')
        self.labbook.git.add(package_yaml_path)
        commit = self.labbook.git.commit(short_message)

        ns = NoteStore(self.labbook)
        ns.create_note({"linked_commit": commit.hexsha,
                        "message": short_message,
                        "level": NoteLogLevel.USER_MAJOR,
                        "tags": ["environment", 'package_manager', package_manager],
                        "free_text": "",
                        "objects": []
                        })

    def add_component(self, component_class: str, repository: str, namespace: str, component: str, version: str,
                      force=False):
        """Method to add a component to a LabBook's environment

        Args:
            component_class(str): The class of component (e.g. "base_image", "dev_env")
            repository(str): The Environment Component repository the component is in
            namespace(str): The namespace the component is in
            component(str): The name of the component
            version(str): The version to use
            force(bool): Force overwriting a component if it already exists (e.g. you want to update the version)

        Returns:
            None
        """

        if not component_class:
            raise ValueError('component_class cannot be None or empty')

        if not repository:
            raise ValueError('component_class cannot be None or empty')

        if not namespace:
            raise ValueError('namespace cannot be None or empty')

        if not component:
            raise ValueError('component cannot be None or empty')

        if not version:
            raise ValueError('version cannot be None or empty')

        # Get the component
        component_data = self.components.get_component(component_class, repository, namespace, component, version)

        # Write to /.gigantum/env
        component_filename = "{}_{}_{}.yaml".format(repository, namespace, component)
        component_file = os.path.join(self.env_dir, component_class, component_filename)

        if os.path.exists(component_file):
            if not force:
                raise ValueError("The component {} already exists in this LabBook." +
                                 " Use `force` to overwrite".format(component))
            else:
                logger.warning("Overwriting component file at {}".format(component_file))

        with open(component_file, 'wt') as cf:
            cf.write(yaml.dump(component_data, default_flow_style=False))

        logger.info(
            "Added {} environment component YAML file to Labbook {}".format(component_class, component_filename))

        # Add to git
        short_message = "Add {} environment component: {} v{}".format(component_class, component, version)
        self.labbook.git.add(component_file)
        commit = self.labbook.git.commit(short_message)

        # Create a Note record
        long_message = "Added a `{}` class environment component {}\n".format(component_class, component)
        long_message = "{}\n{}\n\n".format(long_message, component_data['info']['description'])
        long_message = "{}  - repository: {}\n".format(long_message, repository)
        long_message = "{}  - namespace: {}\n".format(long_message, namespace)
        long_message = "{}  - component: {}\n".format(long_message, component)
        long_message = "{}  - version: {}\n".format(long_message, version)

        ns = NoteStore(self.labbook)
        ns.create_note({"linked_commit": commit.hexsha,
                        "message": short_message,
                        "level": NoteLogLevel.USER_MAJOR,
                        "tags": ["environment", component_class],
                        "free_text": long_message,
                        "objects": []
                        })

    def get_component_list(self, component_class: str) -> typing.List[dict]:
        """Method to get the YAML contents for a given component class

        Args:
            component_class(str): The class of component you want to access

        Returns:
            list
        """
        # Get component dir
        component_dir = os.path.join(self.env_dir, component_class)
        if not os.path.exists(component_dir):
            raise ValueError("No components found for component class: {}".format(component_class))

        # Get all YAML files in dir
        yaml_files = glob.glob(os.path.join(component_dir, "*.yaml"))
        yaml_files = sorted(yaml_files)

        data = []

        # Read YAML files and write data to dictionary
        for yf in yaml_files:
            with open(yf, 'rt') as yf_file:
                yaml_data = yaml.load(yf_file)
                data.append(yaml_data)

        return data
