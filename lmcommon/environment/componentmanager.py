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
from typing import (Any, List, Dict, Tuple)
import glob

from typing import Optional


from lmcommon.labbook import LabBook
from lmcommon.environment.repository import ComponentRepository  # type: ignore
from lmcommon.logging import LMLogger
from lmcommon.activity import ActivityStore, ActivityType, ActivityRecord, ActivityDetailType, ActivityDetailRecord, \
    ActivityAction
from lmcommon.labbook.schemas import CURRENT_SCHEMA

logger = LMLogger.get_logger()


def strip_package_and_version(package_manager: str, package_str: str) -> Tuple[str, Optional[str]]:
    """For a particular package encoded with version, this strips off the version and returns a tuple
    containing (package-name, version). If version is not specified, it is None.
    """
    if package_manager not in ['pip3', 'pip2', 'pip', 'apt', 'conda', 'conda2', 'conda3']:
        raise ValueError(f'Unsupported package manager: {package_manager}')

    if package_manager in ['pip', 'pip2', 'pip3']:
        if '==' in package_str:
            t = package_str.split('==')
            return t[0], t[1]
        else:
            return package_str, None

    if package_manager == 'apt' or package_manager in ['conda', 'conda2', 'conda3']:
        if '=' in package_str:
            t = package_str.split('=')
            return t[0], t[1]
        else:
            return package_str, None

    raise ValueError(f'Unsupported package manager: {package_manager}')


class ComponentManager(object):
    """Class to manage the Environment Components of a given LabBook
    """

    DEFAULT_CUSTOM_DOCKER_NAME = 'user-custom-docker'

    def __init__(self, labbook: LabBook) -> None:
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
    def env_dir(self) -> str:
        """The environment directory in the given labbook"""
        return os.path.join(self.labbook.root_dir, '.gigantum', 'env')

    def _initialize_env_dir(self) -> None:
        """Method to populate the environment directory if any content is missing

        Returns:
            None
        """
        # Create/validate directory structure
        subdirs = ['base',
                   'package_manager',
                   'custom',
                   'docker']

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
useradd --shell /bin/bash -u $USER_ID -o -c "" -m giguser
export HOME=/home/giguser

# Setup /mnt/ as a safe place to put user runnable code
mkdir /mnt/labbook
chown -R giguser:root /mnt/labbook

# Setup docker sock to run as the user
chown giguser:root /run/docker.sock
chmod 777 /var/run/docker.sock

export JUPYTER_RUNTIME_DIR=/mnt/share/jupyter/runtime
chown -R giguser:root /mnt/share/

