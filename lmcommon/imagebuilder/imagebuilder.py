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

from typing import (Any, Dict, List)
import yaml

from lmcommon.labbook import LabBook
from lmcommon.logging import LMLogger
from lmcommon.environment.utils import get_package_manager


logger = LMLogger.get_logger()


class ImageBuilder(object):
    """Class to ingest indexes describing base images, environments, and dependencies into Dockerfiles. """

    def __init__(self, labbook: LabBook) -> None:
        """Create a new image builder given the path to labbook.

        Args:
            labbook: Subject LabBook
        """
        self.labbook = labbook
        if not os.path.exists(self.labbook.root_dir):
            raise IOError("Labbook directory {} does not exist.".format(self.labbook.root_dir))
        self._validate_labbook_tree()

    def _get_yaml_files(self, directory: str) -> List[str]:
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
                   ['.gigantum', 'env', 'base'],
                   ['.gigantum', 'env', 'custom'],
                   ['.gigantum', 'env', 'package_manager']]

        for subdir in subdirs:
            if not os.path.exists(os.path.join(self.labbook.root_dir, *subdir)):
                raise ValueError("Labbook directory missing subdir `{}'".format(subdir))

    def _import_baseimage_fields(self) -> Dict[str, Any]:
        """Load fields from base_image yaml file into a convenient dict. """
        root_dir = os.path.join(self.labbook.root_dir, '.gigantum', 'env', 'base')
        base_images = self._get_yaml_files(root_dir)

        logger.debug("Searching {} for base image file".format(root_dir))
        if len(base_images) != 1:
            raise ValueError(f"There should only be one base image in {root_dir}, found {len(base_images)}")

        logger.info("Using {} as base image file for labbook at {}.".format(base_images[0], self.labbook.root_dir))
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

        root_dir = os.path.join(self.labbook.root_dir, '.gigantum', 'env', 'custom')
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
        root_dir = os.path.join(self.labbook.root_dir, '.gigantum', 'env', 'package_manager')
        package_files = [os.path.join(root_dir, n) for n in os.listdir(root_dir) if 'yaml' in n]
        docker_lines = ['## Adding individual packages']
        apt_updated = False

        for package in sorted(package_files):
            pkg_fields: Dict[str, Any] = {}

            with open(package) as package_content:
                pkg_fields.update(yaml.load(package_content))

            # Generate the appropriate docker command for the given package info
            pkg_info = {"name": str(pkg_fields['package']),
                        "version": str(pkg_fields.get('version'))}
            if not pkg_fields.get('from_base'):
                if pkg_fields['manager'] == 'apt' and not apt_updated:
                    docker_lines.append('RUN apt-get -y update')
                    apt_updated = True

                docker_lines.extend(
                    get_package_manager(pkg_fields['manager']).generate_docker_install_snippet([pkg_info]))

        return docker_lines

    def _load_docker_snippets(self) -> List[str]:
        docker_lines = ['# Custom docker snippets']
        root_dir = os.path.join(self.labbook.root_dir, '.gigantum', 'env', 'docker')
        if not os.path.exists(root_dir):
            logger.warning(f"No `docker` subdirectory for environment in labbook")
            return []

        for snippet_file in [f for f in os.listdir(root_dir) if '.yaml' in f]:
            docker_data = yaml.load(open(os.path.join(root_dir, snippet_file)))
            docker_lines.append(f'# Custom Docker: {docker_data["name"]} - {len(docker_data["content"])}'
                                f'line(s) - (Created {docker_data["timestamp_utc"]})')
            docker_lines.extend(docker_data['content'])
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
            docker_lines.append('ENV LB_HOME=/mnt/labbook')
            docker_lines.append('ENV LB_CODE=/mnt/labbook/code')
            docker_lines.append('ENV LB_INPUT=/mnt/labbook/input')
            docker_lines.append('ENV LB_OUTPUT=/mnt/labbook/output')
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
                             self._load_custom,
                             self._load_packages,
                             self._load_docker_snippets,
                             self._post_image_hook,
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

        dockerfile_name = os.path.join(self.labbook.root_dir, ".gigantum", "env", "Dockerfile")
        if write:
            logger.info("Writing Dockerfile to {}".format(dockerfile_name))

            # Get a LabBook instance
            lb = LabBook()
            lb.from_directory(self.labbook.root_dir)

            with lb.lock_labbook():
                with open(dockerfile_name, "w") as dockerfile:
                    dockerfile.write(os.linesep.join(docker_lines))
        else:
            logger.info("Dockerfile NOT being written; write=False; {}".format(dockerfile_name))

        return os.linesep.join(docker_lines)
