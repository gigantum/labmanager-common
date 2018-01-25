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

from lmcommon.environment.conda import Conda3PackageManager, Conda2PackageManager


class TestConda3PackageManager(object):

    @pytest.mark.skipif(getpass.getuser() == 'circleci', reason="Conda not available on CircleCI")
    def test_search(self):
        """Test search command"""
        mrg = Conda3PackageManager()
        result = mrg.search("requests")
        assert type(result) == list
        assert type(result[0]) == str
        assert len(result) > 6
        assert "requests" in result

    @pytest.mark.skipif(getpass.getuser() == 'circleci', reason="Conda not available on CircleCI")
    def test_list_versions(self):
        """Test list_versions command"""
        mrg = Conda3PackageManager()

        result = mrg.list_versions("requests")

        assert len(result) == 9
        assert result[8] == "2.12.4"
        assert result[0] == "2.18.4"

    @pytest.mark.skipif(getpass.getuser() == 'circleci', reason="Conda not available on CircleCI")
    def test_latest_version(self):
        """Test latest_version command"""
        mrg = Conda3PackageManager()
        result = mrg.latest_version("requests")

        assert result == "2.18.4"

    @pytest.mark.skipif(getpass.getuser() == 'circleci', reason="Conda not available on CircleCI")
    def test_list_installed_packages(self):
        """Test list_installed_packages command

        Note, if the contents of the container change, this test will break and need to be updated. Because of this,
        only limited asserts are made to make sure things are coming back in a reasonable format
        """
        mrg = Conda3PackageManager()

        result = mrg.list_installed_packages()

        assert type(result) == list
        assert len(result) == 14
        assert type(result[0]) == dict
        assert type(result[0]['name']) == str
        assert type(result[0]['version']) == str

    @pytest.mark.skip(reason="Cannot test for updates yet.")
    def test_list_available_updates(self):
        """Test list_available_updates command

        Note, if the contents of the container change, this test will break and need to be updated. Because of this,
        only limited asserts are made to make sure things are coming back in a reasonable format
        """
        mrg = Conda3PackageManager()

        result = mrg.list_available_updates()

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

    @pytest.mark.skipif(getpass.getuser() == 'circleci', reason="Conda not available on CircleCI")
    def test_list_versions_badpackage(self):
        """Test list_versions command"""
        mrg = Conda3PackageManager()

        with pytest.raises(ValueError):
            mrg.list_versions("gigantumasdfasdfasdf")

    @pytest.mark.skipif(getpass.getuser() == 'circleci', reason="Conda not available on CircleCI")
    def test_is_valid(self):
        """Test list_versions command"""
        mrg = Conda3PackageManager()

        result = mrg.is_valid("requestsasdfasdfasd")

        assert result.package is False
        assert result.version is False

        result = mrg.is_valid("requests", "10.0")

        assert result.package is True
        assert result.version is False

        result = mrg.is_valid("requests", "2.18.4")

        assert result.package is True
        assert result.version is True


class TestConda2PackageManager(object):

    @pytest.mark.skipif(getpass.getuser() == 'circleci', reason="Conda not available on CircleCI")
    def test_search(self):
        """Test search command"""
        mrg = Conda2PackageManager()
        result = mrg.search("requests")
        assert type(result) == list
        assert type(result[0]) == str
        assert len(result) > 6
        assert "requests" in result

    @pytest.mark.skipif(getpass.getuser() == 'circleci', reason="Conda not available on CircleCI")
    def test_list_versions(self):
        """Test list_versions command"""
        mrg = Conda2PackageManager()

        result = mrg.list_versions("requests")

        assert len(result) == 38
        assert "2.12.4" in result
        assert "2.18.4" in result

    @pytest.mark.skipif(getpass.getuser() == 'circleci', reason="Conda not available on CircleCI")
    def test_latest_version(self):
        """Test latest_version command"""
        mrg = Conda2PackageManager()
        result = mrg.latest_version("requests")

        assert result == "2.18.4"

    @pytest.mark.skipif(getpass.getuser() == 'circleci', reason="Conda not available on CircleCI")
    def test_list_installed_packages(self):
        """Test list_installed_packages command

        Note, if the contents of the container change, this test will break and need to be updated. Because of this,
        only limited asserts are made to make sure things are coming back in a reasonable format
        """
        mrg = Conda2PackageManager()

        result = mrg.list_installed_packages()

        assert type(result) == list
        assert len(result) == 13
        assert type(result[0]) == dict
        assert type(result[0]['name']) == str
        assert type(result[0]['version']) == str

    @pytest.mark.skip(reason="Cannot test for updates yet.")
    def test_list_available_updates(self):
        """Test list_available_updates command

        Note, if the contents of the container change, this test will break and need to be updated. Because of this,
        only limited asserts are made to make sure things are coming back in a reasonable format
        """
        mrg = Conda2PackageManager()

        result = mrg.list_available_updates()

        # TODO: Create test where something needs to be updated. right now nothing should need to updated because the
        # container is built up to date
        assert result == []

    def test_generate_docker_install_snippet_single(self):
        """Test generate_docker_install_snippet command
        """
        mrg = Conda2PackageManager()

        packages = [{'name': 'mypackage', 'version': '3.1.4'}]

        result = mrg.generate_docker_install_snippet(packages)
        assert result == ['RUN conda install mypackage=3.1.4']

        result = mrg.generate_docker_install_snippet(packages, single_line=True)
        assert result == ['RUN conda install mypackage=3.1.4']

    def test_generate_docker_install_snippet_multiple(self):
        """Test generate_docker_install_snippet command
        """
        mrg = Conda2PackageManager()

        packages = [{'name': 'mypackage', 'version': '3.1.4'},
                    {'name': 'yourpackage', 'version': '2017-54.0'}]

        result = mrg.generate_docker_install_snippet(packages)
        assert result == ['RUN conda install mypackage=3.1.4', 'RUN conda install yourpackage=2017-54.0']

        result = mrg.generate_docker_install_snippet(packages, single_line=True)
        assert result == ['RUN conda install mypackage=3.1.4 yourpackage=2017-54.0']

    @pytest.mark.skipif(getpass.getuser() == 'circleci', reason="Conda not available on CircleCI")
    def test_list_versions_badpackage(self):
        """Test list_versions command"""
        mrg = Conda2PackageManager()

        with pytest.raises(ValueError):
            mrg.list_versions("gigantumasdfasdfasdf")

    @pytest.mark.skipif(getpass.getuser() == 'circleci', reason="Conda not available on CircleCI")
    def test_is_valid(self):
        """Test list_versions command"""
        mrg = Conda2PackageManager()

        result = mrg.is_valid("requestsasdfasdfasd")

        assert result.package is False
        assert result.version is False

        result = mrg.is_valid("requests", "10.0")

        assert result.package is True
        assert result.version is False

        result = mrg.is_valid("requests", "2.18.4")

        assert result.package is True
        assert result.version is True
