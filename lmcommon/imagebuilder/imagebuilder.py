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
import typing
import yaml
import os

class ImageBuidler(object):
    """Class to ingest indexes describing base images, environments, and dependencies into Dockerfiles. """

    def __init__(self, labbook_directory: typing.AnyStr) -> None:
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

    def _load_baseimage(self) -> typing.List[typing.AnyStr]:
        base_images = [f for f in os.listdir(self.labbook_directory, '.gigantum', 'env', 'base_image')
                       if os.path.isfile(f)]

        assert len(base_images) == 1

        with open(base_images[0]) as base_image_file:
            fields = yaml.load(base_image_file)

        generation_ts =str(datetime.datetime.now())
        docker_owner_ns = fields['image']['namespace']
        docker_repo = fields['image']['repo']
        docker_tag = fields['image']['tag']

        docker_lines: typing.List[typing.AnyStr] = []
        docker_lines.append("# Dockerfile generated on {}".format(generation_ts))
        docker_lines.append("# Name: {}".format(fields["info"]["human_name"]))
        docker_lines.append("# Description: {}".format(fields["info"]["description"]))
        docker_lines.append("# Author: {} <{}>, {}".format(fields['author']['name'], fields['author']['email'],
                                                           fields['author']['organization']))
        docker_lines.append("")
        docker_lines.append("FROM {}/{}:{}".format(docker_owner_ns, docker_repo, docker_tag))


    def _load_devenv(self) -> typing.List[typing.AnyStr]:
        pass

    def _load_packages(self) -> typing.List[typing.AnyStr]:
        pass

    def assemble_dockerfile(self) -> typing.AnyStr:
        """Create the content of a Dockerfile per the fields in the indexed data.

        Returns:
            typing.AnyStr - Content of Dockerfile.
        """

        baseimage_lines = self._load_baseimage()
        devenv_lines = []
        package_lines = []
        docker_lines = baseimage_lines + devenv_lines + package_lines
        return os.linesep.join(docker_lines)