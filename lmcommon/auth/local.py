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
from lmcommon.auth.identity import IdentityManager, User, AuthenticationError
from lmcommon.configuration import Configuration
import os
import json
import requests

from typing import Optional, Dict

from lmcommon.logging import LMLogger
logger = LMLogger.get_logger()


class LocalIdentityManager(IdentityManager):
    """Class for authenticating a user and accessing user identity while supporting local, offline operation"""

    def __init__(self, config_obj: Configuration) -> None:
        """Constructor"""
        # Call super constructor
        IdentityManager.__init__(self, config_obj=config_obj)

        self.auth_dir = os.path.join(self.config.config['git']['working_directory'], '.labmanager', 'identity')

    # Override the user property to automatically try to load the user from disk
    @property
    def user(self) -> Optional[User]:
        if self._user:
            return self._user
        else:
            return self._load_user()

    @user.setter
    def user(self, value: User) -> None:
        self._user = value

    def is_authenticated(self, access_token: Optional[str] = None) -> bool:
        """Method to check if the user is currently authenticated in the context of this identity manager

        Returns:
            bool
        """
        user = self._load_user()
        if user:
            return True
        else:
            is_valid = self.is_token_valid(access_token)
            if is_valid:
                # Load the user profile now so the user doesn't have to log in again later
                self.get_user_profile(access_token)

            return is_valid

    def is_token_valid(self, access_token: Optional[str] = None) -> bool:
        """Method to check if the user's Auth0 session is still valid

        Returns:
            bool
        """
        if not access_token:
            return False
        else:
            try:
                _ = self.validate_access_token(access_token)
            except AuthenticationError:
                return False

            return True

    def get_user_profile(self, access_token: Optional[str] = None) -> Optional[User]:
        """Method to authenticate a user by verifying the jwt signature OR loading from backend storage

        Args:
            access_token(str): JSON web token from Auth0

        Returns:
            User
        """
        # Check if user is already loaded or stored locally
        user = self._load_user()
        if user:
            return user
        else:
            if not access_token:
                err_dict = {"code": "missing_token",
                            "description": "JWT must be provided to authenticate user if no local "
                                           "stored identity is available"}
                raise AuthenticationError(err_dict, 401)

            # Validate JWT token
            _ = self.validate_access_token(access_token)

            # Go get the user profile data
            url = "https://" + self.config.config['auth']['provider_domain'] + "/userinfo"
            response = requests.get(url, headers={'Authorization': f'Bearer {access_token}'})
            if response.status_code != 200:
                AuthenticationError({"code": "profile_unauthorized",
                                     "description": "Failed to get user profile data"}, 401)
            user_profile = response.json()

            # Create user identity
            self.user = User()
            self.user.email = self._get_profile_attribute(user_profile, "email", required=True)
            self.user.username = self._get_profile_attribute(user_profile, "nickname", required=True)
            self.user.given_name = self._get_profile_attribute(user_profile, "given_name", required=False)
            self.user.family_name = self._get_profile_attribute(user_profile, "family_name", required=False)

            # Save User to local storage
            self._save_user()

            return self.user

    def logout(self) -> None:
        """Method to logout a user if applicable

        Returns:
            None
        """
        data_file = os.path.join(self.auth_dir, 'user.json')
        if os.path.exists(data_file):
            os.remove(data_file)

        self.user = None
        self.rsa_key = None
        logger.info("Removed user identity from local storage.")

    def _save_user(self) -> None:
        """Method to save a User props to disk

        Returns:
            None
        """
        if self.user:
            data = {'username': self.user.username,
                    'email': self.user.email,
                    'given_name': self.user.given_name,
                    'family_name': self.user.family_name,
                    }
        else:
            raise ValueError("No User Identity is loaded. Cannot save identity.")

        # Create directory to store user info if it doesn't exist
        if not os.path.exists(self.auth_dir):
            os.makedirs(self.auth_dir)

        # If user data exists, remove it first
        data_file = os.path.join(self.auth_dir, 'user.json')
        if os.path.exists(data_file):
            os.remove(data_file)
            logger.warning(f"User identity data already exists. Overwriting with {data['username']}")

        with open(data_file, 'wt') as user_file:
            json.dump(data, user_file)

    def _load_user(self) -> Optional[User]:
        """Method to load a User from disk if it exists

        Returns:
            None
        """
        data_file = os.path.join(self.auth_dir, 'user.json')
        if os.path.exists(data_file):
            with open(data_file, 'rt') as user_file:
                data = json.load(user_file)

                user_obj = User()
                user_obj.username = data.get('username')
                user_obj.email = data.get('email')
                user_obj.given_name = data.get('given_name')
                user_obj.family_name = data.get('family_name')

                return user_obj
        else:
            return None
