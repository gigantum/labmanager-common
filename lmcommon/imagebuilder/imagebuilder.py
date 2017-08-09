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
import typing
import yaml
import os


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

    def _validate_labbook_tree(self) -> None:
        """Throw exception if labbook directory structure not in expected format. """
        subdirs = [['.gigantum'],
                   ['.gigantum', 'env'],
                   ['.gigantum', 'env', 'base_image'],
                   ['.gigantum', 'env', 'dev_env'],
                   ['.gigantum', 'env', 'package_manager']]

        for subdir in subdirs:
            if not os.path.exists(os.path.join(self.labbook_directory, *subdir)):
                raise ValueError("Labbook directory missing subdir `{}'".format(subdir))

    def _import_baseimage_fields(self) -> typing.Dict[str, typing.Any]:
        """Load fields from base_image yaml file into a convenient dict. """
        root_dir = os.path.join(self.labbook_directory, '.gigantum', 'env', 'base_image')
        base_images = [os.path.join(root_dir, f) for f in os.listdir(root_dir)
                       if os.path.isfile(os.path.join(root_dir, f))]

        assert len(base_images) == 1, "There should only be one base image in {}".format(self.labbook_directory)

        with open(base_images[0]) as base_image_file:
            fields = yaml.load(base_image_file)

        return fields

    def _load_baseimage(self) -> typing.List[str]:
        """Search expected directory structure to find the base image. Only one should exist. """

        fields = self._import_baseimage_fields()
        generation_ts = str(datetime.datetime.now())
        docker_owner_ns = fields['image']['namespace']
        docker_repo = fields['image']['repo']
        docker_tag = fields['image']['tag']

        docker_lines: typing.List[str] = []
        docker_lines.append("# Dockerfile generated on {}".format(generation_ts))
        docker_lines.append("# Name: {}".format(fields["info"]["human_name"]))
        docker_lines.append("# Description: {}".format(fields["info"]["description"]))
        docker_lines.append("# Author: {} <{}>, {}".format(fields['author']['name'], fields['author']['email'],
                                                           fields['author']['organization']))
        docker_lines.append("")
        docker_lines.append("FROM {}/{}:{}".format(docker_owner_ns, docker_repo, docker_tag))

        return docker_lines

    def _load_devenv(self) -> typing.List[str]:
        """Load dev environments from yaml file in expected location. """

        root_dir = os.path.join(self.labbook_directory, '.gigantum', 'env', 'dev_env')
        dev_envs = [os.path.join(root_dir, f) for f in os.listdir(root_dir)
                    if os.path.isfile(os.path.join(root_dir, f))]

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

    def _load_packages(self) -> typing.List[str]:
        """Load packages from yaml files in expected location in directory tree. """
        """ Contents of docker setup that must be at end of Dockerfile. """
        fields = self._import_baseimage_fields()
        package_managers = {c['name']: c for c in fields['available_package_managers']}

        root_dir = os.path.join(self.labbook_directory, '.gigantum', 'env', 'package_manager')
        package_files = [os.path.join(root_dir, f) for f in os.listdir(root_dir)
                         if os.path.isfile(os.path.join(root_dir, f))]

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

    def _post_image_hook(self) -> typing.List[str]:
        """Contents that must be after baseimages but before development environments. """
        docker_lines = ["# Post-image creation hooks"]
        docker_lines.append('RUN apt-get -y install supervisor curl gosu')
        docker_lines.append('COPY entrypoint.sh /usr/local/bin/entrypoint.sh')
        docker_lines.append('RUN chmod u+x /usr/local/bin/entrypoint.sh')
        docker_lines.append('')

        return docker_lines

    def _entrypoint_hooks(self):
        """ Contents of docker setup that must be at end of Dockerfile. """
        root_dir = os.path.join(self.labbook_directory, '.gigantum', 'env', 'dev_env')
        base_images = [os.path.join(root_dir, f) for f in os.listdir(root_dir)
                       if os.path.isfile(os.path.join(root_dir, f))]

        assert len(base_images) == 1, "Currently only one development environment is supported."

        with open(base_images[0]) as base_image_file:
            fields = yaml.load(base_image_file)

        docker_lines = ['## Entrypoint hooks']
        docker_lines.append("# Run Environment")
        docker_lines.append('ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]')
        docker_lines.append('WORKDIR /mnt/labbook')

        for cmd in fields['exec_commands']:
            tokenized_args = [c.strip().replace('"', "'") for c in cmd.split(' ') if c]
            quoted_args = ['"{}"'.format(arg) for arg in tokenized_args]
            cmd_str = 'CMD [{}]'.format(", ".join(quoted_args))
            docker_lines.append(cmd_str)

        return docker_lines

    def assemble_dockerfile(self, write: bool=False) -> str:
        """Create the content of a Dockerfile per the fields in the indexed data.

        Returns:
            str - Content of Dockerfile in single string using os.linesep as line separator.
        """

        assembly_pipeline = [self._load_baseimage,
                             self._post_image_hook,
                             self._load_devenv,
                             self._load_packages,
                             self._entrypoint_hooks]

        # flat map the results of executing the pipeline.
        docker_lines = functools.reduce(lambda a, b: a + b, [f() for f in assembly_pipeline], [])

        if write:
            with open(os.path.join(self.labbook_directory, ".gigantum", "env", "Dockerfile"), "w") as dockerfile:
                dockerfile.write(os.linesep.join(docker_lines))

        return os.linesep.join(docker_lines)

if __name__ == '__main__':
    """Helper utility to run imagebuilder from the command line. """
    ib = ImageBuilder(os.getcwd())
    ib.assemble_dockerfile(write=True)
