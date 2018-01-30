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
import json
from lmcommon.activity.records import ActivityDetailRecord, ActivityDetailType, ActivityRecord, ActivityType


class TestActivityRecord(object):

    def test_constructor(self):
        """Test the constructor"""
        ar = ActivityRecord(ActivityType.MILESTONE)

        assert type(ar) == ActivityRecord
        assert ar.type == ActivityType.MILESTONE
        assert ar.commit is None
        assert ar.linked_commit is None
        assert ar.message is None
        assert ar.show is True
        assert ar.importance is None
        assert ar.tags is None
        assert ar.detail_objects == []

        ar = ActivityRecord(ActivityType.CODE,
                            show=False,
                            message="message 1",
                            importance=23,
                            tags=['a', 'b'],
                            linked_commit='aadfadff',
                            username="user1",
                            email="user1@test.com")

        assert type(ar) == ActivityRecord
        assert ar.type == ActivityType.CODE
        assert ar.commit is None
        assert ar.linked_commit == 'aadfadff'
        assert ar.message == "message 1"
        assert ar.show is False
        assert ar.importance == 23
        assert ar.tags == ['a', 'b']
        assert ar.detail_objects == []
        assert ar.username == 'user1'
        assert ar.email == 'user1@test.com'

    def test_add_detail_object(self):
        """Test adding values to the detail object"""
        ar = ActivityRecord(ActivityType.CODE,
                            show=True,
                            message="added some code",
                            importance=50,
                            linked_commit='aaaaaaaa')

        adr = ActivityDetailRecord(ActivityDetailType.CODE)
        adr.add_value("text/plain", "this is some data")

        ar.add_detail_object(adr)

        assert len(ar.detail_objects) == 1
        assert ar.detail_objects[0][0] is True
        assert ar.detail_objects[0][1] == ActivityDetailType.CODE.value
        assert ar.detail_objects[0][2] == 0
        assert ar.detail_objects[0][3] == adr

    def test_add_detail_objects_sort(self):
        """Test adding values to the detail object"""
        ar = ActivityRecord(ActivityType.CODE,
                            show=True,
                            message="added some code",
                            importance=50,
                            linked_commit='aaaaaaaa')

        adr = ActivityDetailRecord(ActivityDetailType.CODE)
        adr.show = True
        adr.importance = 100
        adr.add_value("text/plain", "second")
        ar.add_detail_object(adr)

        adr = ActivityDetailRecord(ActivityDetailType.CODE)
        adr.show = True
        adr.importance = 200
        adr.add_value("text/plain", "first")
        ar.add_detail_object(adr)

        adr = ActivityDetailRecord(ActivityDetailType.CODE)
        adr.show = False
        adr.importance = 0
        adr.add_value("text/plain", "sixth")
        ar.add_detail_object(adr)

        adr = ActivityDetailRecord(ActivityDetailType.OUTPUT_DATA)
        adr.show = True
        adr.importance = 201
        adr.add_value("text/plain", "forth")
        ar.add_detail_object(adr)

        adr = ActivityDetailRecord(ActivityDetailType.RESULT)
        adr.show = True
        adr.importance = 201
        adr.add_value("text/plain", "third")
        ar.add_detail_object(adr)

        adr = ActivityDetailRecord(ActivityDetailType.INPUT_DATA)
        adr.show = False
        adr.importance = 201
        adr.add_value("text/plain", "fifth")
        ar.add_detail_object(adr)

        assert len(ar.detail_objects) == 6

        assert ar.detail_objects[0][3].data['text/plain'] == 'first'
        assert ar.detail_objects[1][3].data['text/plain'] == 'second'
        assert ar.detail_objects[2][3].data['text/plain'] == 'third'
        assert ar.detail_objects[3][3].data['text/plain'] == 'forth'
        assert ar.detail_objects[4][3].data['text/plain'] == 'fifth'
        assert ar.detail_objects[5][3].data['text/plain'] == 'sixth'

    def test_log_str_prop_errors(self):
        """Test the log string property"""
        ar = ActivityRecord(ActivityType.CODE,
                            show=True,
                            importance=50,
                            linked_commit='aaaaaaaa')

        with pytest.raises(ValueError):
            # Missing message
            _ = ar.log_str

        ar = ActivityRecord(ActivityType.CODE,
                            show=True,
                            message="added some code",
                            importance=50,
                            linked_commit='aaaaaaaa')

        adr = ActivityDetailRecord(ActivityDetailType.CODE)
        adr.add_value("text/plain", "this is some data")
        ar.add_detail_object(adr)

        with pytest.raises(ValueError):
            # Missing detail key for detail record
            ar.log_str

    def test_log_str_prop(self):
        """Test the log string property"""
        ar = ActivityRecord(ActivityType.CODE,
                            show=True,
                            message="added some code",
                            importance=50,
                            linked_commit='aaaaaaaa')

        adr = ActivityDetailRecord(ActivityDetailType.CODE)
        adr.add_value("text/plain", "this is some data")
        adr.key = "my_fake_detail_key"
        ar.add_detail_object(adr)

        assert ar.log_str == """_GTM_ACTIVITY_START_**
msg:added some code**
metadata:{"show":true,"importance":50,"type":2,"linked_commit":"aaaaaaaa","tags":null}**
details:**
4,1,0,my_fake_detail_key**
_GTM_ACTIVITY_END_"""

    def test_from_log_str(self):
        """Test the creating from a log string"""
        ar = ActivityDetailRecord.from_log_str("5,1,25,my_key")

        assert type(ar) == ActivityDetailRecord
        assert ar.type == ActivityDetailType.INPUT_DATA
        assert ar.key == "my_key"
        assert ar.show is True
        assert ar.importance == 25
        assert ar.tags == []
        assert ar.data == {}

    def test_update_detail_object(self):
        """Test converting to a dictionary"""
        ar = ActivityRecord(ActivityType.CODE,
                            show=True,
                            message="added some code",
                            importance=50,
                            linked_commit='aaaaaaaa')

        adr1 = ActivityDetailRecord(ActivityDetailType.CODE)
        adr1.show = True
        adr1.importance = 100
        adr1.add_value("text/plain", "first")
        ar.add_detail_object(adr1)

        adr2 = ActivityDetailRecord(ActivityDetailType.CODE)
        adr2.show = True
        adr2.importance = 0
        adr2.add_value("text/plain", "second")
        ar.add_detail_object(adr2)

        assert len(ar.detail_objects) == 2
        assert ar.detail_objects[0][3].data['text/plain'] == 'first'
        assert ar.detail_objects[1][3].data['text/plain'] == 'second'

        adr2.importance = 200

        ar.update_detail_object(adr2, 1)

        assert len(ar.detail_objects) == 2
        assert ar.detail_objects[0][3].data['text/plain'] == 'second'
        assert ar.detail_objects[1][3].data['text/plain'] == 'first'
