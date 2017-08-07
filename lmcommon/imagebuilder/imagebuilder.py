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
import os

class ImageBuidler(object):
    """Class to ingest indexes describing base images, environments, and dependencies into Dockerfiles. """

    def __init__(self, indexed_data: typing.Dict) -> None:
        self.indexed_data = indexed_data
        self._validate_index()

    def _validate_index(self) -> None:
        """Throw exception if self.indexed_data does not follow anticipated schema or is missing keys. """
        pass

    def assemble_dockerfile(self) -> typing.AnyStr:
        """Create the content of a Dockerfile per the fields in the indexed data.

        Returns:
            typing.AnyStr - Content of Dockerfile.
        """

        fields = self.indexed_data["gig-dev_environment-components"]["gigantum"]["ubuntu1604-python3"]["0.1.0"]
        generation_ts =str(datetime.datetime.now())

        docker_owner_ns = fields['image']['namespace']
        docker_repo = fields['image']['repo']
        docker_tag = fields['image']['tag']

        docker_lines: typing.List[typing.AnyStr] = []
        docker_lines.append("# Dockerfile generated on {}".format(generation_ts))
        docker_lines.append("# Name: {}".format(fields["info"]["human_name"]))
        docker_lines.append("# Description: {}".format(fields["info"]["description"]))
        docker_lines.append("")
        docker_lines.append("FROM {}/{}:{}".format(docker_owner_ns, docker_repo, docker_tag))

        return os.linesep.join(docker_lines)