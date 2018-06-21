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
from typing import (List, Dict, Optional)

from lmcommon.environment.packagemanager import PackageManager, PackageResult
from lmcommon.container.container import ContainerOperations
from lmcommon.labbook import LabBook
from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()


class AptPackageManager(PackageManager):
    """Class to implement the apt package manager

    Note: apt is somewhat limiting in the ability to access old versions of packages
    """

    def search(self, search_str: str, labbook: LabBook, username: str) -> List[str]:
        """Method to search a package manager for packages based on a string. The string can be a partial string.

        Args:
            search_str(str): The string to search on

        Returns:
            list(str): The list of package names that match the search string
        """
        result = ContainerOperations.run_command(f"apt-cache search {search_str}", labbook, username)

        packages = []
        if result:
            lines = result.decode('utf-8').split('\n')
            for l in lines:
                if l:
                    packages.append(l.split(" - ")[0])

        return packages

    def list_versions(self, package_name: str, labbook: LabBook, username: str) -> List[str]:
        """Method to list all available versions of a package based on the package name

        Args:
            package_name(str): Name of the package to query

        Returns:
            list(str): Version strings
        """
        result = ContainerOperations.run_command(f"apt-cache madison {package_name}", labbook, username)

        package_versions: List[str] = []
        if result:
            lines = result.decode('utf-8').split('\n')
            for l in lines:
                if l:
                    parts = l.split(" | ")
                    if parts[1] not in package_versions:
                        package_versions.append(parts[1].strip())
        else:
            raise ValueError(f"Package {package_name} not found in apt.")

        return package_versions

    def latest_version(self, package_name: str, labbook: LabBook, username: str) -> str:
        """Method to get the latest version string for a package

        Args:
            package_name(str): Name of the package to query

        Returns:
            str: latest version string
        """
        versions = self.list_versions(package_name, labbook, username)
        if versions:
            return versions[0]
        else:
            raise ValueError("Could not retrieve version list for provided package name")

    def latest_versions(self, package_names: List[str], labbook: LabBook, username: str) -> List[str]:
        """Method to get the latest version string for a list of packages

        Args:
            package_names(list): list of names of the packages to query

        Returns:
            list: latest version strings
        """
        return [self.latest_version(pkg, labbook, username) for pkg in package_names]

    def list_installed_packages(self, labbook: LabBook, username: str) -> List[Dict[str, str]]:
        """Method to get a list of all packages that are currently installed

        Note, this will return results for the computer/container in which it is executed. To get the properties of
        a LabBook container, a docker exec command would be needed from the Gigantum application container.

        return format is a list of dicts with the format (name: <package name>, version: <version string>)

        Returns:
            list
        """
        result = ContainerOperations.run_command("apt list --installed", labbook, username)

        packages = []
        if result:
            lines = result.decode('utf-8').split('\n')
            for line in lines:
                if line is not None and line != "Listing..." and "/" in line:
                    parts = line.split(" ")
                    package_name, _ = parts[0].split("/")
                    version = parts[1].strip()
                    packages.append({'name': package_name, 'version': version})

        return packages

    def list_available_updates(self, labbook: LabBook, username: str) -> List[Dict[str, str]]:
        """Method to get a list of all installed packages that could be updated and the new version string

        Note, this will return results for the computer/container in which it is executed. To get the properties of
        a LabBook container, a docker exec command would be needed from the Gigantum application container.

        return format is a list of dicts with the format
         {name: <package name>, version: <currently installed version string>, latest_version: <latest version string>}

        Returns:
            list
        """
        result = ContainerOperations.run_command("apt list --upgradable", labbook, username)

        packages = []
        if result:
            lines = result.decode('utf-8').split('\n')
            for line in lines:
                if line is not None and line != "Listing..." and "/" in line:
                    package_name, version_info_t = line.split("/")
                    version_info = version_info_t.split(' ')
                    packages.append({'name': package_name, 'latest_version': version_info[1],
                                     'version': version_info[5][:-1]})

        return packages

    def validate_packages(self, package_list: List[Dict[str, str]], labbook: LabBook, username: str) -> List[PackageResult]:
        """Method to validate a list of packages, and if needed fill in any missing versions

        Should check both the provided package name and version. If the version is omitted, it should be generated
        from the latest version.

        Args:
            package_list(list): A list of dictionaries of packages to validate
            labbook(str): The labbook instance
            username(str): The username for the logged in user

        Returns:
            namedtuple: namedtuple indicating if the package and version are valid
        """
        result = list()
        for package in package_list:
            pkg_result = PackageResult(package=package['package'], version=package['version'], error=True)

            try:
                version_list = self.list_versions(package['package'], labbook, username)
            except ValueError:
                result.append(pkg_result)
                continue

            if not version_list:
                # If here, no versions found for the package...so invalid
                result.append(pkg_result)
            else:
                if package['version']:
                    if package['version'] in version_list:
                        # Both package name and version are valid
                        pkg_result = pkg_result._replace(error=False)
                        result.append(pkg_result)

                    else:
                        # The package version is not in the list, so invalid
                        result.append(pkg_result)

                else:
                    # You need to look up the version and then add
                    try:
                        pkg_result = pkg_result._replace(version=self.latest_version(package['package'],
                                                                                     labbook,
                                                                                     username))
                        pkg_result = pkg_result._replace(error=False)
                        result.append(pkg_result)
                    except ValueError:
                        result.append(pkg_result)

        return result

    def generate_docker_install_snippet(self, packages: List[Dict[str, str]], single_line: bool = False) -> List[str]:
        """Method to generate a docker snippet to install 1 or more packages

        Args:
            packages(list(dict)): A list of package names and versions to install
            single_line(bool): If true, collapse

        Returns:
            list
        """
        package_strings = [f"{x['name']}" for x in packages]

        if single_line:
            return [f"RUN apt-get -y install {' '.join(package_strings)}"]
        else:
            docker_strings = [f"RUN apt-get -y install {x}" for x in package_strings]
            return docker_strings
