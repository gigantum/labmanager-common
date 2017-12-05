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
import uuid
import shutil
import random
from datetime import datetime

from lmcommon.labbook import LabBook
from lmcommon.activity.detaildb import ActivityDetailDB
from lmcommon.activity.records import ActivityType, ActivityRecord, ActivityDetailRecord, ActivityDetailType
from lmcommon.activity import ActivityStore
from lmcommon.fixtures import mock_config_with_activitystore


def helper_create_labbook_change(labbook, cnt=0):
    """Helper method to create a change to the labbook"""
    # Make a new file
    new_filename = os.path.join(labbook.root_dir, ''.join(random.choice('0123456789abcdef') for i in range(15)))
    with open(new_filename, 'wt') as f:
        f.write(''.join(random.choice('0123456789abcdef ') for i in range(50)))

    # Add and commit file
    labbook.git.add_all()
    return labbook.git.commit("test commit {}".format(cnt))


def helper_create_activitydetailobject():
    """Helper to create a random ActivityDetailRecord"""
    adr = ActivityDetailRecord(ActivityDetailType(random.randint(0, 6)), key=f"my_key_{random.randint(0, 99999)}")
    adr.add_value("text/plain", ''.join(random.choice('abcdefghijklmnopqrstuvwxyz ') for _ in range(50)))


