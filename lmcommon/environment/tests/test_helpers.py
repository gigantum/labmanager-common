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
from lmcommon.environment import get_package_manager

from lmcommon.environment.pip import PipPackageManager
from lmcommon.environment.conda import Conda2PackageManager, Conda3PackageManager
from lmcommon.environment.apt import AptPackageManager


class TestPackageManagerHelper(object):
    def test_get_pip(self):
        assert type(get_package_manager('pip')) == PipPackageManager
        assert type(get_package_manager('pip2')) == PipPackageManager

    def test_get_conda(self):
        assert type(get_package_manager('conda2')) == Conda2PackageManager
        assert type(get_package_manager('conda3')) == Conda3PackageManager

    def test_get_apt(self):
        assert type(get_package_manager('apt')) == AptPackageManager
        assert type(get_package_manager('apt-get')) == AptPackageManager

    def test_get_invalid(self):
        with pytest.raises(ValueError):
            get_package_manager("asdfasdf")
