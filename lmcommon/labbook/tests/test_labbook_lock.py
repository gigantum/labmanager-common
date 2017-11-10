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
import time
import os
from multiprocessing import Process

from lmcommon.labbook.lock import lock_labbook
from lmcommon.fixtures import mock_labbook


def write_function(filename, delay, value):
    """
    A test function that appends to a file after a delay
    """
    time.sleep(delay)
    with open(filename, 'at') as f:
        f.write(value)


class TestLabBookLock(object):
    def test_simple_write(self, mock_labbook):
        """Test creating favorite in an invalid subdir"""
        filename = os.path.join(mock_labbook[2].root_dir, 'testfile.txt')

        with lock_labbook(mock_labbook[2]):
            write_function(filename, 0, "1")

        with open(filename, 'rt') as f:
            data = f.read()

        assert data == "1"

    #def test_simple_write(self, mock_labbook):
    #    """Test creating favorite in an invalid subdir"""
    #    filename = os.path.join(mock_labbook[2].root_dir, 'testfile.txt')
#
    #    proc1 = Process(target=write_function, args=(filename, 3, "1"))
    #    proc1.start()
    #    proc = Process(target=write_function, args=(filename, 3, "1"))
#
    #    with pytest.raises(ValueError):
    #        mock_labbook[2].create_favorite("blah", "test/file.file")

