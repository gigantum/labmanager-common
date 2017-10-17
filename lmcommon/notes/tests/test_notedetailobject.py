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
import sys
import random
import json
import base64

from lmcommon.notes import NoteDetailObject
from lmcommon.notes.note_store import NoteRecordEncoder


@pytest.fixture()
def gen_object_data():
    """A pytest fixture that creates data for a single note detail object"""
    key = ''.join(random.choice('0123456789abcdef') for i in range(30))
    uni = bytes(bytearray(random.getrandbits(8) for i in range(1020)))
    yield {'key': key, 'type': "blob", 'value': uni}


class TestNoteDetailObject:
    """Test the NoteDetailObject class"""

    def test_note_detail_object(self, gen_object_data):
        """Basic note detail object creation and interaction"""

        ndo = NoteDetailObject(gen_object_data["key"],
                               gen_object_data["type"],
                               gen_object_data["value"])

        assert type(ndo) == NoteDetailObject
        assert ndo.key == gen_object_data["key"]
        assert ndo.type == gen_object_data["type"]
        assert ndo.value == gen_object_data["value"]
        assert type(ndo.value) == bytes

    def test_to_dict(self, gen_object_data):
        """Test converting NoteDetailObject to a dict"""
        ndo = NoteDetailObject(gen_object_data["key"],
                               gen_object_data["type"],
                               gen_object_data["value"])

        assert {"key": gen_object_data["key"],
                "type": gen_object_data["type"],
                "value": gen_object_data["value"]} == ndo.to_dict()

    def test_to_json(self, gen_object_data):
        ndo = NoteDetailObject(gen_object_data["key"],
                               gen_object_data["type"],
                               gen_object_data["value"])

        assert json.dumps({"key": gen_object_data["key"],
                           "type": gen_object_data["type"],
                           "value": base64.b64encode(gen_object_data["value"]).decode("UTF-8")}) == ndo.to_json()

    def test_from_json(self, gen_object_data):
        """Test creating a NoteDetailObject from a json string"""
        json_str = json.dumps({"key": gen_object_data["key"],
                               "type": gen_object_data["type"],
                               "value": base64.b64encode(gen_object_data["value"]).decode("UTF-8")})

        ndo = NoteDetailObject.from_json(json_str)

        assert type(ndo) == NoteDetailObject
        assert ndo.key == gen_object_data["key"]
        assert ndo.type == gen_object_data["type"]
        assert type(ndo.value) == bytes
        assert ndo.value == gen_object_data["value"]

    def test_json_serialization(self, gen_object_data):
        """Test serializing to and from JSON"""
        ndo = NoteDetailObject(gen_object_data["key"],
                               gen_object_data["type"],
                               gen_object_data["value"])

        utf8_value = base64.b64encode(gen_object_data["value"]).decode("UTF-8")
        json_str = json.dumps(ndo, cls=NoteRecordEncoder)
        assert json.dumps({"key": gen_object_data["key"],
                           "type": gen_object_data["type"],
                           "value": utf8_value}) == json_str

        # Load and make sure everything is the same
        ndo2 = NoteDetailObject.from_json(json_str)

        assert ndo.__dict__ == ndo2.__dict__


