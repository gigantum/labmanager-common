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
import functools
import glob
import os
import re
from typing import (Any, Dict, List, Optional, Union)
import yaml

from docker.errors import NotFound

from lmcommon.environment.componentmanager import ComponentManager
from lmcommon.dispatcher import Dispatcher, jobs
from lmcommon.labbook import LabBook
from lmcommon.logging import LMLogger
from lmcommon.activity import ActivityDetailType, ActivityType, ActivityRecord, ActivityDetailRecord, ActivityStore

from .dockermapper import map_package_to_docker


logger = LMLogger.get_logger()


def dockerize_path(volpath: str) -> str:
    if os.environ.get('WINDOWS_HOST'):
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

    def _get_yaml_files(self, directory: str) -> List[str]:
        """Method to get all YAML files in a directory

        Args:
            directory(str): Directory to search

        Returns:
            list
        """
        return [x for x in glob.glob("{}{}*.yaml".format(directory, os.path.sep))]
        #return [n for n in os.listdir(directory) if '.yaml' in n]

    def _validate_labbook_tree(self) -> None:
        """Throw exception if labbook directory structure not in expected format. """
        subdirs = [['.gigantum'],
                   ['.gigantum', 'env'],
                   ['.gigantum', 'env', 'base'],
                   ['.gigantum', 'env', 'custom'],
                   ['.gigantum', 'env', 'package_manager']]

        for subdir in subdirs:
            if not os.path.exists(os.path.join(self.labbook_directory, *subdir)):
                raise ValueError("Labbook directory missing subdir `{}'".format(subdir))

    def _import_baseimage_fields(self) -> Dict[str, Any]:
        """Load fields from base_image yaml file into a convenient dict. """
        root_dir = os.path.join(self.labbook_directory, '.gigantum', 'env', 'base')
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
        docker_repo = fields['image']['repository']
        docker_tag = fields['image']['tag']

        docker_lines: List[str] = []
        docker_lines.append("# Dockerfile generated on {}".format(generation_ts))
        docker_lines.append("# Name: {}".format(fields["name"]))
        docker_lines.append("# Description: {}".format(fields["description"]))
        docker_lines.append("")

        # Must remove '_' if its in docker hub namespace.
        prefix = '' if '_' in docker_owner_ns else f'{docker_owner_ns}/'
        docker_lines.append("FROM {}{}:{}".format(prefix, docker_repo, docker_tag))

        return docker_lines

    def _load_custom(self) -> List[str]:
        """Load custom dependencies, specifically the docker snippet"""

        root_dir = os.path.join(self.labbook_directory, '.gigantum', 'env', 'custom')
        custom_dep_files = self._get_yaml_files(root_dir)


        docker_lines = ['## Adding Custom Packages']
        for custom in sorted(custom_dep_files):
            pkg_fields: Dict[str, Any] = {}
            with open(custom) as custom_content:
                pkg_fields.update(yaml.load(custom_content))
                docker_lines.append('## Installing {}'.format(pkg_fields['name']))
                docker_lines.extend(pkg_fields['docker'].split(os.linesep))

        return docker_lines

    def _load_packages(self) -> List[str]:
        """Load packages from yaml files in expected location in directory tree. """
        """ Contents of docker setup that must be at end of Dockerfile. """
        fields = self._import_baseimage_fields()
        root_dir = os.path.join(self.labbook_directory, '.gigantum', 'env', 'package_manager')
        package_files = [os.path.join(root_dir, n) for n in os.listdir(root_dir) if 'yaml' in n]

        docker_lines = ['## Adding individual packages']
        for package in sorted(package_files):
            pkg_fields: Dict[str, Any] = {}

            with open(package) as package_content:
                pkg_fields.update(yaml.load(package_content))
            manager = pkg_fields['manager']
            package_name = pkg_fields['package']
            package_version = pkg_fields.get('version')
            from_base = pkg_fields.get('from_base') or False
            if True:
                # Generate the appropriate docker command for the given package info
                dl = map_package_to_docker(str(manager), str(package_name), package_version)
                docker_lines.extend(dl)

        return docker_lines

    def _post_image_hook(self) -> List[str]:
        """Contents that must be after baseimages but before development environments. """
        docker_lines = ["# Post-image creation hooks"]
        docker_lines.append('COPY entrypoint.sh /usr/local/bin/entrypoint.sh')
        docker_lines.append('RUN chmod u+x /usr/local/bin/entrypoint.sh')
        docker_lines.append('')

        return docker_lines

    def _entrypoint_hooks(self):
        """ Contents of docker setup that must be at end of Dockerfile. """
        try:
            docker_lines = ['## Entrypoint hooks']
            docker_lines.append("# Run Environment")
            docker_lines.append('ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]')
            docker_lines.append('WORKDIR /mnt/labbook')
            docker_lines.append('')
            docker_lines.append('# Use this command to make the container run indefinitely')
            docker_lines.append('CMD ["tail", "-f", "/dev/null"]')
            docker_lines.append('')
        except Exception as e:
            logger.error(e)
        return docker_lines

    def assemble_dockerfile(self, write: bool = True) -> str:
        """Create the content of a Dockerfile per the fields in the indexed data.

        Returns:
            str - Content of Dockerfile in single string using os.linesep as line separator.
        """
        assembly_pipeline = [self._load_baseimage,
                             self._post_image_hook,
                             self._load_custom,
                             self._load_packages,
                             self._entrypoint_hooks]

        # flat map the results of executing the pipeline.
        try:
            docker_lines: List[str] = functools.reduce(lambda a, b: a + b, [f() for f in assembly_pipeline], [])
        except KeyError as e:
            logger.error('Component file missing key: {}'.format(e))
            raise
        except Exception as e:
            logger.error(e)
            raise

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

            # Create detail record
            adr = ActivityDetailRecord(ActivityDetailType.ENVIRONMENT, show=False)
            adr.add_value('text/plain', short_message)

            # Create activity record
            ar = ActivityRecord(ActivityType.ENVIRONMENT,
                                message=short_message,
                                show=False,
                                linked_commit=commit.hexsha,
                                tags=['dockerfile'])
            ar.add_detail_object(adr)

            # Store
            ars = ActivityStore(lb)
            ars.create_activity_record(ar)

        else:
            logger.info("Dockerfile NOT being written; write=False; {}".format(dockerfile_name))

        return os.linesep.join(docker_lines)

    def build_image(self, docker_client, image_tag: str, username: str, assemble: bool = True, nocache: bool = False,
                    background: bool = False, owner: Optional[str] = None) -> Dict[str, Optional[str]]:
        """Build docker image according to the Dockerfile just assembled.

        Args:
            docker_client(docker.client): Docker context
            image_tag(str): Tag of docker image
            assemble(bool): Re-assemble the docker file using assemble_dockerfile if True
            nocache(bool): Don't user the Docker cache if True
            background(bool): Run the task in the background using the dispatcher.
            username(str): The current logged in username
            owner(str): The owner of the lab book

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

        return_keys: Dict[str, Optional[str]] = {
            'background_job_key': None,
            'docker_image_id': None
        }

        if background:
            job_dispatcher = Dispatcher()
            # No owner provided, assume user's namespace
            if not owner:
                owner = username
            job_metadata = {
                'labbook': "{}-{}-{}".format(username, owner, self.labbook_directory.split('/')[-1]),
                'method': 'build_image'}
            job_key = job_dispatcher.dispatch_task(jobs.build_docker_image, args=(env_dir, image_tag, True, nocache),
                                                   metadata=job_metadata)
            return_keys['background_job_key'] = job_key.key_str
        else:
            docker_image = docker_client.images.build(path=env_dir, tag=image_tag, pull=True, nocache=nocache)
            return_keys['docker_image_id'] = docker_image.id

        return return_keys

    def run_container(self, docker_client, docker_image_id: str, labbook: LabBook,
                      background: bool = False) -> Dict[str, Optional[str]]:
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

        if not os.environ.get('HOST_WORK_DIR'):
            raise ValueError("Environment variable HOST_WORK_DIR must be set")

        env_manager = ComponentManager(labbook)

        # Produce port mappings to labbook container.
        # For now, we map host-to-container ports without any indirection
        # (e.g., port 8888 on the host maps to port 8888 in the container)
        exposed_ports: Dict[Any, Any] = {}
        
        mnt_point = dockerize_path(labbook.root_dir.replace('/mnt/gigantum', os.environ['HOST_WORK_DIR']))

        # Map volumes - The labbook docker container is unaware of labbook name, all labbooks
        # map to /mnt/labbook.
        volumes_dict = {
            mnt_point: {'bind': '/mnt/labbook', 'mode': 'cached'},
            'labmanager_share_vol':  {'bind': '/mnt/share', 'mode': 'rw'}
        }

        # If re-mapping permissions, be sure to configure the container
        if 'LOCAL_USER_ID' in os.environ:
            env_var = ["LOCAL_USER_ID={}".format(os.environ['LOCAL_USER_ID'])]
            logger.info("Starting labbook container with user: {}".format(env_var))
        else:
            env_var = ["WINDOWS_HOST=1"]

        # If using Jupyter, set work dir (TEMPORARY HARD CODE)
        if 'JUPYTER_RUNTIME_DIR' in os.environ:
            env_var.append("JUPYTER_RUNTIME_DIR={}".format(os.environ['JUPYTER_RUNTIME_DIR']))

        logger.info("Starting labbook container with environment variables: {}".format(env_var))

        # Finally, run the image in a container.
        logger.info(
            "Running container id {} -- ports {} -- volumes {}".format(docker_image_id, ', '.join(exposed_ports.keys()),
                                                                       ', '.join(volumes_dict.keys())))

        return_keys: Dict[str, Optional[str]] = {
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

            logger.info(f"Background job key for run_container: {key}")
            return_keys['background_job_key'] = key.key_str
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