# Run the Docker Command
exec gosu giguser "$@"
""")

            short_message = "Adding missing entrypoint.sh, required for container automation"
            self.labbook.git.add(entrypoint_file)
            self.labbook.git.commit(short_message)

    def add_docker_snippet(self, name: str, docker_content: List[str], description: Optional[str] = None) -> None:
        """ Add a custom docker snippet to the environment (replacing custom dependency).

        Args:
            name: Name or identifier of the custom docker snippet
            docker_content: Content of the docker material (May make this a list of strings instead)
            description: Human-readable verbose description of what the snippet is intended to accomplish.

        Returns:
            None
        """

        if not name:
            raise ValueError('Argument `name` cannot be None or empty')

        if not name.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Argument `name` must be alphanumeric string (- and _ accepted)')

        if not docker_content:
            docker_content = []

        file_data = {
            'name': name,
            'timestamp_utc': datetime.datetime.utcnow().isoformat(),
            'description': description or "",
            'content': docker_content
        }

        with self.labbook.lock_labbook():
            docker_dir = os.path.join(self.labbook.root_dir, '.gigantum', 'env', 'docker')
            docker_file = os.path.join(docker_dir, f'{name}.yaml')
            os.makedirs(docker_dir, exist_ok=True)
            yaml_dump = yaml.dump(file_data, default_flow_style=False)
            with open(docker_file, 'w') as df:
                df.write(yaml_dump)

            logger.info(f"Wrote custom Docker snippet `{name}` to {str(self.labbook)}")
            short_message = f"Wrote custom Docker snippet `{name}`"
            self.labbook.git.add(docker_file)
            commit = self.labbook.git.commit(short_message)
            adr = ActivityDetailRecord(ActivityDetailType.ENVIRONMENT, show=True, action=ActivityAction.CREATE)
            adr.add_value('text/plain', '\n'.join(docker_content))
            ar = ActivityRecord(ActivityType.ENVIRONMENT,
                                message=short_message,
                                show=True,
                                linked_commit=commit.hexsha,
                                tags=["environment", "docker", "snippet"])
            ar.add_detail_object(adr)
            ars = ActivityStore(self.labbook)
            ars.create_activity_record(ar)

    def remove_docker_snippet(self, name: str) -> None:
        """Remove a custom docker snippet

        Args:
            name: Name or identifer of snippet to remove

        Returns:
            None
        """
        docker_dir = os.path.join(self.labbook.root_dir, '.gigantum', 'env', 'docker')
        docker_file = os.path.join(docker_dir, f'{name}.yaml')

        if not os.path.exists(docker_file):
            raise ValueError(f'Docker snippet name `{name}` does not exist')

        with self.labbook.lock_labbook():
            self.labbook.git.remove(docker_file, keep_file=False)
            short_message = f"Removed custom Docker snippet `{name}`"
            logger.info(short_message)
            commit = self.labbook.git.commit(short_message)
            adr = ActivityDetailRecord(ActivityDetailType.ENVIRONMENT, show=False, action=ActivityAction.DELETE)
            adr.add_value('text/plain', short_message)
            ar = ActivityRecord(ActivityType.ENVIRONMENT,
                                message=short_message,
                                show=False,
                                linked_commit=commit.hexsha,
                                tags=["environment", "docker", "snippet"])
            ar.add_detail_object(adr)
            ars = ActivityStore(self.labbook)
            ars.create_activity_record(ar)

    def add_packages(self, package_manager: str, packages: List[dict],
                     force: bool = False, from_base: bool = False) -> None:
        """Add a new yaml file describing the new package and its context to the labbook.

        Args:
            package_manager: The package manager (eg., "apt" or "pip3")
            packages: A dictionary of packages to install (package & version are main keys needed)
            force: Force overwriting a component if it already exists (e.g. you want to update the version)
            from_base: If a package in a base image, not deletable. Otherwise, can be deleted by LB user.

        Returns:
            None
        """
        if not package_manager:
            raise ValueError('Argument package_manager cannot be None or empty')

        # Create activity record
        ar = ActivityRecord(ActivityType.ENVIRONMENT,
                            show=True,
                            message="",
                            linked_commit="",
                            tags=["environment", 'package_manager', package_manager])

        update_cnt = 0
        add_cnt = 0
        for pkg in packages:
            version_str = f'"{pkg["version"]}"' if pkg["version"] else 'latest'

            yaml_lines = ['# Generated on: {}'.format(str(datetime.datetime.now())),
                          'manager: "{}"'.format(package_manager),
                          'package: "{}"'.format(pkg["package"]),
                          'version: {}'.format(version_str),
                          f'from_base: {str(from_base).lower()}',
                          f'schema: {CURRENT_SCHEMA}']
            yaml_filename = '{}_{}.yaml'.format(package_manager, pkg["package"])
            package_yaml_path = os.path.join(self.env_dir, 'package_manager', yaml_filename)

            # Check if package already exists
            if os.path.exists(package_yaml_path):
                if force:
                    # You are updating, since force is set and package already exists.
                    logger.warning("Updating package file at {}".format(package_yaml_path))
                    detail_msg = "Update {} managed package: {} {}".format(package_manager, pkg["package"], version_str)
                    adr = ActivityDetailRecord(ActivityDetailType.ENVIRONMENT, show=False, action=ActivityAction.EDIT)
                    update_cnt += 1
                else:
                    raise ValueError("The package {} already exists in this LabBook.".format(pkg["package"]) +
                                     " Use `force` to overwrite")
            else:
                add_cnt += 1
                detail_msg = "Add {} managed package: {} {}".format(package_manager, pkg["package"], version_str)
                adr = ActivityDetailRecord(ActivityDetailType.ENVIRONMENT, show=False, action=ActivityAction.CREATE)

            # Write the YAML to the file
            with open(package_yaml_path, 'w') as package_yaml_file:
                package_yaml_file.write(os.linesep.join(yaml_lines))

            # Create activity record
            adr.add_value('text/plain', detail_msg)
            ar.add_detail_object(adr)
            logger.info("Added package {} to labbook at {}".format(pkg["package"], self.labbook.root_dir))

        # Set activity message
        ar_msg = ""
        if add_cnt > 0:
            ar_msg = f"Added {add_cnt} {package_manager} package(s). "

        if update_cnt > 0:
            ar_msg = f"{ar_msg}Updated {update_cnt} {package_manager} package(s)"

        # Add to git
        self.labbook.git.add_all(self.env_dir)
        commit = self.labbook.git.commit(ar_msg)
        ar.linked_commit = commit.hexsha
        ar.message = ar_msg

        # Store
        ars = ActivityStore(self.labbook)
        ars.create_activity_record(ar)

    def remove_packages(self, package_manager: str, package_names: List[str]) -> None:
        """Remove yaml files describing a package and its context to the labbook.

        Args:
            package_manager: The package manager (eg., "apt" or "pip3")
            package_names: A list of packages to uninstall

        Returns:
            None
        """
        # Create activity record
        ar = ActivityRecord(ActivityType.ENVIRONMENT,
                            message="",
                            show=True,
                            linked_commit="",
                            tags=["environment", 'package_manager', package_manager])

        for pkg in package_names:
            yaml_filename = '{}_{}.yaml'.format(package_manager, pkg)
            package_yaml_path = os.path.join(self.env_dir, 'package_manager', yaml_filename)

            # Check for package to exist
            if not os.path.exists(package_yaml_path):
                raise ValueError(f"{package_manager} installed package {pkg} does not exist.")

            # Check to make sure package isn't from the base. You cannot remove packages from the base yet.
            with open(package_yaml_path, 'rt') as cf:
                package_data = yaml.load(cf)

            if not package_data:
                raise IOError("Failed to load package description")

            if package_data['from_base'] is True:
                raise ValueError("Cannot remove a package installed in the Base")

            # Delete the yaml file, which on next Dockerfile gen/rebuild will remove the dependency
            os.remove(package_yaml_path)
            if os.path.exists(package_yaml_path):
                raise ValueError(f"Failed to remove package.")

            self.labbook.git.remove(package_yaml_path)

            # Create detail record
            adr = ActivityDetailRecord(ActivityDetailType.ENVIRONMENT, show=False, action=ActivityAction.DELETE)
            adr.add_value('text/plain', f"Removed {package_manager} managed package: {pkg}")
            ar.add_detail_object(adr)
            logger.info(f"Removed {package_manager} managed package: {pkg}")

        # Add to git
        short_message = f"Removed {len(package_names)} {package_manager} managed package(s)"
        commit = self.labbook.git.commit(short_message)
        ar.linked_commit = commit.hexsha
        ar.message = short_message

        # Store
        ars = ActivityStore(self.labbook)
        ars.create_activity_record(ar)

    def add_component(self, component_class: str, repository: str, component: str, revision: int,
                      force: bool = False) -> None:
        """Method to add a component to a LabBook's environment

        Args:
            component_class(str): The class of component (e.g. "base", "custom", etc)
            repository(str): The Environment Component repository the component is in
            component(str): The name of the component
            revision(int): The revision to use (r_<revision_) in yaml filename.
            force(bool): Force overwriting a component if it already exists (e.g. you want to update the version)

        Returns:
            None
        """

        if not component_class:
            raise ValueError('component_class cannot be None or empty')

        if not repository:
            raise ValueError('repository cannot be None or empty')

        if not component:
            raise ValueError('component cannot be None or empty')

        # Get the component
        component_data = self.components.get_component(component_class, repository, component, revision)
        component_filename = "{}_{}.yaml".format(repository, component, revision)
        component_file = os.path.join(self.env_dir, component_class, component_filename)

        short_message = "Add {} environment component: {}".format(component_class, component)
        if os.path.exists(component_file):
            if not force:
                raise ValueError("The component {} already exists in this LabBook." +
                                 " Use `force` to overwrite".format(component))
            else:
                logger.warning("Updating component file at {}".format(component_file))
                short_message = "Update {} environment component: {} ".format(component_class, component)

        with open(component_file, 'wt') as cf:
            cf.write(yaml.dump(component_data, default_flow_style=False))

        if component_class == 'base':
            for manager in component_data['package_managers']:
                packages = list()
                # Build dictionary of packages
                for p_manager in manager.keys():
                    if manager[p_manager]:
                        for pkg in manager[p_manager]:
                            pkg_name, pkg_version = strip_package_and_version(p_manager, pkg)
                            packages.append({"package": pkg_name, "version": pkg_version, "manager": p_manager})

                        self.add_packages(package_manager=p_manager, packages=packages,
                                          force=True, from_base=True)

        logger.info(f"Added {component_class} from {repository}: {component} rev{revision}")

        # Add to git
        self.labbook.git.add(component_file)
        commit = self.labbook.git.commit(short_message)

        # Create a ActivityRecord
        long_message = "Added a `{}` class environment component {}\n".format(component_class, component)
        long_message = "{}\n{}\n\n".format(long_message, component_data['description'])
        long_message = "{}  - repository: {}\n".format(long_message, repository)
        long_message = "{}  - component: {}\n".format(long_message, component)
        long_message = "{}  - revision: {}\n".format(long_message, revision)

        # Create detail record
        adr = ActivityDetailRecord(ActivityDetailType.ENVIRONMENT, show=False, action=ActivityAction.CREATE)
        adr.add_value('text/plain', long_message)

        # Create activity record
        ar = ActivityRecord(ActivityType.ENVIRONMENT,
                            message=short_message,
                            linked_commit=commit.hexsha,
                            tags=["environment", component_class],
                            show=True)
        ar.add_detail_object(adr)

        # Store
        ars = ActivityStore(self.labbook)
        ars.create_activity_record(ar)

    def remove_component(self, component_class: str, repository: str, component: str) -> None:
        """Remove yaml file describing a custom component and its context to the labbook.

        Args:
            component_class: The class of component (e.g. "base", "custom", etc)
            repository: The Environment Component repository the component is in
            component: The name of the component

        Returns:
            None
        """
        if not component_class:
            raise ValueError('component_class cannot be None or empty')

        if not repository:
            raise ValueError('repository cannot be None or empty')

        if not component:
            raise ValueError('component cannot be None or empty')

        component_filename = "{}_{}.yaml".format(repository, component)
        component_file = os.path.join(self.env_dir, component_class, component_filename)

        # Check for package to exist
        if not os.path.exists(component_file):
            raise ValueError(f"{component_class} {component_file} does not exist. Failed to remove")

        # Delete the yaml file, which on next Dockerfile gen/rebuild will remove the dependency
        os.remove(component_file)
        if os.path.exists(component_file):
            raise ValueError(f"Failed to remove {component_class} {component}.")

        # Add to git
        short_message = f"Remove {component_class} component {component}"
        self.labbook.git.remove(component_file)
        commit = self.labbook.git.commit(short_message)

        # Create detail record
        adr = ActivityDetailRecord(ActivityDetailType.ENVIRONMENT, show=False, action=ActivityAction.DELETE)
        adr.add_value('text/plain', short_message)

        # Create activity record
        ar = ActivityRecord(ActivityType.ENVIRONMENT,
                            show=True,
                            message=short_message,
                            linked_commit=commit.hexsha,
                            tags=["environment", component_class])
        ar.add_detail_object(adr)

        # Store
        ars = ActivityStore(self.labbook)
        ars.create_activity_record(ar)

        logger.info(f"Removed {component_class} from {repository}: {component}")

    def get_component_list(self, component_class: str) -> List[Dict[str, Any]]:
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
        return sorted(data, key=lambda elt: elt.get('id') or elt.get('manager'))

    @property
    def base_fields(self) -> Dict[str, Any]:
        """Load the base data for this LabBook from disk"""
        base_yaml_file = glob.glob(os.path.join(self.env_dir, 'base', '*.yaml'))

        if len(base_yaml_file) != 1:
            raise ValueError(f"LabBook misconfigured. Found {len(base_yaml_file)} base configurations.")

        # If you got 1 base, load from disk
        with open(base_yaml_file[0], 'rt') as bf:
            data = yaml.load(bf)

        return data
