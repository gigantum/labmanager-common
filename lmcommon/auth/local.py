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
import jose

from typing import Optional

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
            return self._load_user(None)

    @user.setter
    def user(self, value: User) -> None:
        self._user = value

    def is_authenticated(self, access_token: Optional[str] = None, id_token: Optional[str] = None) -> bool:
        """Method to check if the user is currently authenticated in the context of this identity manager

        Returns:
            bool
        """
        user = self._load_user(id_token)
        if user:
            return True
        else:
            is_valid = self.is_token_valid(access_token)
            if is_valid:
                # Load the user profile now so the user doesn't have to log in again later
                self.get_user_profile(access_token, id_token)

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
                _ = self.validate_jwt_token(access_token, self.config.config['auth']['audience'])
            except AuthenticationError:
                return False

            return True

    def get_user_profile(self, access_token: Optional[str] = None, id_token: Optional[str] = None) -> Optional[User]:
        """Method to get the current logged in user profile info

        Args:
            access_token(str): API JSON web token from Auth0
            id_token(str): ID JSON web token from Auth0

        Returns:
            User
        """
        # Check if user is already loaded or stored locally
        user = self._load_user(id_token)
        if user:
            return user
        else:
            if not id_token:
                err_dict = {"code": "missing_token",
                            "description": "JWT must be provided if no locally stored identity is available"}
                raise AuthenticationError(err_dict, 401)

            # Validate JWT token
            token_payload = self.validate_jwt_token(id_token, self.config.config['auth']['client_id'],
                                                    access_token=access_token)

            # Create user identity instance
            self.user = User()
            self.user.email = self._get_profile_attribute(token_payload, "email", required=True)
            self.user.username = self._get_profile_attribute(token_payload, "nickname", required=True)
            self.user.given_name = self._get_profile_attribute(token_payload, "given_name", required=False)
            self.user.family_name = self._get_profile_attribute(token_payload, "family_name", required=False)

            # Save User to local storage
            self._save_user(id_token)

            # Check if it's the first time this user has logged into this instance
            self._check_first_login(self.user.username, access_token)

            return self.user

    def logout(self) -> None:
        """Method to logout a user if applicable

        Returns:
            None
        """
        data_file = os.path.join(self.auth_dir, 'cached_id_jwt')
        if os.path.exists(data_file):
            os.remove(data_file)
        data_file = os.path.join(self.auth_dir, 'jwks.json')
        if os.path.exists(data_file):
            os.remove(data_file)

        self.user = None
        self.rsa_key = None
        logger.info("Removed user identity from local storage.")

    def _save_user(self, id_token: str) -> None:
        """Method to save the current logged in user's ID token to disk

        Returns:
            None
        """
        # Create directory to store user info if it doesn't exist
        if not os.path.exists(self.auth_dir):
            os.makedirs(self.auth_dir)

        # If user data exists, remove it first
        data_file = os.path.join(self.auth_dir, 'cached_id_jwt')
        if os.path.exists(data_file):
            os.remove(data_file)
            logger.warning(f"User identity data already exists. Overwriting")

        with open(data_file, 'wt') as user_file:
            json.dump(id_token, user_file)

    def _load_user(self, id_token: Optional[str]) -> Optional[User]:
        """Method to load a users's ID token to disk

        Returns:
            None
        """
        data_file = os.path.join(self.auth_dir, 'cached_id_jwt')
        if os.path.exists(data_file):
            with open(data_file, 'rt') as user_file:
                data = json.load(user_file)

                if id_token is not None and id_token != data:
                    old_user = jose.jwt.get_unverified_claims(data)['nickname']
                    new_user = jose.jwt.get_unverified_claims(id_token)['nickname']
                    print(old_user)
                    print(new_user)
                    if old_user == new_user:
                        logger.info("ID Token has been updated.")
                        self._save_user(id_token)

                        data = id_token
                    else:
                        logger.warning("ID Token user does not match locally cached identity!")
                        data_file = os.path.join(self.auth_dir, 'cached_id_jwt')
                        os.remove(data_file)
                        return None

                # Load data from JWT with limited checks due to possible timeout and lack of access token
                token_payload = self.validate_jwt_token(data, self.config.config['auth']['client_id'],
                                                        limited_validation=True)

                # Create user identity instance
                user_obj = User()
                user_obj.email = self._get_profile_attribute(token_payload, "email", required=True)
                user_obj.username = self._get_profile_attribute(token_payload, "nickname", required=True)
                user_obj.given_name = self._get_profile_attribute(token_payload, "given_name", required=False)
                user_obj.family_name = self._get_profile_attribute(token_payload, "family_name", required=False)

                return user_obj
        else:
            return None
