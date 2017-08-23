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

import subprocess
import os

import docker

from .configuration import Configuration


def _get_docker_server_api_version() -> str:
    """Retrieve the Docker server API version. """

    # Returns the lines of output, even if command is invalid
    output_lines = subprocess.getoutput("docker version").split(os.linesep)

    # We must infer if docker server is installed since subprocess is not returning a status code
    if not any(['API version' in l for l in output_lines]):
        raise ValueError('Unable to obtain docker version (is docker installed?)')

    # We need to get the API version of the docker SERVER, not necessarily client.
    server_flag_found = False
    server_info_lines = list()

    for line in output_lines:
        if 'Server:' in line:
            server_flag_found = True

        if server_flag_found:
            server_info_lines.append(line)

    if not server_info_lines:
        raise ValueError('Unable to find docker server API version')

    for line in server_info_lines:
        if 'API version' in line:
            # Note, version string in format of:
            # "API version:  1.30 (minimum version 1.12)"
            return line.strip().split(':')[1].strip().split(' ')[0]
    else:
        # Impossible to get here (cause we've checked that 'API version' exists in line)
        # but just put this clause in here for closure.
        assert False, "Docker API version should have been found"


def get_docker_client(check_server_version=True):
    """Return a docker client with proper version to match server API. """
    if check_server_version:
        docker_server_api_version = _get_docker_server_api_version()
        return docker.from_env(version=docker_server_api_version)
    else:
        return docker.from_env()