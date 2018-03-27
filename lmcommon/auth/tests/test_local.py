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
import pytest
import os
import requests
import responses
import time
import mock
from typing import Optional

from lmcommon.configuration import Configuration
from lmcommon.fixtures import mock_config_file_with_auth, mock_config_file_with_auth_first_login, cleanup_auto_import
from lmcommon.auth.identity import get_identity_manager, AuthenticationError
from lmcommon.auth.local import LocalIdentityManager
from lmcommon.auth import User


def mock_import(archive_path: str, username: str, owner: str,
                config_file: Optional[str] = None, base_filename: Optional[str] = None,
                remove_source: bool = True) -> str:
    if not username:
        username = "johndoe"
    if not base_filename:
        base_filename = "awful-intersection-demo"

    lb_dir = os.path.join('/mnt', 'gigantum', username, username, "labbooks", base_filename)
    os.makedirs(lb_dir)

    return lb_dir


class TestIdentityLocal(object):
    def test_load_user_no_user(self, mock_config_file_with_auth):
        """test getting an identity manager"""
        config = Configuration(mock_config_file_with_auth[0])
        mgr = get_identity_manager(config)
        assert type(mgr) == LocalIdentityManager

        # Load User
        assert mgr._load_user() is None

    def test_save_load_user(self, mock_config_file_with_auth):
        """test getting an identity manager"""
        config = Configuration(mock_config_file_with_auth[0])
        mgr = get_identity_manager(config)
        assert type(mgr) == LocalIdentityManager

        u = User()
        u.username = "johndoe"
        u.email = "john.doe@gmail.com"
        u.given_name = "John"
        u.family_name = "Doe"
        mgr.user = u

        # Save User
        assert os.path.exists(os.path.join(mgr.auth_dir, 'user.json')) is False
        mgr._save_user()
        assert os.path.exists(os.path.join(mgr.auth_dir, 'user.json')) is True

        # Load User
        u2 = mgr._load_user()
        assert type(u2) == User

        assert u.username == u2.username
        assert u.email == u2.email
        assert u.given_name == u2.given_name
        assert u.family_name == u2.family_name

    def test_logout_user(self, mock_config_file_with_auth):
        """test getting an identity manager"""
        config = Configuration(mock_config_file_with_auth[0])
        mgr = get_identity_manager(config)
        assert type(mgr) == LocalIdentityManager

        u = User()
        u.username = "johndoe"
        u.email = "john.doe@gmail.com"
        u.given_name = "John"
        u.family_name = "Doe"
        mgr.user = u

        # Save User
        assert os.path.exists(os.path.join(mgr.auth_dir, 'user.json')) is False
        mgr._save_user()
        assert os.path.exists(os.path.join(mgr.auth_dir, 'user.json')) is True

        # Load User
        mgr.logout()
        assert os.path.exists(os.path.join(mgr.auth_dir, 'user.json')) is False
        assert mgr.user is None
        assert mgr._load_user() is None

    def test_authenticate_user_exists(self, mock_config_file_with_auth):
        """test getting an identity manager"""
        config = Configuration(mock_config_file_with_auth[0])
        mgr = get_identity_manager(config)
        assert type(mgr) == LocalIdentityManager

        u = User()
        u.username = "johndoe"
        u.email = "john.doe@gmail.com"
        u.given_name = "John"
        u.family_name = "Doe"
        mgr.user = u

        # Save User
        assert os.path.exists(os.path.join(mgr.auth_dir, 'user.json')) is False
        mgr._save_user()
        assert os.path.exists(os.path.join(mgr.auth_dir, 'user.json')) is True

        # Load User
        u2 = mgr.get_user_profile()
        assert type(u2) == User

        assert u.username == u2.username
        assert u.email == u2.email
        assert u.given_name == u2.given_name
        assert u.family_name == u2.family_name

    def test_get_profile_attribute(self, mock_config_file_with_auth):
        """test getting profile attributes safely from the profile dictionary"""
        config = Configuration(mock_config_file_with_auth[0])
        mgr = get_identity_manager(config)

        profile_data = {"username": "",
                        "email": "test@test.com"}

        assert mgr._get_profile_attribute(profile_data, "email") == "test@test.com"
        assert mgr._get_profile_attribute(profile_data, "email", False) == "test@test.com"

        assert mgr._get_profile_attribute(profile_data, "username", False) is None

        with pytest.raises(AuthenticationError):
            mgr._get_profile_attribute(profile_data, "username")
        with pytest.raises(AuthenticationError):
            mgr._get_profile_attribute(profile_data, "username", True)

        with pytest.raises(AuthenticationError):
            mgr._get_profile_attribute(profile_data, "first_name")

        assert mgr._get_profile_attribute(profile_data, "first_name", False) is None

    def test_is_session_valid(self, mock_config_file_with_auth):
        """test check for valid session"""
        # TODO: Possibly move to integration tests or fully mock since this makes a call out to Auth0
        config = Configuration(mock_config_file_with_auth[0])
        mgr = get_identity_manager(config)
        assert type(mgr) == LocalIdentityManager

        # Invalid with no token
        assert mgr.is_token_valid() is False
        assert mgr.is_token_valid(None) is False
        assert mgr.is_token_valid("asdfasdfasdf") is False

        # Go get a JWT for the test user from the dev auth client (real users are not in this DB)
        response = requests.post("https://gigantum.auth0.com/oauth/token", json=mock_config_file_with_auth[2])
        token_data = response.json()

        assert mgr.is_token_valid(token_data['access_token']) is True
        assert mgr.rsa_key is not None

    def test_is_authenticated_token(self, mock_config_file_with_auth):
        """test checking if the user is authenticated via a token"""
        # TODO: Possibly move to integration tests or fully mock since this makes a call out to Auth0
        config = Configuration(mock_config_file_with_auth[0])
        mgr = get_identity_manager(config)
        assert type(mgr) == LocalIdentityManager

        # Invalid with no token
        assert mgr.is_authenticated() is False
        assert mgr.is_authenticated(None) is False
        assert mgr.is_authenticated("asdfasdfa") is False

        # Go get a JWT for the test user from the dev auth client (real users are not in this DB)
        response = requests.post("https://gigantum.auth0.com/oauth/token", json=mock_config_file_with_auth[2])
        token_data = response.json()

        assert mgr.is_authenticated(token_data['access_token']) is True

        # Seccond access should load from disk and not need a token
        mgr2 = get_identity_manager(config)
        assert mgr2.is_authenticated() is True
        assert mgr2.is_authenticated("asdfasdfa") is True  # An "expired" token will essentially do this

        # Double check logging out un-authenticates
        mgr2.logout()
        assert mgr.is_authenticated() is False
        assert mgr2.is_authenticated() is False

    def test_get_user_profile(self, mock_config_file_with_auth):
        """test getting a user profile from Auth0"""
        # TODO: Possibly move to integration tests or fully mock since this makes a call out to Auth0
        config = Configuration(mock_config_file_with_auth[0])
        mgr = get_identity_manager(config)
        assert type(mgr) == LocalIdentityManager

        # Load User
        with pytest.raises(AuthenticationError):
            # Should fail without a token
            mgr.get_user_profile()

        # Go get a JWT for the test user from the dev auth client (real users are not in this DB)
        response = requests.post("https://gigantum.auth0.com/oauth/token", json=mock_config_file_with_auth[2])
        token_data = response.json()

        # Load User
        u = mgr.get_user_profile(token_data['access_token'])
        assert type(u) == User
        assert os.path.exists(os.path.join(mgr.auth_dir, 'user.json')) is True
        assert u.username == "johndoe"
        assert u.email == "john.doe@gmail.com"
        assert u.given_name == "John"
        assert u.family_name == "Doe"

        # Seccond access should load from disk and not need a token
        mgr2 = get_identity_manager(config)
        u2 = mgr2.get_user_profile()
        assert type(u) == User
        assert os.path.exists(os.path.join(mgr.auth_dir, 'user.json')) is True
        assert u2.username == "johndoe"
        assert u2.email == "john.doe@gmail.com"
        assert u2.given_name == "John"
        assert u2.family_name == "Doe"

        # Double check logging out un-authenticates
        mgr2.logout()
        with pytest.raises(AuthenticationError):
            # Should fail without a token
            mgr.get_user_profile()
        with pytest.raises(AuthenticationError):
            # Should fail without a token
            mgr2.get_user_profile()

    def test_check_first_login_user_locally(self, mock_config_file_with_auth_first_login,
                                            cleanup_auto_import):
        """Test login, but the user already logged into this instance"""
        # fake the user already existing by creating the user directory
        working_dir = mock_config_file_with_auth_first_login[1]
        os.makedirs(os.path.join(working_dir, "johndoe"))

        config = Configuration(mock_config_file_with_auth_first_login[0])
        mgr = get_identity_manager(config)

        # Go get a JWT for the test user from the dev auth client (real users are not in this DB)
        response = requests.post("https://gigantum.auth0.com/oauth/token",
                                 json=mock_config_file_with_auth_first_login[2])
        token_data = response.json()

        mgr._check_first_login("johndoe", access_token=token_data['access_token'])

        # Should not import labbook - note we aren't mocking all the way to the workers
        time.sleep(5)
        assert os.path.exists(os.path.join('/mnt', 'gigantum', "johndoe", "johndoe", "labbooks",
                                           "awful-intersections-demo")) is False

    @mock.patch('lmcommon.dispatcher.jobs.import_labboook_from_zip', side_effect=mock_import)
    @responses.activate
    def test_check_first_login_no_user_locally_in_repo(self, mock_import, mock_config_file_with_auth_first_login,
                                                       cleanup_auto_import):
        """Test login with the user in the repo alread"""
        # Add mock for call to auth service
        responses.add(responses.GET, 'https://usersrv.gigantum.io/user',
                      json={'exists': True}, status=200)
        responses.add_passthru("https://gigantum.auth0.com/oauth/token")

        config = Configuration(mock_config_file_with_auth_first_login[0])
        mgr = get_identity_manager(config)

        # Go get a JWT for the test user from the dev auth client (real users are not in this DB)
        response = requests.post("https://gigantum.auth0.com/oauth/token",
                                 json=mock_config_file_with_auth_first_login[2])
        token_data = response.json()

        mgr._check_first_login("johndoe", access_token=token_data['access_token'])

        # Should import labbook - note we aren't mocking all the way to the workers
        time.sleep(5)
        assert os.path.exists(os.path.join('/mnt', 'gigantum', "johndoe", "johndoe", "labbooks",
                                           "awful-intersections-demo")) is True

    @mock.patch('lmcommon.dispatcher.jobs.import_labboook_from_zip', side_effect=mock_import)
    @responses.activate
    def test_check_first_login_no_user_locally_no_repo(self, mock_import, mock_config_file_with_auth_first_login,
                                                       cleanup_auto_import):

        """Test login with the user in the repo alread"""
        # Add mock for call to auth service
        responses.add(responses.GET, 'https://usersrv.gigantum.io/user',
                      json={'exists': False}, status=404)
        responses.add(responses.POST, 'https://usersrv.gigantum.io/user', status=201)
        responses.add_passthru("https://gigantum.auth0.com/oauth/token")

        config = Configuration(mock_config_file_with_auth_first_login[0])
        mgr = get_identity_manager(config)

        # Go get a JWT for the test user from the dev auth client (real users are not in this DB)
        response = requests.post("https://gigantum.auth0.com/oauth/token",
                                 json=mock_config_file_with_auth_first_login[2])
        token_data = response.json()

        mgr._check_first_login("johndoe", access_token=token_data['access_token'])

        # Should import labbook - note we aren't mocking all the way to the workers
        time.sleep(5)
        assert os.path.exists(os.path.join('/mnt', 'gigantum', "johndoe", "johndoe", "labbooks",
                                           "awful-intersections-demo")) is True
