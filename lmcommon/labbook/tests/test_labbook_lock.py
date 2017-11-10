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

from lmcommon.labbook import LabBook
from lmcommon.fixtures import mock_labbook


def write_function(filename: str, delay: int, value: str, labbook: LabBook) -> None:
    """
    A test function that appends to a file after a delay
    """
    time.sleep(delay)
    with labbook.lock_labbook():
        with open(filename, 'at') as f:
            f.write(value)
            time.sleep(2)


class TestLabBookLock(object):
    def test_simple_write(self, mock_labbook):
        """Test simple lock case"""
        filename = os.path.join(mock_labbook[2].root_dir, 'testfile.txt')

        write_function(filename, 0, "1", mock_labbook[2])

        with open(filename, 'rt') as f:
            data = f.read()

        assert data == "1"

    def test_multiple_acquires(self, mock_labbook):
        """Test trying to lock around multiple writes"""
        filename = os.path.join(mock_labbook[2].root_dir, 'testfile.txt')

        proc1 = Process(target=write_function, args=(filename, 1, "1", mock_labbook[2]))
        proc1.start()
        proc2 = Process(target=write_function, args=(filename, 0, "2", mock_labbook[2]))
        proc2.start()
        proc3 = Process(target=write_function, args=(filename, .5, "3", mock_labbook[2]))
        proc3.start()

        time.sleep(7)
        proc1.join()
        proc1.terminate()
        proc2.join()
        proc2.terminate()
        proc3.join()
        proc3.terminate()

        with open(filename, 'rt') as f:
            data = f.read()

        assert data == "231"




