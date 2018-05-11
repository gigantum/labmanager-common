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
import pytest

from lmcommon.environment.pip import PipPackageManager
from lmcommon.fixtures import mock_config_with_repo, build_lb_image_for_env


class TestPipPackageManager(object):
    def test_search(self, mock_config_with_repo, build_lb_image_for_env):
        """Test search command"""
        mrg = PipPackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]
        result = mrg.search("peppercorn", lb, username)
        assert len(result) == 2

        result = mrg.search("gigantum", lb, username)
        assert len(result) == 1
        assert result[0] == "gigantum"

    def test_list_versions(self, build_lb_image_for_env):
        """Test list_versions command"""
        mrg = PipPackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]
        result = mrg.list_versions("gigantum", lb, username)

        assert len(result) > 3
        assert "0.3" in result
        assert "0.4" in result
        assert "0.5" in result

    def test_latest_version(self, build_lb_image_for_env):
        """Test latest_version command"""
        mrg = PipPackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]
        result = mrg.latest_version("gigantum", lb, username)

        assert result == "0.8"

    def test_latest_versions(self, build_lb_image_for_env):
        """Test latest_version command"""
        mrg = PipPackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]
        gig_res, req_res = mrg.latest_versions(["gigantum", "requests"], lb, username)

        assert gig_res == "0.8"
        assert req_res.startswith('2.')

    def test_list_installed_packages(self, build_lb_image_for_env):
        """Test list_installed_packages command

        Note, if the contents of the container change, this test will break and need to be updated. Because of this,
        only limited asserts are made to make sure things are coming back in a reasonable format
        """
        mrg = PipPackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]
        result = mrg.list_installed_packages(lb, username)

        assert type(result) == list
        assert len(result) > 50
        assert type(result[0]) == dict
        assert type(result[0]['name']) == str
        assert type(result[0]['version']) == str

    def test_list_available_updates(self, build_lb_image_for_env):
        """Test list_available_updates command

        Note, if the contents of the container change, this test will break and need to be updated. Because of this,
        only limited asserts are made to make sure things are coming back in a reasonable format
        """
        mrg = PipPackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]
        result = mrg.list_available_updates(lb, username)

        assert type(result) == list
        assert len(result) < len(mrg.list_installed_packages(lb, username))
        assert type(result[0]) == dict
        assert type(result[0]['name']) == str
        assert type(result[0]['version']) == str
        assert type(result[0]['latest_version']) == str

    def test_generate_docker_install_snippet_single(self):
        """Test generate_docker_install_snippet command
        """
        mrg = PipPackageManager()

        packages = [{'name': 'mypackage', 'version': '3.1.4'}]

        result = mrg.generate_docker_install_snippet(packages)
        assert result == ['RUN pip install mypackage==3.1.4']

        result = mrg.generate_docker_install_snippet(packages, single_line=True)
        assert result == ['RUN pip install mypackage==3.1.4']

    def test_generate_docker_install_snippet_multiple(self):
        """Test generate_docker_install_snippet command
        """
        mrg = PipPackageManager()

        packages = [{'name': 'mypackage', 'version': '3.1.4'},
                    {'name': 'yourpackage', 'version': '2017-54.0'}]

        result = mrg.generate_docker_install_snippet(packages)
        assert result == ['RUN pip install mypackage==3.1.4', 'RUN pip install yourpackage==2017-54.0']

        result = mrg.generate_docker_install_snippet(packages, single_line=True)
        assert result == ['RUN pip install mypackage==3.1.4 yourpackage==2017-54.0']

    def test_list_versions_badpackage(self, build_lb_image_for_env):
        """Test list_versions command"""
        mrg = PipPackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]
        with pytest.raises(ValueError):
            mrg.list_versions("gigantumasdfasdfasdf", lb, username)

    def test_is_valid(self, build_lb_image_for_env):
        """Test list_versions command"""
        mrg = PipPackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]
        result = mrg.is_valid("gigantumasdfasdfasdf", lb, username)

        assert result.package is False
        assert result.version is False

        result = mrg.is_valid("gigantum", lb, username, package_version="10.0")

        assert result.package is True
        assert result.version is False

        result = mrg.is_valid("gigantum", lb, username, package_version="0.1")

        assert result.package is True
        assert result.version is True

        result = mrg.is_valid("numpy", lb, username)

        assert result.package is True
        assert result.version is False

        result = mrg.is_valid("numpy", lb, username, "1.11.2rc1")

        assert result.package is True
        assert result.version is True

        result = mrg.is_valid("numpy", lb, username, package_version="1.12.1")

        assert result.package is True
        assert result.version is True

        result = mrg.is_valid("numpy", lb, username, "10000000")

        assert result.package is True
        assert result.version is False
