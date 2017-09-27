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
import glob
import datetime
import functools
import yaml
import os
import re
import typing

from docker.errors import NotFound
from typing import (Any, Dict, List, Union)

from lmcommon.environment.componentmanager import ComponentManager
from lmcommon.dispatcher import Dispatcher, jobs
from lmcommon.labbook import LabBook
from lmcommon.notes import NoteLogLevel, NoteStore
from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()


def dockerize_volume_path(volpath: str) -> str:
    # TODO - This must be removed and replaced.
    if os.path.__name__ == 'ntpath':
        # for windows switch the slashes and then sub the drive letter
        return re.sub('(^[A-Z]):(.*$)', '//\g<1>\g<2>', volpath.replace('\\', '/'))
    else:
        return volpath


class ImageBuilder(object):
    """Class to ingest indexes describing base images, environments, and dependencies into Dockerfiles. """

    def __init__(self, labbook_directory: str) -> None:
        """Create a new image builder given the path to labbook.

        Args:
            labbook_directory(str): Directory path to labook
        """
        self.labbook_directory = labbook_directory
        if not os.path.exists(self.labbook_directory):
            raise IOError("Labbook directory {} does not exist.".format(self.labbook_directory))
        self._validate_labbook_tree()

    def _get_yaml_files(self, directory: str) -> typing.List[typing.AnyStr]:
        """Method to get all YAML files in a directory

        Args:
            directory(str): Directory to search

        Returns:
            list
        """
        return [x for x in glob.glob("{}{}*.yaml".format(directory, os.path.sep))]

    def _validate_labbook_tree(self) -> None:
        """Throw exception if labbook directory structure not in expected format. """
        subdirs = [['.gigantum'],
                   ['.gigantum', 'env'],
                   ['.gigantum', 'env', 'base_image'],
                   ['.gigantum', 'env', 'custom'],
                   ['.gigantum', 'env', 'dev_env'],
                   ['.gigantum', 'env', 'package_manager']]

        for subdir in subdirs:
            if not os.path.exists(os.path.join(self.labbook_directory, *subdir)):
                raise ValueError("Labbook directory missing subdir `{}'".format(subdir))

    def _import_baseimage_fields(self) -> Dict[str, Any]:
        """Load fields from base_image yaml file into a convenient dict. """
        root_dir = os.path.join(self.labbook_directory, '.gigantum', 'env', 'base_image')
        base_images = self._get_yaml_files(root_dir)

        logger.debug("Searching {} for base image file".format(root_dir))
        assert len(base_images) == 1, "There should only be one base image in {}".format(root_dir)

        logger.info("Using {} as base image file for labbook at {}.".format(base_images[0], self.labbook_directory))
        with open(base_images[0]) as base_image_file:
            fields = yaml.load(base_image_file)

        return fields

    def _load_baseimage(self) -> List[str]:
        """Search expected directory structure to find the base image. Only one should exist. """

        fields = self._import_baseimage_fields()
        generation_ts = str(datetime.datetime.now())
        docker_owner_ns = fields['image']['namespace']
        docker_repo = fields['image']['repo']
        docker_tag = fields['image']['tag']

        docker_lines: List[str] = []
        docker_lines.append("# Dockerfile generated on {}".format(generation_ts))
        docker_lines.append("# Name: {}".format(fields["info"]["human_name"]))
        docker_lines.append("# Description: {}".format(fields["info"]["description"]))
        docker_lines.append("# Author: {} <{}>, {}".format(fields['author']['name'], fields['author']['email'],
                                                           fields['author']['organization']))
        docker_lines.append("")
        docker_lines.append("FROM {}/{}:{}".format(docker_owner_ns, docker_repo, docker_tag))

        return docker_lines

    def _load_devenv(self) -> List[str]:
        """Load dev environments from yaml file in expected location. """

        root_dir = os.path.join(self.labbook_directory, '.gigantum', 'env', 'dev_env')
        dev_envs = self._get_yaml_files(root_dir)

        docker_lines = []
        for dev_env in dev_envs:
            with open(dev_env) as current_dev_env:
                fields = yaml.load(current_dev_env)

            docker_lines.append("### Development Environment: {}".format(fields['info']['name']))
            docker_lines.append("# Description: {}".format(fields['info']['description']))
            docker_lines.append("# Version {}.{} by {} <{}>".format(fields['info']['version_major'],
                                                                    fields['info']['version_minor'],
                                                                    fields['author']['name'],
                                                                    fields['author']['email']))
            docker_lines.append("# Environment installation instructions:")
            docker_lines.extend(["EXPOSE {}".format(port) for port in fields['exposed_tcp_ports']])
            docker_lines.extend(["RUN {}".format(cmd) for cmd in fields['install_commands']])

            docker_lines.append("# Finished section {}".format(fields['info']['name']))
            docker_lines.append("")

        return docker_lines

    def _load_custom(self) -> List[str]:
        """Load custom dependencies, specifically the docker snippet"""

        root_dir = os.path.join(self.labbook_directory, '.gigantum', 'env', 'custom')
        custom_dep_files = self._get_yaml_files(root_dir)


        docker_lines = ['## Adding Custom Packages']
        for custom in sorted(custom_dep_files):
            pkg_fields = {}
            with open(custom) as custom_content:
                pkg_fields.update(yaml.load(custom_content))
                docker_lines.append('## Installing {}'.format(pkg_fields['info']['description']))
                docker_lines.extend(pkg_fields['docker'].split(os.linesep))

        return docker_lines

    def _load_packages(self) -> List[str]:
        """Load packages from yaml files in expected location in directory tree. """
        """ Contents of docker setup that must be at end of Dockerfile. """
        fields = self._import_baseimage_fields()
        package_managers = {c['name']: c for c in fields['available_package_managers']}

        root_dir = os.path.join(self.labbook_directory, '.gigantum', 'env', 'package_manager')
        package_files = self._get_yaml_files(root_dir)

        docker_lines = ['## Adding individual packages']
        for package in sorted(package_files):
            pkg_fields = {}
            with open(package) as package_content:
                pkg_fields.update(yaml.load(package_content))
            manager = pkg_fields.get('package_manager')
            package_name = pkg_fields.get('name')
            package_version = pkg_fields.get('version')
            docker_lines.append(package_managers[manager]['docker'].replace('$PKG$', package_name))

        return docker_lines

    def _post_image_hook(self) -> List[str]:
        """Contents that must be after baseimages but before development environments. """
        docker_lines = ["# Post-image creation hooks"]
        docker_lines.append('RUN apt-get -y install supervisor curl gosu')
        docker_lines.append('COPY entrypoint.sh /usr/local/bin/entrypoint.sh')
        docker_lines.append('RUN chmod u+x /usr/local/bin/entrypoint.sh')
        docker_lines.append('')

        return docker_lines

    def _entrypoint_hooks(self):
        """ Contents of docker setup that must be at end of Dockerfile. """
        try:
            root_dir = os.path.join(self.labbook_directory, '.gigantum', 'env', 'dev_env')
            dev_envs = self._get_yaml_files(root_dir)

            assert len(dev_envs) == 1, "Currently only one development environment is supported."

            with open(dev_envs[0]) as dev_env_file:
                fields = yaml.load(dev_env_file)

            docker_lines = ['## Entrypoint hooks']
            docker_lines.append("# Run Environment")
            docker_lines.append('ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]')
            docker_lines.append('WORKDIR /mnt/labbook')

            for cmd in fields['exec_commands']:
                tokenized_args = [c.strip().replace('"', "'") for c in cmd.split(' ') if c]
                quoted_args = ['"{}"'.format(arg) for arg in tokenized_args]
                cmd_str = 'CMD [{}]'.format(", ".join(quoted_args))
                docker_lines.append(cmd_str)

        except Exception as e:
            logger.error(e)

        return docker_lines

    def assemble_dockerfile(self, write: bool=False) -> str:
        """Create the content of a Dockerfile per the fields in the indexed data.

        Returns:
            str - Content of Dockerfile in single string using os.linesep as line separator.
        """
        assembly_pipeline = [self._load_baseimage,
                             self._post_image_hook,
                             self._load_devenv,
                             self._load_custom,
                             self._load_packages,
                             self._entrypoint_hooks]

        # flat map the results of executing the pipeline.
        try:
            docker_lines = functools.reduce(lambda a, b: a + b, [f() for f in assembly_pipeline], [])
        except KeyError as e:
            logger.error('Component file missing key: {}'.format(e))
            raise
        except Exception as e:
            logger.error(e)

        dockerfile_name = os.path.join(self.labbook_directory, ".gigantum", "env", "Dockerfile")
        if write:
            logger.info("Writing Dockerfile to {}".format(dockerfile_name))

            with open(dockerfile_name, "w") as dockerfile:
                dockerfile.write(os.linesep.join(docker_lines))

            # Get a LabBook instance
            lb = LabBook()
            lb.from_directory(self.labbook_directory)

            # Add updated dockerfile to git
            short_message = "Re-Generated Dockerfile"
            lb.git.add(dockerfile_name)
            commit = lb.git.commit(short_message)

            # Create a note record
            ns = NoteStore(lb)
            ns.create_note({"linked_commit": commit.hexsha,
                            "message": short_message,
                            "level": NoteLogLevel.AUTO_MINOR,
                            "tags": ["environment", 'dockerfile'],
                            "free_text": "",
                            "objects": []
                            })
        else:
            logger.info("Dockerfile NOT being written; write=False; {}".format(dockerfile_name))

        return os.linesep.join(docker_lines)

    def build_image(self, docker_client, image_tag: str, assemble: bool=True, nocache: bool=False, background=False):
        """Build docker image according to the Dockerfile just assembled.

        Args:
            docker_client(docker.client): Docker context
            image_tag(str): Tag of docker image
            assemble(bool): Re-assemble the docker file using assemble_dockerfile if True
            nocache(bool): Don't user the Docker cache if True
            background(bool): Run the task in the background using the dispatcher.

        Returns:
            dict: Contains the following keys, 'background_job_key' and 'docker_image_id', depending
                  if run in the background or foreground, respectively.
        """
        # Make sure image isn't running in container currently. If so, stop it.
        try:
            build_container = docker_client.containers.get(image_tag)
            build_container.stop()
            build_container.remove()
        except NotFound:
            # Container isn't running, so just move on
            # TODO: Add logging.info to indicate building a non-running container
            pass

        if not image_tag:
            raise ValueError("image_tag cannot be None or empty")

        env_dir = os.path.join(self.labbook_directory, '.gigantum', 'env')
        logger.info("Building labbook image (tag {}) from Dockerfile in {}".format(image_tag, env_dir))
        if not os.path.exists(env_dir):
            raise ValueError('Expected env directory `{}` does not exist.'.format(env_dir))

        if assemble:
            self.assemble_dockerfile(write=True)

        return_keys: Dict[str, Union[str, Any]] = {
            'background_job_key': None,
            'docker_image_id': None
        }

        if background:
            job_dispatcher = Dispatcher()
            # FIXME -- Labbook owner and user should be properly loaded and not be "default"
            job_metadata = {
                'labbook': "{}-{}-{}".format("default", "default", self.labbook_directory.split('/')[-1]),
                'method': 'build_image'}
            job_key = job_dispatcher.dispatch_task(jobs.build_docker_image, args=(env_dir, image_tag, True, nocache),
                                                   metadata=job_metadata)
            return_keys['background_job_key'] = job_key
        else:
            docker_image = docker_client.images.build(path=env_dir, tag=image_tag, pull=True, nocache=nocache)
            return_keys['docker_image_id'] = docker_image.id

        return return_keys

    def run_container(self, docker_client, docker_image_id, labbook: LabBook, background=False):
        """Launch docker container from image that was just (re-)built.

        Args:
            docker_client(docker.client): Docker context
            docker_image_id(str): Docker image to be launched.
            labbook(LabBook): Labbook context.
            background(bool): Run the task in the background using the dispatcher

        Returns:
            dict: Sets keys 'background_job_key' or 'docker_container_id' if background is True, respectively.
        """

        if not docker_image_id:
            raise ValueError("docker_image_id cannot be None or empty")

        env_manager = ComponentManager(labbook)
        dev_envs_list = env_manager.get_component_list('dev_env')

        # Ensure that base_image_list is exactly a list of one element.
        if not dev_envs_list:
            logger.error('No development environment in labbok at {}'.format(labbook.root_dir))

        # Produce port mappings to labbook container.
        # For now, we map host-to-container ports without any indirection
        # (e.g., port 8888 on the host maps to port 8888 in the container)
        exposed_ports = {}
        for dev_env in dev_envs_list:
            exposed_ports.update({"{}/tcp".format(port): port for port in dev_env['exposed_tcp_ports']})

        mnt_point = labbook.root_dir.replace('/mnt/gigantum', os.environ.get('HOST_WORK_DIR'))

        # Setup mount point for "application" share dir. A mount shared between lab book and labmanager containers
        app_share_mnt_point = os.path.join(os.environ.get('HOST_WORK_DIR'), '.labmanager', 'share')
        logger.info("Kicking of container, share: {}".format(app_share_mnt_point))

        # Map volumes - The labbook docker container is unaware of labbook name, all labbooks
        # map to /mnt/labbook.
        volumes_dict = {
            mnt_point: {'bind': '/mnt/labbook', 'mode': 'rw'},
            app_share_mnt_point:  {'bind': '/mnt/share', 'mode': 'rw'}
        }

        # If re-mapping permissions, be sure to configure the container
        if 'LOCAL_USER_ID' in os.environ:
            env_var = ["LOCAL_USER_ID={}".format(os.environ['LOCAL_USER_ID'])]
            logger.info("Starting labbook container with user: {}".format(env_var))
        else:
            env_var = []

        # If using Jupyter, set work dir (TEMPORARY HARD CODE)
        if 'JUPYTER_RUNTIME_DIR' in os.environ:
            env_var.append("JUPYTER_RUNTIME_DIR={}".format(os.environ['JUPYTER_RUNTIME_DIR']))

        logger.info("Starting labbook container with environment variables: {}".format(env_var))

        # Finally, run the image in a container.
        logger.info(
            "Running container id {} -- ports {} -- volumes {}".format(docker_image_id, ', '.join(exposed_ports.keys()),
                                                                       ', '.join(volumes_dict.keys())))

        return_keys: Dict[str, Union[Any, str]] = {
            'background_job_key': None,
            'docker_container_id': None
        }

        if background:
            logger.info("Launching container in background for container {}".format(docker_image_id))
            job_dispatcher = Dispatcher()
            # FIXME XXX TODO -- Note that labbook.user throws an excpetion, so putting in labbook.owner for now
            job_metadata = {'labbook': '{}-{}-{}'.format(labbook.owner, labbook.owner, labbook.name),
                            'method': 'run_container'}

            try:
                key = job_dispatcher.dispatch_task(jobs.start_docker_container,
                                                   args=(docker_image_id, exposed_ports, volumes_dict, env_var),
                                                   metadata=job_metadata)
            except Exception as e:
                logger.exception(e, exc_info=True)
                raise

            logger.info("Background job key for run_container: {}".format(key))
            return_keys['background_job_key'] = key
        else:
            logger.info("Launching container in-process for container {}".format(docker_image_id))
            if float(docker_client.version()['ApiVersion']) < 1.25:
                container = docker_client.containers.run(docker_image_id,
                                                         detach=True,
                                                         name=docker_image_id,
                                                         ports=exposed_ports,
                                                         environment=env_var,
                                                         volumes=volumes_dict)
            else:
                container = docker_client.containers.run(docker_image_id,
                                                         detach=True,
                                                         init=True,
                                                         name=docker_image_id,
                                                         ports=exposed_ports,
                                                         environment=env_var,
                                                         volumes=volumes_dict)
            return_keys['docker_container_id'] = container.id
        return return_keys


if __name__ == '__main__':
    """Helper utility to run imagebuilder from the command line. """
    ib = ImageBuilder(os.getcwd())
    ib.assemble_dockerfile(write=True)
