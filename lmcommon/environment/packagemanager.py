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
import abc
from typing import (List, Dict, Optional)
from collections import namedtuple

from lmcommon.labbook import LabBook

# A namedtuple for the result of package validation
PackageValidation = namedtuple('PackageValidation', ['package', 'version'])


class PackageManager(metaclass=abc.ABCMeta):
    """Class to implement the standard interface for all available Package Managers
    """

    @abc.abstractmethod
    def search(self, search_str: str, labbook: LabBook, username: str) -> List[str]:
        """Method to search a package manager for packages based on a string. The string can be a partial string.

        Args:
            search_str(str): The string to search on

        Returns:
            list(str): The list of package names that match the search string
        """
        raise NotImplemented

    @abc.abstractmethod
    def list_versions(self, package_name: str, labbook: LabBook, username: str) -> List[str]:
        """Method to list all available versions of a package based on the package name with the latest package first

        Args:
            package_name(str): Name of the package to query

        Returns:
            list(str): Version strings
        """
        raise NotImplemented

    @abc.abstractmethod
    def latest_version(self, package_name: str, labbook: LabBook, username: str) -> str:
        """Method to get the latest version string for a package

        Args:
            package_name(str): Name of the package to query

        Returns:
            str: latest version string
        """
        raise NotImplemented

    @abc.abstractmethod
    def latest_versions(self, package_names: List[str], labbook: LabBook, username: str) -> List[str]:
        """Method to get the latest version string for a list of packages

        Args:
            package_names(list): list of names of the packages to query

        Returns:
            list: latest version strings
        """
        raise NotImplemented

    @abc.abstractmethod
    def list_installed_packages(self, labbook: LabBook, username: str) -> List[Dict[str, str]]:
        """Method to get a list of all packages that are currently installed

        Note, this will return results for the computer/container in which it is executed. To get the properties of
        a LabBook container, a docker exec command would be needed from the Gigantum application container.

        return format is a list of dicts with the format {name: <package name>, version: <version string>}

        Returns:
            list
        """
        raise NotImplemented

    @abc.abstractmethod
    def list_available_updates(self, labbook: LabBook, username: str) -> List[Dict[str, str]]:
        """Method to get a list of all installed packages that could be updated and the new version string

        Note, this will return results for the computer/container in which it is executed. To get the properties of
        a LabBook container, a docker exec command would be needed from the Gigantum application container.

        return format is a list of dicts with the format
         {name: <package name>, version: <currently installed version string>, latest_version: <latest version string>}

        Returns:
            list
        """
        raise NotImplemented

    @abc.abstractmethod
    def is_valid(self, package_name: str, labbook: LabBook, username: str, package_version: Optional[str] = None) -> PackageValidation:
        """Method to validate package names and versions

        result should be in the format {package: bool, version: bool}

        Args:
            package_name(str): The package name to validate
            package_version(str): The package version to validate

        Returns:
            namedtuple: namedtuple indicating if the package and version are valid
        """
        raise NotImplemented

    @abc.abstractmethod
    def generate_docker_install_snippet(self, packages: List[Dict[str, str]], single_line: bool = False) -> List[str]:
        """Method to generate a docker snippet to install 1 or more packages

        Args:
            packages(list(dict)): A list of package names and versions to install
            single_line(bool): If true, collapse

        Returns:
            str
        """
        raise NotImplemented
