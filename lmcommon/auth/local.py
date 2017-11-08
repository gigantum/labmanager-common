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
from jose import jwt
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
        unverified_header = jwt.get_unverified_header(id_token)

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

    def _get_profile_attribute(self, profile_data: Dict[str, str], attribute: str,
                               required: bool =True) -> Optional[str]:
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

    def authenticate(self, access_token: Optional[str] = None) -> Optional[User]:
        """Method to authenticate a user by verifying the jwt signiture OR loading from backend storage

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
            # Validate JWT signiture
            if not access_token:
                err_dict = {"code": "missing_token",
                            "description": "JWT must be provided to authenticate user if no local "
                                           "stored identity is available"}
                raise AuthenticationError(err_dict, 401)

            # Get public RSA key
            rsa_key = self._get_jwt_public_key(access_token)

            if rsa_key:
                try:
                    payload = jwt.decode(access_token, rsa_key,
                                         algorithms=self.config.config['auth']['signing_algorithm'],
                                         audience=self.config.config['auth']['audience'],
                                         issuer="https://" + self.config.config['auth']['provider_domain'] + "/")

                    # Go get the user profile data
                    url = "https://" + self.config.config['auth']['provider_domain'] + "/userinfo"
                    response = requests.get(url, headers={'Authorization': f'Bearer {access_token}'})
                    if response.status_code != 200:
                        AuthenticationError({"code": "profile_unauthorized",
                                             "description": "Failed to get user profile data"}, 401)
                    user_profile = response.json()

                except jwt.ExpiredSignatureError:
                    raise AuthenticationError({"code": "token_expired",
                                               "description": "token is expired"}, 401)
                except jwt.JWTClaimsError:
                    raise AuthenticationError({"code": "invalid_claims",
                                               "description":
                                                   "incorrect claims,"
                                                   "please check the audience and issuer"}, 401)
                except Exception:
                    raise AuthenticationError({"code": "invalid_header",
                                               "description":
                                                   "Unable to parse authentication"
                                                   " token."}, 400)

                # Create user identity
                self.user = User()
                self.user.email = self._get_profile_attribute(user_profile, "email", required=True)
                self.user.username = self._get_profile_attribute(user_profile, "nickname", required=True)
                self.user.given_name = self._get_profile_attribute(user_profile, "given_name", required=False)
                self.user.family_name = self._get_profile_attribute(user_profile, "family_name", required=False)

                # Save User to local storage
                self._save_user()

                return self.user

            raise AuthenticationError({"code": "invalid_header", "description": "Unable to find appropriate key"}, 400)

    def logout(self) -> None:
        """Method to logout a user if applicable

        Returns:
            None
        """
        data_file = os.path.join(self.auth_dir, 'user.json')
        if os.path.exists(data_file):
            os.remove(data_file)

        logger.info("Removed user identity from local storage.")
        self.user = None

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
            raise IOError("User identity data already exists. Must explicitly remove to store new identity.")

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
