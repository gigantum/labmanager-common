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
from lmcommon.fixtures import mock_config_file_with_auth_browser
from lmcommon.auth.identity import get_identity_manager, AuthenticationError
from lmcommon.auth.browser import BrowserIdentityManager
from lmcommon.auth import User


class TestIdentityBrowser(object):

    def test_is_session_valid(self, mock_config_file_with_auth_browser):
        """test check for valid session"""
        # TODO: Possibly move to integration tests or fully mock since this makes a call out to Auth0
        config = Configuration(mock_config_file_with_auth_browser[0])
        mgr = get_identity_manager(config)
        assert type(mgr) == BrowserIdentityManager

        # Invalid with no token
        assert mgr.is_token_valid() is False
        assert mgr.is_token_valid(None) is False
        assert mgr.is_token_valid("asdfasdfasdf") is False

        # Go get a JWT for the test user from the dev auth client (real users are not in this DB)
        response = requests.post("https://gigantum.auth0.com/oauth/token", json=mock_config_file_with_auth_browser[2])
        token_data = response.json()

        assert mgr.is_token_valid(token_data['access_token']) is True
        assert mgr.rsa_key is not None

    def test_is_authenticated_token(self, mock_config_file_with_auth_browser):
        """test checking if the user is authenticated via a token"""
        # TODO: Possibly move to integration tests or fully mock since this makes a call out to Auth0
        config = Configuration(mock_config_file_with_auth_browser[0])
        mgr = get_identity_manager(config)
        assert type(mgr) == BrowserIdentityManager

        # Invalid with no token
        assert mgr.is_authenticated() is False
        assert mgr.is_authenticated(None) is False
        assert mgr.is_authenticated("asdfasdfa") is False

        # Go get a JWT for the test user from the dev auth client (real users are not in this DB)
        response = requests.post("https://gigantum.auth0.com/oauth/token", json=mock_config_file_with_auth_browser[2])
        token_data = response.json()

        assert mgr.is_authenticated(token_data['access_token']) is True

        # Second access should fail since not cached
        mgr2 = get_identity_manager(config)
        assert mgr2.is_authenticated() is False
        assert mgr2.is_authenticated("asdfasdfa") is False  # An "expired" token will essentially do this

    def test_get_user_profile(self, mock_config_file_with_auth_browser):
        """test getting a user profile from Auth0"""
        # TODO: Possibly move to integration tests or fully mock since this makes a call out to Auth0
        config = Configuration(mock_config_file_with_auth_browser[0])
        mgr = get_identity_manager(config)
        assert type(mgr) == BrowserIdentityManager

        # Load User
        with pytest.raises(AuthenticationError):
            # Should fail without a token
            mgr.get_user_profile()

        # Go get a JWT for the test user from the dev auth client (real users are not in this DB)
        response = requests.post("https://gigantum.auth0.com/oauth/token", json=mock_config_file_with_auth_browser[2])
        token_data = response.json()

        # Load User
        u = mgr.get_user_profile(token_data['access_token'])
        assert type(u) == User
        assert u.username == "johndoe"
        assert u.email == "john.doe@gmail.com"
        assert u.given_name == "John"
        assert u.family_name == "Doe"

        # Second access should fail since not cached
        mgr2 = get_identity_manager(config)
        with pytest.raises(AuthenticationError):
            # Should fail without a token
            mgr2.get_user_profile()
