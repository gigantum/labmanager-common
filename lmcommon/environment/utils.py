from lmcommon.environment.packagemanager import PackageManager
from lmcommon.environment.pip import PipPackageManager
from lmcommon.environment.conda import Conda2PackageManager, Conda3PackageManager
from lmcommon.environment.apt import AptPackageManager


def get_package_manager(manager: str) -> PackageManager:
    """Helper class to instantiate a package manager based on manager string"""
    if manager in ["pip2", "pip3", "pip"]:
        return PipPackageManager()
    elif manager == "conda2":
        return Conda2PackageManager()
    elif manager == "conda3":
        return Conda3PackageManager()
    elif manager in ["apt", "apt-get"]:
        return AptPackageManager()
    else:
        raise ValueError(f"Unsupported package manager `{manager}`")
