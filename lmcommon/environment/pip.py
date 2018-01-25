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
from typing import (Any, List, Dict, Optional)
import pip
from io import StringIO
import requests
import json

from distutils.version import StrictVersion
from distutils.version import LooseVersion

from contextlib import redirect_stdout
from lmcommon.environment.packagemanager import PackageManager, PackageValidation


class PipPackageManager(PackageManager):
    """Class to implement the pip package manager
    """

    def search(self, search_str: str) -> List[str]:
        """Method to search a package manager for packages based on a string. The string can be a partial string.

        Args:
            search_str(str): The string to search on

        Returns:
            list(str): The list of package names that match the search string
        """
        buffer = StringIO()
        with redirect_stdout(buffer):
            pip.main(['search', search_str])

        lines = buffer.getvalue().splitlines()
        return [x.split(' ')[0] for x in lines]

    def list_versions(self, package_name: str) -> List[str]:
        """Method to list all available versions of a package based on the package name

        Args:
            package_name(str): Name of the package to query

        Returns:
            list(str): Version strings
        """
        url = f"https://pypi.python.org/pypi/{package_name}/json"
        result = requests.get(url)
        if result.status_code == 404:
            # Didn't find the package
            raise ValueError("Package not found in package index")
        if result.status_code != 200:
            raise IOError("Failed to query package index for package versions. Check internet connection.")

        versions = list(result.json()["releases"].keys())
        try:
            versions.sort(key=StrictVersion)
        except ValueError as e:
            if 'invalid version number' in str(e):
                versions.sort(key=LooseVersion)
            else:
                raise e

        versions.reverse()
        return versions

    def latest_version(self, package_name: str) -> str:
        """Method to get the latest version string for a package

        Args:
            package_name(str): Name of the package to query

        Returns:
            str: latest version string
        """
        versions = self.list_versions(package_name)
        if versions:
            return versions[0]
        else:
            raise ValueError("Could not retrieve version list for provided package name")

    def list_installed_packages(self) -> List[Dict[str, str]]:
        """Method to get a list of all packages that are currently installed

        Note, this will return results for the computer/container in which it is executed. To get the properties of
        a LabBook container, a docker exec command would be needed from the Gigantum application container.

        return format is a list of dicts with the format (name: <package name>, version: <version string>)

        Returns:
            list
        """
        buffer = StringIO()
        with redirect_stdout(buffer):
            pip.main(['list', '--format=json'])

        return json.loads(buffer.getvalue())

    def list_available_updates(self) -> List[Dict[str, str]]:
        """Method to get a list of all installed packages that could be updated and the new version string

        Note, this will return results for the computer/container in which it is executed. To get the properties of
        a LabBook container, a docker exec command would be needed from the Gigantum application container.

        return format is a list of dicts with the format
         {name: <package name>, version: <currently installed version string>, latest_version: <latest version string>}

        Returns:
            list
        """
        buffer = StringIO()
        with redirect_stdout(buffer):
            pip.main(['list', '--format=json', '-o'])

        return json.loads(buffer.getvalue())

    def is_valid(self, package_name: str, package_version: Optional[str] = None) -> PackageValidation:
        """Method to validate package names and versions

        result should be in the format {package: bool, version: bool}

        Args:
            package_name(str): The package name to validate
            package_version(str): The package version to validate

        Returns:
            namedtuple: namedtuple indicating if the package and version are valid
        """
        invalid_result = PackageValidation(package=False, version=False)

        try:
            version_list = self.list_versions(package_name)
        except ValueError:
            return invalid_result

        if not version_list:
            # If here, no versions found for the package...so invalid
            return invalid_result
        else:
            if package_version:
                if package_version in version_list:
                    # Both package name and version are valid
                    return PackageValidation(package=True, version=True)

            # Since versions were returned, package name is valid, but version was either omitted or not valid
            return PackageValidation(package=True, version=False)

    def generate_docker_install_snippet(self, packages: List[Dict[str, str]], single_line: bool = False) -> List[str]:
        """Method to generate a docker snippet to install 1 or more packages

        Args:
            packages(list(dict)): A list of package names and versions to install
            single_line(bool): If true, collapse

        Returns:
            list
        """
        package_strings = [f"{x['name']}=={x['version']}" for x in packages]

        if single_line:
            return [f"RUN pip install {' '.join(package_strings)}"]
        else:
            docker_strings = [f"RUN pip install {x}" for x in package_strings]
            return docker_strings
