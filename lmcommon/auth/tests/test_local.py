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
import getpass

from lmcommon.configuration import Configuration
from lmcommon.fixtures import mock_config_file_with_auth
from lmcommon.auth.identity import get_identity_manager, AuthenticationError
from lmcommon.auth.local import LocalIdentityManager
from lmcommon.auth import User

#from lmcommon.auth.tests.fixtures import mock_config_file


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
        u2 = mgr.authenticate()
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

    @pytest.mark.skipif(getpass.getuser() == 'circleci', reason="Cannot test auth0 on CircleCI")
    def test_authenticate(self, mock_config_file_with_auth):
        """test get authenticating a user from a JWT"""
        # TODO: Possibly move to integration tests or fully mock since this makes a call out to Auth0
        config = Configuration(mock_config_file_with_auth[0])
        mgr = get_identity_manager(config)
        assert type(mgr) == LocalIdentityManager

        # Load User
        with pytest.raises(AuthenticationError):
            mgr.authenticate()

        # Go get a JWT for the test user from the dev auth client (real users are not in this DB)
        response = requests.post("https://gigantum.auth0.com/oauth/token", json=mock_config_file_with_auth[2])
        token_data = response.json()

        # Load User
        u = mgr.authenticate(token_data['access_token'])
        assert type(u) == User
        assert os.path.exists(os.path.join(mgr.auth_dir, 'user.json')) is True
        assert u.username == "johndoe"
        assert u.email == "john.doe@gmail.com"
        assert u.given_name == "John"
        assert u.family_name == "Doe"
