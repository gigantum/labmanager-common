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
import os
import requests

from typing import Optional
from lmcommon.logging import LMLogger

from lmcommon.auth.identity import IdentityManager, User, AuthenticationError
from lmcommon.configuration import Configuration

logger = LMLogger.get_logger()


class BrowserIdentityManager(IdentityManager):
    """Class for authenticating a user and accessing user identity in a no-cache mode suitable for web hosting. """

    def __init__(self, config_obj: Configuration) -> None:
        """Constructor"""
        # Call super constructor
        IdentityManager.__init__(self, config_obj=config_obj)
        self.auth_dir = os.path.join(self.config.config['git']['working_directory'], '.labmanager', 'identity')

    def is_authenticated(self, access_token: Optional[str] = None, id_token: Optional[str] = None) -> bool:
        """Method to check if the user is currently authenticated in the context of this identity manager

        Returns:
            bool
        """
        return self.is_token_valid(access_token)

    def is_token_valid(self, access_token: Optional[str] = None) -> bool:
        """Method to check if the user's access token session is still valid

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
        if access_token is None or id_token is None:
            err_dict = {"code": "missing_token",
                        "description": "JWT must be provided to authenticate user if no local "
                                       "stored identity is available"}
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

        # Check if it's the first time this user has logged into this instance
        self._check_first_login(self.user.username, access_token)

        return self.user

    def logout(self) -> None:
        """Method to logout a user if applicable

        Returns:
            None
        """
        self.user = None
        self.rsa_key = None
        logger.info("Logout complete.")
