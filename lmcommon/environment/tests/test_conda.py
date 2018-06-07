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
import getpass
import pprint

from lmcommon.fixtures.container import mock_config_with_repo, build_lb_image_for_env
from lmcommon.environment.conda import Conda3PackageManager, Conda2PackageManager


class TestConda3PackageManager(object):

    def test_search(self, build_lb_image_for_env):
        """Test search command"""
        mrg = Conda3PackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]
        result = mrg.search("reque*", lb, username)
        assert type(result) == list
        assert type(result[0]) == str
        assert len(result) > 6
        assert "requests" in result
        result = mrg.search("nump*", lb, username)
        assert type(result) == list
        assert type(result[0]) == str
        assert len(result) > 2
        assert "numpy" in result

    def test_search_no_wildcard(self, build_lb_image_for_env):
        """Test search command"""
        mrg = Conda3PackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]
        result = mrg.search("reque", lb, username)
        assert type(result) == list
        assert type(result[0]) == str
        assert len(result) > 6
        assert "requests" in result

    def test_search_empty(self, build_lb_image_for_env):
        """Test search command with no result"""
        mrg = Conda3PackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]
        result = mrg.search("asdffdghdfghdraertasdfsadfa", lb, username)
        assert type(result) == list
        assert len(result) == 0

    def test_list_versions(self, build_lb_image_for_env):
        """Test list_versions command"""
        mrg = Conda3PackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]
        result = mrg.list_versions("requests", lb, username)
        assert len(result) == 9
        assert result[8] == "2.12.4"
        assert result[0] == "2.18.4"

        result = mrg.list_versions("numpy", lb, username)
        assert len(result) > 5
        assert result[0] == "1.14.2"
        assert result[1] == "1.14.1"

    def test_latest_version(self, build_lb_image_for_env):
        """Test latest_version command"""
        mrg = Conda3PackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]

        # Note, "requests" is an installed package
        result = mrg.latest_version("requests", lb, username)
        assert result == "2.18.4"

        # numpy is a non-installed package
        result = mrg.latest_version("numpy", lb, username)
        assert result == '1.14.4'

    def test_latest_versions(self, build_lb_image_for_env):
        """Test latest_version command"""
        mrg = Conda3PackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]
        pkgs = ["numpy", "requests"]
        result = mrg.latest_versions(pkgs, lb, username)

        assert result[0] == '1.14.4'  # Numpy
        assert result[1] == '2.18.4'  # Requests

    def test_latest_versions_bad_pkg(self, build_lb_image_for_env):
        """Test latest_version command"""
        mrg = Conda3PackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]
        with pytest.raises(ValueError):
            mrg.latest_versions(["asdasdfdasdff", "numpy"], lb, username)

    def test_list_installed_packages(self, build_lb_image_for_env):
        """Test list_installed_packages command

        Note, if the contents of the container change, this test will break and need to be updated. Because of this,
        only limited asserts are made to make sure things are coming back in a reasonable format
        """
        mrg = Conda3PackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]
        result = mrg.list_installed_packages(lb, username)

        assert type(result) == list
        assert len(result) >= 14
        assert type(result[0]) == dict
        assert type(result[0]['name']) == str
        assert type(result[0]['version']) == str

    @pytest.mark.skip(reason="Cannot test for updates yet.")
    def test_list_available_updates(self, build_lb_image_for_env):
        """Test list_available_updates command

        Note, if the contents of the container change, this test will break and need to be updated. Because of this,
        only limited asserts are made to make sure things are coming back in a reasonable format
        """
        mrg = Conda3PackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]
        result = mrg.list_available_updates(lb, username)

        # TODO: Create test where something needs to be updated. right now nothing should need to updated because the
        # container is built up to date
        assert result == []

    def test_generate_docker_install_snippet_single(self):
        """Test generate_docker_install_snippet command
        """
        mrg = Conda3PackageManager()
        packages = [{'name': 'mypackage', 'version': '3.1.4'}]

        result = mrg.generate_docker_install_snippet(packages)
        assert result == ['RUN conda install mypackage=3.1.4']

        result = mrg.generate_docker_install_snippet(packages, single_line=True)
        assert result == ['RUN conda install mypackage=3.1.4']

    def test_generate_docker_install_snippet_multiple(self):
        """Test generate_docker_install_snippet command
        """
        mrg = Conda3PackageManager()
        packages = [{'name': 'mypackage', 'version': '3.1.4'},
                    {'name': 'yourpackage', 'version': '2017-54.0'}]

        result = mrg.generate_docker_install_snippet(packages)
        assert result == ['RUN conda install mypackage=3.1.4', 'RUN conda install yourpackage=2017-54.0']

        result = mrg.generate_docker_install_snippet(packages, single_line=True)
        assert result == ['RUN conda install mypackage=3.1.4 yourpackage=2017-54.0']

    def test_list_versions_badpackage(self, build_lb_image_for_env):
        """Test list_versions command"""
        mrg = Conda3PackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]
        with pytest.raises(ValueError):
            mrg.list_versions("gigantumasdfasdfasdf", lb, username)

    def test_is_valid(self, build_lb_image_for_env):
        """Test list_versions command"""
        mrg = Conda3PackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]

        result = mrg.is_valid("requests", lb, username, "10.0")
        assert result.package is True
        assert result.version is False

        result = mrg.is_valid("requests", lb, username, "2.18.4")
        assert result.package is True
        assert result.version is True

        result = mrg.is_valid("requestsasdfasdfasd", lb, username)
        assert result.package is False
        assert result.version is False


class TestConda2PackageManager(object):
    def test_latest_versions(self, build_lb_image_for_env):
        """Test latest_version command"""
        mrg = Conda2PackageManager()
        lb = build_lb_image_for_env[0]
        username = build_lb_image_for_env[1]
        pkgs = ["numpy", "requests"]
        result = mrg.latest_versions(pkgs, lb, username)

        assert result[0] == '1.14.4' #Numpy
        assert result[1] == '2.18.4' # Requests