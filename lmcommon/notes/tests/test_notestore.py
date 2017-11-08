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
from lmcommon.notes import NoteStore, NoteDetailObject, NoteLogLevel, NoteDetailDB


@pytest.fixture()
def mock_create_notestore():
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
        lb.new({"username": "default"}, "labbook1", username="default", description="my first labbook")
        ns = NoteStore(lb)

        yield ns, lb

    # Remove the temp_dir
    shutil.rmtree(temp_dir)


def helper_create_labbook_change(labbook, cnt=0):
    """Helper method to create a change to the labbook"""
    # Make a new file
    new_filename = os.path.join(labbook.root_dir, ''.join(random.choice('0123456789abcdef') for i in range(15)))
    with open(new_filename, 'wt') as f:
        f.write(''.join(random.choice('0123456789abcdef ') for i in range(50)))

    # Add and commit file
    labbook.git.add_all()
    return labbook.git.commit("test commit {}".format(cnt))


def helper_create_notedetailobject():
    """Helper to create a random NoteDetailObject"""
    return NoteDetailObject(''.join(random.choice('0123456789abcdef') for i in range(10)),
                            "my_obj_typ",
                            bytes(bytearray(random.getrandbits(8) for i in range(1020))))


class TestNoteStore:

    def test_create_notestore(self, mock_create_notestore):
        """Test to verify the notestore is initialized properly"""
        assert type(mock_create_notestore[0]) == NoteStore
        assert type(mock_create_notestore[0].labbook) == LabBook

    def test_put_get_detail_record(self, mock_create_notestore):
        """Test to test storing and retrieving data from the notestore"""

        # Create test values
        linked_hash1 = ''.join(random.choice('0123456789abcdef') for i in range(30))
        free_text1 = ''.join(random.choice('0123456789abcdefghijklmnopqrstuv;') for i in range(1000))
        objects1 = [helper_create_notedetailobject() for _ in range(1, 5)]

        linked_hash2 = ''.join(random.choice('0123456789abcdef') for i in range(30))
        free_text2 = ''.join(random.choice('0123456789abcdefghijklmnopqrstuv;') for i in range(1000))
        objects2 = [helper_create_notedetailobject() for _ in range(1, 2)]

        linked_hash3 = ''.join(random.choice('0123456789abcdef') for i in range(30))
        free_text3 = ''.join(random.choice('0123456789abcdefghijklmnopqrstuv;') for i in range(1000))
        objects3 = [helper_create_notedetailobject()]

        note_detail_key1 = mock_create_notestore[0].put_detail_record(linked_hash1, free_text1, objects1)
        note_detail_key2 = mock_create_notestore[0].put_detail_record(linked_hash2, free_text2, objects2)
        note_detail_key3 = mock_create_notestore[0].put_detail_record(linked_hash3, free_text3, objects3)

        detail_record = mock_create_notestore[0].get_detail_record(note_detail_key1)
        assert free_text1 == detail_record["free_text"]
        for true_obj, test_obj in zip(objects1, detail_record["objects"]):
            assert true_obj.__dict__ == test_obj.__dict__

        detail_record = mock_create_notestore[0].get_detail_record(note_detail_key2)
        assert free_text2 == detail_record["free_text"]
        for true_obj, test_obj in zip(objects2, detail_record["objects"]):
            assert true_obj.__dict__ == test_obj.__dict__

        detail_record = mock_create_notestore[0].get_detail_record(note_detail_key3)
        assert free_text3 == detail_record["free_text"]
        for true_obj, test_obj in zip(objects3, detail_record["objects"]):
            assert true_obj.__dict__ == test_obj.__dict__

    def test_validate_tags_length(self, mock_create_notestore):
        """Method to test limiting tag length"""
        max_length_tag = [''.join(random.choice('0123456789abcdef') for i in range(mock_create_notestore[0].max_tag_length))]
        too_big_tag = [''.join(random.choice('0123456789abcdef') for i in range(mock_create_notestore[0].max_tag_length + 1))]

        assert max_length_tag == mock_create_notestore[0]._validate_tags(max_length_tag)

        with pytest.raises(ValueError):
            mock_create_notestore[0]._validate_tags(too_big_tag)

    def test_validate_tags_num(self, mock_create_notestore):
        """Method to test limiting number of tags"""
        max_num_tag = ["{}".format(x) for x in range(mock_create_notestore[0].max_num_tags)]
        too_many_tag = ["{}".format(x) for x in range(mock_create_notestore[0].max_num_tags+1)]

        assert len(max_num_tag) == len(mock_create_notestore[0]._validate_tags(max_num_tag))

        with pytest.raises(ValueError):
            mock_create_notestore[0]._validate_tags(too_many_tag)

    def test_validate_tags_cleanup(self, mock_create_notestore):
        """Method to test tag validation and cleanup"""
        tags = ["goodtag", "another tag", "dup", "dup", "bad tag\`;"]
        clean_tags = mock_create_notestore[0]._validate_tags(tags)
        assert len(clean_tags) == 4
        assert "bad tag\`;" not in clean_tags
        assert "bad tag" in clean_tags
        assert "goodtag" in clean_tags
        assert "another tag" in clean_tags
        assert "dup" in clean_tags

    def test_create_get_note_summary(self, mock_create_notestore):
        """Method to test creating and getting an individual note summary"""
        # Create a repo change
        linked_commit = helper_create_labbook_change(mock_create_notestore[1])

        # Create Note Data
        note_data = {"linked_commit": linked_commit.hexsha,
                     "message": "This is a high level note message",
                     "level": NoteLogLevel.USER_MAJOR,
                     "tags": ["tag1", "tag2"],
                     "free_text": "as;ldkfjhas;dfghasd;lifhjasd;lfijhasd;lfijsdaf;lkjsadfl;ijhasdf",
                     "objects": [helper_create_notedetailobject(), helper_create_notedetailobject()]
                     }

        # Create Note
        note_commit = mock_create_notestore[0].create_note(note_data)

        # Get Note and check
        stored_note = mock_create_notestore[0].get_note_summary(note_commit.hexsha)

        assert note_data["note_detail_key"] == stored_note["note_detail_key"]
        assert note_data["linked_commit"] == stored_note["linked_commit"]
        assert note_data["message"] == stored_note["message"]
        assert note_data["level"] == stored_note["level"]
        assert sorted(note_data["tags"]) == sorted(stored_note["tags"])
        assert stored_note["note_commit"] == note_commit.hexsha
        assert stored_note["timestamp"] == note_commit.committed_datetime
        assert stored_note["author"] == {'name': 'Gigantum AutoCommit', 'email': 'noreply@gigantum.io'}

    def test_invalid_log_level(self, mock_create_notestore):
        """Method to test trying to create a note with an invalid log level"""
        # Create a repo change
        linked_commit = helper_create_labbook_change(mock_create_notestore[1])

        # Create Note Data
        note_data = {"linked_commit": linked_commit.hexsha,
                     "message": "This is a high level note message",
                     "level": "asdfasd",
                     "tags": ["tag1", "tag2"],
                     "free_text": "as;ldkfjhas;dfghasd;lifhjasd;lfijhasd;lfijsdaf;lkjsadfl;ijhasdf",
                     "objects": [helper_create_notedetailobject(), helper_create_notedetailobject()]
                     }

        # Create Note
        with pytest.raises(ValueError):
            mock_create_notestore[0].create_note(note_data)

    def test_get_note_does_not_exist(self, mock_create_notestore):
        """Test getting a note by a commit hash that does not exist"""
        with pytest.raises(ValueError):
            mock_create_notestore[0].get_note_summary("abcdabcdacbd")

    def test_create_get_note(self, mock_create_notestore):
        """Method to test creating and getting an individual note"""
        # Create a repo change
        linked_commit = helper_create_labbook_change(mock_create_notestore[1])

        # Create Note Data
        note_data = {"linked_commit": linked_commit.hexsha,
                     "message": "This is a high level note message",
                     "level": NoteLogLevel.USER_MAJOR,
                     "tags": ["tag1", "tag2"],
                     "free_text": "as;ldkfjhas;dfghasd;lifhjasd;lfijhasd;lfijsdaf;lkjsadfl;ijhasdf",
                     "objects": [helper_create_notedetailobject(), helper_create_notedetailobject()]
                     }

        # Create Note
        note_commit = mock_create_notestore[0].create_note(note_data)

        # Get Note and check
        stored_note = mock_create_notestore[0].get_note(note_commit.hexsha)

        assert note_data["linked_commit"] == stored_note["linked_commit"]
        assert note_data["message"] == stored_note["message"]
        assert note_data["level"] == stored_note["level"]
        assert sorted(note_data["tags"]) == sorted(stored_note["tags"])
        assert stored_note["note_commit"] == note_commit.hexsha
        assert stored_note["timestamp"] == note_commit.committed_datetime
        assert note_data["free_text"] == stored_note["free_text"]
        assert stored_note["author"] == {'name': 'Gigantum AutoCommit', 'email': 'noreply@gigantum.io'}

        for obj_truth, obj_test in zip(note_data["objects"], stored_note["objects"]):
            assert obj_truth.__dict__ == obj_test.__dict__

    def test_get_note_summaries(self, mock_create_notestore):
        """Method to test creating and getting a bunch of note summaries"""

        note_truth = []
        for cnt in range(0, 10):
            # Create a repo change
            linked_commit = helper_create_labbook_change(mock_create_notestore[1])

            # Create Note Data
            note_data = {"linked_commit": linked_commit.hexsha,
                         "message": "{} This is a high level note message".format(cnt),
                         "level": NoteLogLevel.USER_MAJOR,
                         "tags": ["tag1", "tag2", "{}".format(cnt)],
                         "free_text": "{} = as;ldkfjhas;dfghasdhjasd;lfijhasd;lfijsdaf;lkjsadfl;ijhasdf".format(cnt),
                         "objects": [helper_create_notedetailobject(), helper_create_notedetailobject()]
                         }

            # Create Note
            note_commit = mock_create_notestore[0].create_note(note_data)
            note_truth.append([note_data, note_commit])

        # Test Getting all the summaries
        summaries = mock_create_notestore[0].get_all_note_summaries()
        note_truth.reverse()

        for truth, test in zip(note_truth, summaries):
            assert truth[0]["linked_commit"] == test["linked_commit"]
            assert truth[0]["message"] == test["message"]
            assert truth[0]["level"] == test["level"]
            assert sorted(truth[0]["tags"]) == sorted(test["tags"])
            assert test["note_commit"] == truth[1].hexsha
            assert test["timestamp"] == truth[1].committed_datetime
            assert test["author"] == {'name': 'Gigantum AutoCommit', 'email': 'noreply@gigantum.io'}

    def test_get_notes(self, mock_create_notestore):
        """Method to test creating and getting a bunch of note summaries and converting them to notes"""

        note_truth = []
        for cnt in range(0, 10):
            # Create a repo change
            linked_commit = helper_create_labbook_change(mock_create_notestore[1])

            # Create Note Data
            note_data = {"linked_commit": linked_commit.hexsha,
                         "message": "{} This is a high level note message".format(cnt),
                         "level": NoteLogLevel.USER_MAJOR,
                         "tags": ["tag1", "tag2", "{}".format(cnt)],
                         "free_text": "{} = as;ldkfjhas;dfghasdhjasd;lfijhasd;lfijsdaf;lkjsadfl;ijhasdf".format(cnt),
                         "objects": [helper_create_notedetailobject(), helper_create_notedetailobject()]
                         }

            # Create Note
            note_commit = mock_create_notestore[0].create_note(note_data)
            note_truth.append([note_data, note_commit])

        # Test Getting all the summaries
        # RB summaries does not return correct note_detail_key
        summaries = mock_create_notestore[0].get_all_note_summaries()
        note_truth.reverse()

        for truth, test in zip(note_truth, summaries):
            test = mock_create_notestore[0].summary_to_note(test)
            assert truth[0]["linked_commit"] == test["linked_commit"]
            assert truth[0]["message"] == test["message"]
            assert truth[0]["level"] == test["level"]
            assert sorted(truth[0]["tags"]) == sorted(test["tags"])
            assert test["note_commit"] == truth[1].hexsha
            assert test["timestamp"] == truth[1].committed_datetime
            assert truth[0]["free_text"] == test["free_text"]
            assert test["author"] == {'name': 'Gigantum AutoCommit', 'email': 'noreply@gigantum.io'}

            for obj_truth, obj_test in zip(truth[0]["objects"], test["objects"]):
                assert obj_truth.__dict__ == obj_test.__dict__

    def test_rotate_log(self, mock_create_notestore):

        # insert objects until the log rotates twice
        note_detail_db = NoteDetailDB(mock_create_notestore[0]._entries_path, mock_create_notestore[0].labbook.labmanager_config)

        oldfnum = note_detail_db.latestfnum

        while note_detail_db.latestfnum == oldfnum:
            note_detail_db.put(os.urandom(100000))

        secondoldfnum = note_detail_db.latestfnum

        while note_detail_db.latestfnum == secondoldfnum:
            note_detail_db.put(os.urandom(100000))

        assert(note_detail_db.latestfnum == oldfnum+2)