class TestActivityStore:
    def test_create_activitystore(self, mock_config_with_activitystore):
        """Test to verify the ActivityStore is initialized properly"""
        assert type(mock_config_with_activitystore[0]) == ActivityStore
        assert type(mock_config_with_activitystore[0].labbook) == LabBook

        assert mock_config_with_activitystore[0].compress_details is True
        assert mock_config_with_activitystore[0].compress_min_bytes == 4000

    def test_validate_tags_length(self, mock_config_with_activitystore):
        """Method to test limiting tag length"""
        max_length_tag = [''.join(random.choice('0123456789abcdef') for i in range(mock_config_with_activitystore[0].max_tag_length))]
        too_big_tag = [''.join(random.choice('0123456789abcdef') for i in range(mock_config_with_activitystore[0].max_tag_length + 1))]

        assert max_length_tag == mock_config_with_activitystore[0]._validate_tags(max_length_tag)

        with pytest.raises(ValueError):
            mock_config_with_activitystore[0]._validate_tags(too_big_tag)

    def test_validate_tags_num(self, mock_config_with_activitystore):
        """Method to test limiting number of tags"""
        max_num_tag = ["{}".format(x) for x in range(mock_config_with_activitystore[0].max_num_tags)]
        too_many_tag = ["{}".format(x) for x in range(mock_config_with_activitystore[0].max_num_tags+1)]

        assert len(max_num_tag) == len(mock_config_with_activitystore[0]._validate_tags(max_num_tag))

        with pytest.raises(ValueError):
            mock_config_with_activitystore[0]._validate_tags(too_many_tag)

    def test_validate_tags_cleanup(self, mock_config_with_activitystore):
        """Method to test tag validation and cleanup"""
        tags = ["goodtag", "another tag", "dup", "dup", "bad tag\`;"]
        clean_tags = mock_config_with_activitystore[0]._validate_tags(tags)
        assert len(clean_tags) == 4
        assert "bad tag\`;" not in clean_tags
        assert "bad tag" in clean_tags
        assert "goodtag" in clean_tags
        assert "another tag" in clean_tags
        assert "dup" in clean_tags

    def test_write_options(self, mock_config_with_activitystore):
        """Test encoding/decoding write options"""
        store = mock_config_with_activitystore[0]

        wo = store._encode_write_options()
        assert type(wo) == bytes
        assert wo == b'\x01'

        wo_decoded = store._decode_write_options(wo)
        assert wo_decoded['compress'] is True

        wo = store._encode_write_options(compress=False)
        assert wo == b'\x00'

        wo_decoded = store._decode_write_options(wo)
        assert wo_decoded['compress'] is False

    def test_put_get_detail_record(self, mock_config_with_activitystore):
        """Test to test storing and retrieving data from the activity detail db"""
        # Create test values
        adr1 = ActivityDetailRecord(ActivityDetailType.CODE)
        adr1.show = True
        adr1.importance = 100
        adr1.add_value("text/plain", "first")

        adr2 = ActivityDetailRecord(ActivityDetailType.CODE)
        adr2.show = True
        adr2.importance = 0
        adr2.add_value("text/plain", "second")

        adr1 = mock_config_with_activitystore[0].put_detail_record(adr1)
        adr2 = mock_config_with_activitystore[0].put_detail_record(adr2)

        assert adr1.key is not None
        assert adr2.key is not None
        assert type(adr1.key) == str
        assert type(adr2.key) == str

        # Load
        adr1_loaded = mock_config_with_activitystore[0].get_detail_record(adr1.key)
        adr2_loaded = mock_config_with_activitystore[0].get_detail_record(adr2.key)

        assert adr1.key == adr1_loaded.key
        assert adr1.importance == adr1_loaded.importance
        assert adr1.type == adr1_loaded.type
        assert adr1.is_loaded == adr1_loaded.is_loaded == True
        assert adr1.data == adr1_loaded.data

        assert adr2.key == adr2_loaded.key
        assert adr2.importance == adr2_loaded.importance
        assert adr2.type == adr2_loaded.type
        assert adr2.is_loaded == adr2_loaded.is_loaded == True
        assert adr2.data == adr2_loaded.data

    def test_put_get_detail_record_with_compression(self, mock_config_with_activitystore):
        """Test to test storing and retrieving data from the activity detail db w/ compression"""
        # Create test values
        adr1 = ActivityDetailRecord(ActivityDetailType.CODE)
        adr1.show = True
        adr1.importance = 100
        adr1.add_value("text/plain", "first" * 1000)

        adr2 = ActivityDetailRecord(ActivityDetailType.CODE)
        adr2.show = True
        adr2.importance = 0
        adr2.add_value("text/plain", "second" * 1000)

        adr1 = mock_config_with_activitystore[0].put_detail_record(adr1)
        adr2 = mock_config_with_activitystore[0].put_detail_record(adr2)

        assert adr1.key is not None
        assert adr2.key is not None
        assert type(adr1.key) == str
        assert type(adr2.key) == str

        # Load
        adr1_loaded = mock_config_with_activitystore[0].get_detail_record(adr1.key)
        adr2_loaded = mock_config_with_activitystore[0].get_detail_record(adr2.key)

        assert adr1.key == adr1_loaded.key
        assert adr1.importance == adr1_loaded.importance
        assert adr1.type == adr1_loaded.type
        assert adr1.is_loaded == adr1_loaded.is_loaded is True
        assert adr1.data == adr1_loaded.data

        assert adr2.key == adr2_loaded.key
        assert adr2.importance == adr2_loaded.importance
        assert adr2.type == adr2_loaded.type
        assert adr2.is_loaded == adr2_loaded.is_loaded is True
        assert adr2.data == adr2_loaded.data

    def test_put_get_activity_record(self, mock_config_with_activitystore):
        """Method to test creating and getting an individual activity record"""
        adr1 = ActivityDetailRecord(ActivityDetailType.CODE)
        adr1.show = True
        adr1.importance = 100
        adr1.add_value("text/plain", "this is a thing" * 1000)
        adr1.tags = ['tag1', 'tag2']

        adr2 = ActivityDetailRecord(ActivityDetailType.RESULT)
        adr2.show = False
        adr2.importance = 0
        adr2.add_value("text/plain", "another item")
        adr2.tags = ['tag1', 'tag2']

        linked_commit = helper_create_labbook_change(mock_config_with_activitystore[1], 1)

        ar = ActivityRecord(ActivityType.CODE,
                            show=True,
                            message="added some code",
                            importance=50,
                            linked_commit=linked_commit.hexsha)

        ar.add_detail_object(adr1)
        ar.add_detail_object(adr2)

        assert ar.commit is None

        # Create Activity Record
        ar_written = mock_config_with_activitystore[0].create_activity_record(ar)
        assert ar.commit is not None

        # Get Note and check
        stored_ar = mock_config_with_activitystore[0].get_activity_record(ar_written.commit)

        assert ar.commit == stored_ar.commit
        assert ar.importance == stored_ar.importance
        assert ar.linked_commit == stored_ar.linked_commit
        assert ar.log_str == stored_ar.log_str
        assert ar.message == stored_ar.message
        assert ar.show == stored_ar.show
        assert ar.tags == stored_ar.tags
        assert ar.type == stored_ar.type
        assert len(ar.detail_objects) == len(stored_ar.detail_objects)

        assert ar.detail_objects[0][0] == stored_ar.detail_objects[0][0]
        assert ar.detail_objects[0][1] == stored_ar.detail_objects[0][1]
        assert ar.detail_objects[0][2] == stored_ar.detail_objects[0][2]

        assert ar.detail_objects[0][3].is_loaded is True
        assert ar.detail_objects[1][3].is_loaded is True

        assert stored_ar.detail_objects[0][3].is_loaded is False
        assert stored_ar.detail_objects[1][3].is_loaded is False

    def test_put_get_activity_record_with_tag(self, mock_config_with_activitystore):
        """Method to test creating and getting an individual activity record with a tag"""
        adr1 = ActivityDetailRecord(ActivityDetailType.CODE)
        adr1.show = True
        adr1.importance = 100
        adr1.add_value("text/plain", "this is a thing" * 1000)
        adr1.tags = ['tag1', 'tag2']

        linked_commit = helper_create_labbook_change(mock_config_with_activitystore[1], 1)

        ar = ActivityRecord(ActivityType.CODE,
                            show=True,
                            message="added some code",
                            importance=50,
                            linked_commit=linked_commit.hexsha)

        ar.add_detail_object(adr1)
        ar.tags = ['tag1', 'tag2']

        assert ar.commit is None

        # Create Activity Record
        ar_written = mock_config_with_activitystore[0].create_activity_record(ar)
        assert ar.commit is not None

        # Get Note and check
        stored_ar = mock_config_with_activitystore[0].get_activity_record(ar_written.commit)

        assert ar.commit == stored_ar.commit
        assert ar.importance == stored_ar.importance
        assert ar.linked_commit == stored_ar.linked_commit
        assert ar.log_str == stored_ar.log_str
        assert ar.message == stored_ar.message
        assert ar.show == stored_ar.show
        assert ar.tags == stored_ar.tags
        assert ar.type == stored_ar.type
        assert len(ar.detail_objects) == len(stored_ar.detail_objects)

        assert ar.detail_objects[0][0] == stored_ar.detail_objects[0][0]
        assert ar.detail_objects[0][1] == stored_ar.detail_objects[0][1]
        assert ar.detail_objects[0][2] == stored_ar.detail_objects[0][2]

        assert ar.detail_objects[0][3].is_loaded is True
        assert stored_ar.detail_objects[0][3].is_loaded is False

    def test_get_activity_record_does_not_exist(self, mock_config_with_activitystore):
        """Test getting a note by a commit hash that does not exist"""
        with pytest.raises(ValueError):
            mock_config_with_activitystore[0].get_activity_record("abcdabcdacbd")

    def test_get_log_records(self, mock_config_with_activitystore):
        """Method to test querying the git log for some records"""
        linked_commit = helper_create_labbook_change(mock_config_with_activitystore[1], 1)

        ar = ActivityRecord(ActivityType.CODE,
                            show=True,
                            message="added some code",
                            importance=50,
                            linked_commit=linked_commit.hexsha)

        record1 = mock_config_with_activitystore[0].create_activity_record(ar)

        linked_commit = helper_create_labbook_change(mock_config_with_activitystore[1], 1)

        ar = ActivityRecord(ActivityType.CODE,
                            show=True,
                            message="added some code",
                            importance=50,
                            linked_commit=linked_commit.hexsha)

        record2 = mock_config_with_activitystore[0].create_activity_record(ar)

        linked_commit = helper_create_labbook_change(mock_config_with_activitystore[1], 1)

        ar = ActivityRecord(ActivityType.CODE,
                            show=True,
                            message="added some code",
                            importance=50,
                            linked_commit=linked_commit.hexsha)

        record3 = mock_config_with_activitystore[0].create_activity_record(ar)

        log_records = mock_config_with_activitystore[0]._get_log_records()
        assert len(log_records) == 3
        assert type(log_records[0][0]) == str
        assert len(log_records[0][0]) == 40
        assert type(log_records[0][1]) == str

        log_records = mock_config_with_activitystore[0]._get_log_records(first=1)
        assert len(log_records) == 1

        log_records = mock_config_with_activitystore[0]._get_log_records(after=record2.commit)
        assert len(log_records) == 2

        log_records = mock_config_with_activitystore[0]._get_log_records(after=record2.commit, first=1)
        assert len(log_records) == 1

        with pytest.raises(ValueError):
            _ = mock_config_with_activitystore[0]._get_log_records(before=record2.commit)

    def test_get_activity_records(self, mock_config_with_activitystore):
        """Method to test creating and getting a bunch of activity records"""

        linked_commit = helper_create_labbook_change(mock_config_with_activitystore[1], 1)

        ar = ActivityRecord(ActivityType.CODE,
                            show=True,
                            message="added some code 1",
                            importance=50,
                            linked_commit=linked_commit.hexsha)

        record1 = mock_config_with_activitystore[0].create_activity_record(ar)

        linked_commit = helper_create_labbook_change(mock_config_with_activitystore[1], 1)

        ar = ActivityRecord(ActivityType.CODE,
                            show=True,
                            message="added some code 2",
                            importance=50,
                            linked_commit=linked_commit.hexsha)

        record2 = mock_config_with_activitystore[0].create_activity_record(ar)

        linked_commit = helper_create_labbook_change(mock_config_with_activitystore[1], 1)

        ar = ActivityRecord(ActivityType.CODE,
                            show=True,
                            message="added some code 3",
                            importance=50,
                            linked_commit=linked_commit.hexsha)

        record3 = mock_config_with_activitystore[0].create_activity_record(ar)

        activity_records = mock_config_with_activitystore[0].get_activity_records()
        assert len(activity_records) == 3
        assert activity_records[0].commit == record3.commit
        assert activity_records[0].linked_commit == record3.linked_commit
        assert activity_records[0].message == record3.message
        assert activity_records[1].commit == record2.commit
        assert activity_records[1].linked_commit == record2.linked_commit
        assert activity_records[1].message == record2.message
        assert activity_records[2].commit == record1.commit
        assert activity_records[2].linked_commit == record1.linked_commit
        assert activity_records[2].message == record1.message

        activity_records = mock_config_with_activitystore[0].get_activity_records(first=1)
        assert len(activity_records) == 1
        assert activity_records[0].commit == record3.commit
        assert activity_records[0].linked_commit == record3.linked_commit
        assert activity_records[0].message == record3.message

        activity_records = mock_config_with_activitystore[0].get_activity_records(after=record2.commit)
        assert len(activity_records) == 1
        assert activity_records[0].commit == record1.commit
        assert activity_records[0].linked_commit == record1.linked_commit
        assert activity_records[0].message == record1.message

        activity_records = mock_config_with_activitystore[0].get_activity_records(after=record3.commit, first=1)
        assert len(activity_records) == 1
        assert activity_records[0].commit == record2.commit
        assert activity_records[0].linked_commit == record2.linked_commit
        assert activity_records[0].message == record2.message
