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

from lmcommon.labbook import LabBook
from lmcommon.environment import ComponentRepository
from lmcommon.notes import NoteStore, NoteLogLevel


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

# Setup /opt/ as a safe place to put user runnable code
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
        # Get the component
        component_data = self.components.get_component(component_class, repository, namespace, component, version)

        # Write to /.gigantum/env
        component_file = os.path.join(self.env_dir, component_class, "{}_{}_{}.yaml".format(repository,
                                                                                            namespace,
                                                                                            component))

        if os.path.exists(component_file):
            if not force:
                raise ValueError("The component {} already exists in this LabBook." +
                                 " Use `force` to overwrite".format(component))

        with open(component_file, 'wt') as cf:
            cf.write(yaml.dump(component_data, default_flow_style=False))

        # Add to git
        short_message = "Add {} environment component: {} v{}".format(component_class, component, version)
        self.labbook.git.add(component_file)
        commit = self.labbook.git.commit(short_message)

        # Create a Note record
        long_message = "Added a {} class environment component to the LabBook.\n".format(component_class)
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
