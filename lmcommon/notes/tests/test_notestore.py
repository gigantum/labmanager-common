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
import tempfile
import os
import sys
import uuid
import shutil
import yaml
import random

from lmcommon.labbook import LabBook
from lmcommon.notes import NoteStore


@pytest.fixture()
def test_notestore():
    """A pytest fixture that creates a notestore (and labbook) and deletes directory after test"""
    # Create a temporary working directory
    temp_dir = os.path.join(tempfile.tempdir, uuid.uuid4().hex)
    os.makedirs(temp_dir)
    
    with tempfile.NamedTemporaryFile(mode="wt") as fp:
        # Write a temporary config file
        fp.write("""core:
  team_mode: false 
git:
  backend: 'filesystem'
  working_directory: '{}'""".format(temp_dir))
        fp.seek(0)

        lb = LabBook(fp.name)
        labbook_dir = lb.new(username="test", name="labbook1", description="my first labbook")
        ns = NoteStore(lb)

        yield ns # provide the fixture value

    # Remove the temp_dir
    shutil.rmtree(temp_dir)


class TestNoteStore():

    def test_ns_get_put(self, test_notestore):
        """Write note details and read note details from the NoteStore"""

        # a long value
        key1 = ''.join(random.choice('0123456789abcdef') for i in range(30))
        uni1 = u''.join(chr(random.randint(0x80, sys.maxunicode)) for _ in range(9999))
        value1 = {'uni1': uni1}

        # an embedded list
        key2 = ''.join(random.choice('0123456789abcdef') for i in range(30))
        uni2 = u''.join(chr(random.randint(0x80, sys.maxunicode)) for _ in range(533))
        value2 = {'outer2': 'outerval2', 'embedded2': ['foo', uni2]}


        # an embedded dict
        key3 = ''.join(random.choice('0123456789abcdef') for i in range(30))
        uni3 = u''.join(chr(random.randint(0x80, sys.maxunicode)) for _ in range(700))
        value3 = {'outer3': 'outerval3', 'embedded3': { 'bar': uni3, 'moo': 'mooval'}}

        # interleave puts and gets
        test_notestore.put_entry(key1, value1)

        test_notestore.put_entry(key2, value2)

        ret1 = test_notestore.get_entry(key1)
        assert ( ret1['uni1'] == uni1 )

        test_notestore.put_entry(key3, value3)

        ret2 = test_notestore.get_entry(key2)
        assert ( ret2['embedded2'][1] == uni2 )

        ret3 = test_notestore.get_entry(key3)
        assert ( ret3['embedded3']['bar'] == uni3 )


