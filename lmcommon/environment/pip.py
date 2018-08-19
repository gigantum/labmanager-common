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
import requests
import json
from lmcommon.container.container import ContainerOperations
from lmcommon.labbook import LabBook

from natsort import natsorted

from distutils.version import StrictVersion
from distutils.version import LooseVersion

from lmcommon.environment.packagemanager import PackageManager, PackageResult


class PipPackageManager(PackageManager):
    """Class to implement the pip package manager
    """

    def search(self, search_str: str, labbook: LabBook, username: str) -> List[str]:
        """Method to search a package manager for packages based on a string. The string can be a partial string.

        Args:
            search_str: The string to search on
            labbook: Subject LabBook
            username: username of current user

        Returns:
            list(str): The list of package names that match the search string
        """
        search_result = ContainerOperations.run_command(
            f'pip search {search_str}', labbook, username,
            fallback_image=self.fallback_image(labbook))

        lines = search_result.decode().splitlines()
        return [x.split(' ')[0] for x in lines]

    def list_versions(self, package_name: str, labbook: LabBook, username: str) -> List[str]:
        """Method to list all available versions of a package based on the package name

        Args:
            package_name: Name of the package to query
            labbook: Subject LabBook
            username: username of current user

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

        # Don't include release candidates that have been pushed to pip
        versions = [x for x in versions if 'rc' not in x]

        try:
            # First attempt to sort by StrictVersion which enforces a standard version convention
            versions.sort(key=StrictVersion)
        except ValueError as e:
            if 'invalid version number' in str(e):
                try:
                    # If this failed, try LooseVersion, which is much more flexible, but can fail sometimes
                    versions.sort(key=LooseVersion)
                except Exception:
                    # Finally, try natural sorting the version strings if you still have a problem
                    versions = natsorted(versions, key=lambda x: x.replace('.', '~') + 'z')
            else:
                raise e

        versions.reverse()
        return versions

    def latest_version(self, package_name: str, labbook: LabBook, username: str) -> str:
        """Method to get the latest version string for a package

        Args:
            package_name: Name of the package to query
            labbook: Subject LabBook
            username: username of current user

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
            package_names: list of names of the packages to query
            labbook: Subject LabBook
            username: username of current user

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
        packages = ContainerOperations.run_command('pip list --format=json', labbook, username,
                                                   fallback_image=self.fallback_image(labbook))
        return json.loads(packages.decode())

    def list_available_updates(self, labbook: LabBook, username: str) -> List[Dict[str, str]]:
        """Method to get a list of all installed packages that could be updated and the new version string

        Note, this will return results for the computer/container in which it is executed. To get the properties of
        a LabBook container, a docker exec command would be needed from the Gigantum application container.

        return format is a list of dicts with the format
         {name: <package name>, version: <currently installed version string>, latest_version: <latest version string>}

        Returns:
            list
        """
        packages = ContainerOperations.run_command('pip list --format=json -o', labbook, username,
                                                   fallback_image=self.fallback_image(labbook))
        return json.loads(packages.decode())

    def validate_packages(self, package_list: List[Dict[str, str]], labbook: LabBook, username: str) \
            -> List[PackageResult]:
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
                    except ValueError:
                        # Can't set the version so just continue
                        pass
                    finally:
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
        package_strings = [f"{x['name']}=={x['version']}" for x in packages]

        if single_line:
            return [f"RUN pip install {' '.join(package_strings)}"]
        else:
            docker_strings = [f"RUN pip install {x}" for x in package_strings]
            return docker_strings
