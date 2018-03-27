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

from lmcommon.fixtures import mock_config_file_with_auth
from lmcommon.configuration import Configuration
from lmcommon.auth.identity import get_identity_manager, IdentityManager
from lmcommon.auth.local import LocalIdentityManager
from lmcommon.auth import User


class TestIdentity(object):
    def test_user_obj(self):
        """Manipulating user object"""
        u = User()

        assert u.username is None
        assert u.email is None
        assert u.given_name is None
        assert u.family_name is None

        u.username = "test"
        u.email = "test@test.com"
        u.given_name = "Testy"
        u.family_name = "McTestface"

        assert u.username == "test"
        assert u.email == "test@test.com"
        assert u.given_name == "Testy"
        assert u.family_name == "McTestface"

    def test_get_identity_manager_errors(self, mock_config_file_with_auth):
        """Testing get_identity_manager error handling"""
        config = Configuration(mock_config_file_with_auth[0])
        config.config['auth']['identity_manager'] = "asdfasdf"

        with pytest.raises(ValueError):
            get_identity_manager(config)

        del config.config['auth']['identity_manager']

        with pytest.raises(ValueError):
            get_identity_manager(config)

        del config.config['auth']

        with pytest.raises(ValueError):
            get_identity_manager(config)

    def test_get_identity_manager(self, mock_config_file_with_auth):
        """test getting an identity manager"""
        config = Configuration(mock_config_file_with_auth[0])

        mgr = get_identity_manager(config)

        assert type(mgr) == LocalIdentityManager
        assert mgr.config == config
        assert mgr.auth_dir == os.path.join(mock_config_file_with_auth[1], '.labmanager', 'identity')
        assert mgr.user is None
        assert mgr.rsa_key is None
        assert mgr._user is None