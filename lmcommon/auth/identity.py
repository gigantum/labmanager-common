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
import importlib

from typing import (Optional)

from lmcommon.configuration import Configuration
from lmcommon.logging import LMLogger
from lmcommon.auth import User

logger = LMLogger.get_logger()


# Dictionary of supported implementations.
SUPPORTED_IDENTITY_MANAGERS = {'local': ["lmcommon.auth.local", "LocalIdentityManager"]}


# Custom error for errors when trying to authenticate a user
class AuthenticationError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


class IdentityManager(metaclass=abc.ABCMeta):
    """Abstract class for authenticating a user and accessing user identity"""

    def __init__(self, config_obj: Configuration) -> None:
        self.config: Configuration = config_obj

        # The User instance containing user details
        self._user: Optional[User] = None

    @property
    def user(self) -> Optional[User]:
        if self._user:
            return self._user
        else:
            return None

    @user.setter
    def user(self, value: User) -> None:
        self._user = value

    def authenticate(self, jwt: Optional[str] = None) -> Optional[User]:
        """Method to authenticate a user

        Args:
            jwt(str):

        Returns:
            User
        """
        raise NotImplemented

    def logout(self) -> None:
        """Method to logout a user if applicable

        Returns:
            None
        """
        raise NotImplemented


def get_identity_manager(config_obj: Configuration) -> IdentityManager:
        """Factory method that instantiates a GitInterface implementation based on provided configuration information

        Note: ['auth']['identity_manager'] is a required configuration parameter used to choose implementation

            Supported Implementations:
                - "local" - Provides ability to work both online and offline

        Args:
            config_obj(Configuration): Loaded configuration object

        Returns:
            IdentityManager
        """
        if "auth" not in config_obj.config.keys():
            raise ValueError("You must specify the `auth` parameter to instantiate an IdentityManager implementation")

        if 'identity_manager' not in config_obj.config["auth"]:
            raise ValueError("You must specify the desired identity manager class in the config file.")

        if config_obj.config["auth"]["identity_manager"] not in SUPPORTED_IDENTITY_MANAGERS:
            msg = f"Unsupported `identity_manager` parameter `{config_obj.config['auth']['identity_manager']}`"
            msg = f"{msg}.  Valid identity managers: {', '.join(SUPPORTED_IDENTITY_MANAGERS.keys())}"
            raise ValueError(msg)

        # If you are here OK to import class
        key = config_obj.config["auth"]["identity_manager"]
        identity_mngr_class = getattr(importlib.import_module(SUPPORTED_IDENTITY_MANAGERS[key][0]),
                                      SUPPORTED_IDENTITY_MANAGERS[key][1])

        # Instantiate with the config dict and return to the user
        logger.info(f"Created Identity Manager of type: {key}")
        return identity_mngr_class(config_obj)
