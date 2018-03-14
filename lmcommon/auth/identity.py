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
import requests
import shutil
import os
import pathlib
import time
from jose import jwt

from typing import (Optional, Dict, Any)

from lmcommon.configuration import Configuration
from lmcommon.logging import LMLogger
from lmcommon.auth import User
from lmcommon.dispatcher import (Dispatcher, jobs)


logger = LMLogger.get_logger()


# Dictionary of supported implementations.
SUPPORTED_IDENTITY_MANAGERS = {
    'local': ["lmcommon.auth.local", "LocalIdentityManager"],
    'browser': ["lmcommon.auth.browser", "BrowserIdentityManager"]
}


# Custom error for errors when trying to authenticate a user
class AuthenticationError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


class IdentityManager(metaclass=abc.ABCMeta):
    """Abstract class for authenticating a user and accessing user identity using Auth0 backend"""

    def __init__(self, config_obj: Configuration) -> None:
        self.config: Configuration = config_obj

        # The RSA Access key used to validate a JWT
        self.rsa_key: Optional[Dict[str, str]] = None

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

    def _check_first_login(self, username: Optional[str]) -> None:
        """Method to check if this is the first time a user has logged in. If so, import the demo labbook

        All child classes should place this method at the end of their `get_user_profile()` implementation

        Returns:
            None
        """
        demo_labbook_name = 'awful-intersections-demo.lbk'
        working_directory = Configuration().config['git']['working_directory']

        if not username:
            raise ValueError("Cannot check first login without a username set")

        if self.config.config['core']['import_demo_on_first_login']:
            user_dir = os.path.join(working_directory, username)

            # Check if the user has already logged into this instance
            if not os.path.exists(user_dir):
                # Create user dir
                pathlib.Path(os.path.join(working_directory, username, username, 'labbooks')).mkdir(parents=True,
                                                                                                    exist_ok=True)

                # Import demo labbook
                logger.info(f"Importing Demo LabBook for first-time user: {username}")

                assumed_lb_name = demo_labbook_name.replace('.lbk', '')
                jobs.import_labboook_from_zip(archive_path=os.path.join('/opt', demo_labbook_name),
                                              username=username,
                                              owner=username,
                                              base_filename=assumed_lb_name,
                                              remove_source=False)

                inferred_lb_directory = os.path.join(working_directory, username, username, 'labbooks',
                                                     assumed_lb_name)
                build_img_kwargs = {
                    'path': inferred_lb_directory,
                    'username': username,
                    'nocache': True
                }
                build_img_metadata = {
                    'method': 'build_image',
                    # TODO - we need labbook key but labbook is not available...
                    'labbook': f"{username}|{username}|{assumed_lb_name}"
                }
                dispatcher = Dispatcher()
                build_image_job_key = dispatcher.dispatch_task(jobs.build_labbook_image, kwargs=build_img_kwargs,
                                                               metadata=build_img_metadata)
                logger.info(f"Adding job {build_image_job_key} to build "
                            f"Docker image for labbook `{inferred_lb_directory}`")

                # TODO: Give build a 3 second head start for now. Use subscription in the future
                time.sleep(3)

    def _get_jwt_public_key(self, id_token: str) -> Optional[Dict[str, str]]:
        """Method to get the public key for JWT signing

        Args:
            id_token(str): The JSON Web Token recieved from the identity provider

        Returns:
            dict
        """
        url = "https://" + self.config.config['auth']['provider_domain'] + "/.well-known/jwks.json"
        response = requests.get(url)
        jwks = response.json()
        try:
            unverified_header = jwt.get_unverified_header(id_token)
        except jwt.JWTError as err:
            raise AuthenticationError(str(err), 401)

        rsa_key: dict = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }

        return rsa_key

    @staticmethod
    def _get_profile_attribute(profile_data: Dict[str, str], attribute: str,
                               required: bool = True) -> Optional[str]:
        """Method to get a profile attribute, and if required, raise exception if missing.

        Args:
            profile_data(dict): Dictionary of data returned from /userinfo query
            attribute(str): Name of the attribute to get
            required(bool): If True, will raise exception if param is missing or not set

        Returns:
            str
        """
        if attribute in profile_data.keys():
            if profile_data[attribute]:
                return profile_data[attribute]
            else:
                if required:
                    raise AuthenticationError({"code": "missing_data",
                                "description": f"The required field `{attribute}` was missing from the user profile"},
                                        401)
                else:
                    return None
        else:
            if required:
                raise AuthenticationError({"code": "missing_data",
                          "description": f"The required field `{attribute}` was missing from the user profile"}, 401)
            else:
                return None

    def validate_access_token(self, access_token: str) -> Optional[Dict[str, str]]:
        """Method to parse and validate an access token

        Args:
            access_token(str):

        Returns:
            User
        """
        # Get public RSA key
        if not self.rsa_key:
            self.rsa_key = self._get_jwt_public_key(access_token)

        if self.rsa_key:
            try:
                payload = jwt.decode(access_token, self.rsa_key,
                                     algorithms=self.config.config['auth']['signing_algorithm'],
                                     audience=self.config.config['auth']['audience'],
                                     issuer="https://" + self.config.config['auth']['provider_domain'] + "/")

                return payload

            except jwt.ExpiredSignatureError:
                raise AuthenticationError({"code": "token_expired",
                                           "description": "token is expired"}, 401)
            except jwt.JWTClaimsError:
                raise AuthenticationError({"code": "invalid_claims",
                                           "description":
                                               "incorrect claims, please check the audience and issuer"}, 401)
            except Exception:
                raise AuthenticationError({"code": "invalid_header",
                                           "description": "Unable to parse authentication token."}, 400)
        else:
            raise AuthenticationError({"code": "invalid_header", "description": "Unable to find appropriate key"}, 400)

    @abc.abstractmethod
    def is_authenticated(self, access_token: Optional[str] = None) -> bool:
        """Method to check if the user is currently authenticated in the context of this identity manager

        Returns:
            bool
        """
        raise NotImplemented

    @abc.abstractmethod
    def is_token_valid(self, access_token: Optional[str] = None) -> bool:
        """Method to check if the user's Auth0 session is still valid

        Returns:
            bool
        """
        raise NotImplemented

    @abc.abstractmethod
    def get_user_profile(self, access_token: Optional[str] = None) -> Optional[User]:
        """Method to authenticate a user

        Args:
            access_token(str):

        Returns:
            User
        """
        raise NotImplemented

    @abc.abstractmethod
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
