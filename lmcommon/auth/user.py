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
from typing import (Optional)


class User(object):
    """Class representing a Gigantum User Identity"""

    def __init__(self) -> None:
        """Constructor"""
        self._username: Optional[str] = None
        self._email: Optional[str] = None
        self._given_name: Optional[str] = None
        self._family_name: Optional[str] = None

    @property
    def username(self) -> Optional[str]:
        if self._username:
            return self._username
        else:
            return None

    @username.setter
    def username(self, value: str) -> None:
        self._username = value

    @property
    def email(self) -> Optional[str]:
        if self._email:
            return self._email
        else:
            return None

    @email.setter
    def email(self, value: str) -> None:
        self._email = value

    @property
    def given_name(self) -> Optional[str]:
        if self._given_name:
            return self._given_name
        else:
            return None

    @given_name.setter
    def given_name(self, value: str) -> None:
        self._given_name = value

    @property
    def family_name(self) -> Optional[str]:
        if self._family_name:
            return self._family_name
        else:
            return None

    @family_name.setter
    def family_name(self, value: str) -> None:
        self._family_name = value
