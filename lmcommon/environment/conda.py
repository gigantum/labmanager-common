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
from collections import OrderedDict


from io import StringIO
import requests
import json
from natsort import natsorted

from distutils.version import StrictVersion
from distutils.version import LooseVersion

from contextlib import redirect_stdout
from lmcommon.environment.packagemanager import PackageManager, PackageValidation
from lmcommon.container import ContainerOperations
from lmcommon.container.exceptions import ContainerException
from lmcommon.labbook import LabBook
from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()


class CondaPackageManagerBase(PackageManager):
    """Class to implement the conda package manager
    """
    def __init__(self):
        # String to be set in child classes indicating which python version you are checking. Typically should be either
        # python 3.6* or python 2.7*
        self.python_depends_str = None

        # String of the name of the conda environment (e.g. py36 or py27, as created via container build)
        self.python_env = None

    def search(self, search_str: str, labbook: LabBook, username: str) -> List[str]:
        """Method to search a package manager for packages based on a string. The string can be a partial string.

        Args:
            search_str(str): The string to search on

        Returns:
            list(str): The list of package names that match the search string
        """
        # Add wildcard for search
        if search_str[-1] != '*':
            search_str = search_str + '*'

        try:
            result = ContainerOperations.run_command(f'conda search  --json "{search_str}"',
                                                     labbook=labbook, username=username)
        except ContainerException as e:
            logger.error(e)
            return list()

        data = json.loads(result.decode())
        if 'exception_name' in data:
            if data.get('exception_name') in ['PackagesNotFoundError', 'PackageNotFoundError']:
                # This means you entered an invalid package name that didn't resolve to anything
                return list()
            else:
                raise Exception(f"An error occurred while searching for packages: {data.get('exception_name')}")

        if data:
            return list(data.keys())
        else:
            return list()

    def list_versions(self, package_name: str, labbook: LabBook, username: str) -> List[str]:
        """Method to list all available versions of a package based on the package name

        Args:
            package_name(str): Name of the package to query

        Returns:
            list(str): Version strings
        """
        try:
            result = ContainerOperations.run_command(f"conda info --json {package_name}", labbook, username)
            data = json.loads(result.decode())
        except ContainerException as e:
            logger.error(e)
            data = {}

        # TODO: Conda does not seem to throw this anymore. Remove once confirmed
        if 'exception_name' in data:
            raise ValueError(f"An error occurred while getting package versions: {data.get('exception_name')}")

        if len(data.keys()) == 0 or len(data.get(package_name)) == 0:
            raise ValueError(f"Package {package_name} not found")

        # Check to see if this is a python package. If so, filter based on the current version of python (set in child)
        if any([True for x in data.get(package_name) if self.python_depends_str in x.get('depends')]):
            versions = [x.get('version') for x in data.get(package_name) if self.python_depends_str in x.get('depends')]
        else:
            versions = [x.get('version') for x in data.get(package_name)]

        versions = list(OrderedDict.fromkeys(versions))

        try:
            versions.sort(key=StrictVersion)
        except ValueError as e:
            if 'invalid version number' in str(e):
                try:
                    versions.sort(key=LooseVersion)
                except:
                    versions = natsorted(versions, key=lambda x: x.replace('.', '~') + 'z')
            else:
                raise e

        versions.reverse()

        return versions

    def latest_version(self, package_name: str, labbook: LabBook, username: str) -> str:
        """Method to get the latest version string for a package

        Args:
            package_name(str): Name of the package to query

        Returns:
            str: latest version string
        """
        result = ContainerOperations.run_command(f"conda install --dry-run --no-deps --json {package_name}",
                                                 labbook, username)
        data = json.loads(result.decode().strip())

        if data.get('message') == 'All requested packages already installed.':
            # We enter this block if the given package_name is already installed to the latest version.
            # Then we have to retrieve the latest version using conda list
            result = ContainerOperations.run_command("conda list --json", labbook, username)
            data = json.loads(result.decode().strip())
            for pkg in data:
                if pkg.get('name') == package_name:
                    return pkg.get('version')
        else:
            if isinstance(data.get('actions'), dict) is True:
                # New method - added when bases updated to conda 4.5.1
                for p in data.get('actions').get('LINK'):
                    if p.get('name') == package_name:
                        return p.get("version")
            else:
                # legacy methods to handle older bases built on conda 4.3.31
                try:
                    for p in [x.get('LINK')[0] for x in data.get('actions') if x]:
                        if p.get('name') == package_name:
                            return p.get("version")
                except:
                    for p in [x.get('LINK') for x in data.get('actions') if x]:

                        if p.get('name') == package_name:
                            return p.get("version")

        # if you get here, failed to find the package in the result from conda
        raise ValueError(f"Could not retrieve version list for provided package name: {package_name}")

    def latest_versions(self, package_names: List[str], labbook: LabBook, username: str) -> List[str]:
        """Method to get the latest version string for a list of packages

        Args:
            package_names(list): list of names of the packages to query

        Returns:
            list: latest version strings
        """
        cmd = ['conda', 'install', '--dry-run', '--no-deps', '--json', *package_names]

        try:
            result = ContainerOperations.run_command(' '.join(cmd), labbook, username).decode().strip()
        except Exception as e:
            logger.error(e)
            pkgs = ", ".join(package_names)
            raise ValueError(f"Could not retrieve latest versions due to invalid package name in list: {pkgs}")

        output_versions: List[str] = list()
        if result:
            data = json.loads(result)
            versions = {pn: "" for pn in package_names}
            for package_name in package_names:
                for p in [x for x in data.get('actions')[0]['LINK'] if x]:
                    if p.get('name') == package_name:
                        versions[package_name] = p.get("version")

        # Now, for any packages whose versions could not be found (because they are installed)...
        # ... just look them up manually. This will add some time, but there's no way around it.
        missing_keys = [k for k in versions.keys() if versions[k] == ""]
        for pn in missing_keys:
            versions[pn] = self.latest_version(pn, labbook, username)
        output_versions = [versions[p] for p in package_names]
        return output_versions

    def list_installed_packages(self, labbook: LabBook, username: str) -> List[Dict[str, str]]:
        """Method to get a list of all packages that are currently installed

        Note, this will return results for the computer/container in which it is executed. To get the properties of
        a LabBook container, a docker exec command would be needed from the Gigantum application container.

        return format is a list of dicts with the format (name: <package name>, version: <version string>)

        Returns:
            list
        """
        result = ContainerOperations.run_command(f"conda list --no-pip --json", labbook, username)
        data = json.loads(result.decode().strip())
        if data:
            return [{"name": x['name'], 'version': x['version']} for x in data]
        else:
            return []

    def list_available_updates(self, labbook: LabBook, username: str) -> List[Dict[str, str]]:
        """Method to get a list of all installed packages that could be updated and the new version string

        Note, this will return results for the computer/container in which it is executed. To get the properties of
        a LabBook container, a docker exec command would be needed from the Gigantum application container.

        return format is a list of dicts with the format
         {name: <package name>, version: <currently installed version string>, latest_version: <latest version string>}

        Returns:
            list
        """
        # This may never need to be used and is not currently used by the API.
        return []
        # res = ContainerOperations.run_command("conda search --json --outdated", labbook, username)
        # data = json.loads(res.decode().strip())
        # packages = [x for x in data if data.get(x)]
        # return packages

    def is_valid(self, package_name: str, labbook: LabBook, username: str, package_version: Optional[str] = None) -> PackageValidation:
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
            version_list = self.list_versions(package_name, labbook, username)
        except (ValueError, ContainerException):
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
        package_strings = [f"{x['name']}={x['version']}" for x in packages]

        if single_line:
            return [f"RUN conda install {' '.join(package_strings)}"]
        else:
            docker_strings = [f"RUN conda install {x}" for x in package_strings]
            return docker_strings


class Conda3PackageManager(CondaPackageManagerBase):
    """Class to implement the conda3 package manager
    """

    def __init__(self):
        super().__init__()
        self.python_depends_str = 'python 3.6*'
        self.python_env = 'py36'


class Conda2PackageManager(CondaPackageManagerBase):
    """Class to implement the conda2 package manager
    """

    def __init__(self):
        super().__init__()
        self.python_depends_str = 'python 2.7*'
        self.python_env = 'py27'
