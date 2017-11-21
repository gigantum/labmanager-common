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
import base64
import json
import os
import re
import uuid
from typing import (Any, Dict, List, Union, Optional)

from lmcommon.activity.detaildb import ActivityDetailDB
from lmcommon.activity import ActivityDetailRecord, ActivityDetailType, ActivityRecord, ActivityType


class ActivityStore(object):
    """The ActivityStore class provides a centralized interface to activity data stored in both the git log and db.

    High-level information is stored directly in the git commit messages stored in the git log of a LabBook. For more
    detailed information and arbitrary information an embedded levelDB is used with detailed notes records stored
    through a key/value interface.

    Detailed notes records are stored and accessed by the LINKED COMMIT hash (str) and are encoded as JSON objects.
    The linked commit is the commit hash of the original commit that contained the changes made to the repository.
    """

    def __init__(self, labbook) -> None:
        """ Load the database for the specified labbook

        Args:
            labbook(LabBook): A lmcommon.labbook.LabBook instance
        """
        # Configuration parameters
        self.max_num_tags: int = 100
        self.max_tag_length: int = 256

        self.labbook = labbook

        self.detaildb = ActivityDetailDB(labbook.root, labbook.checkout_id,
                                         logfile_limit=labbook.config.config['detaildb']['logfile_limit'])

        # Note record commit messages follow a special structure
        self.note_regex = re.compile(r"(?s)_GTM_ACTIVITY_START_.*?_GTM_ACTIVITY_END_")
    
        # instantiate notes levelDB at _root_dir/.gigantum/notes/
        self._entries_path: str = os.path.join(labbook.root_dir, ".gigantum", "notes", "log")

        # Params used during detail object serialization
        if self.labbook.labmanager_config.config['detaildb']['options']['compress']:
            self.compress_details: bool = self.labbook.labmanager_config.config['detaildb']['options']['compress']
            self.compress_min_bytes = self.labbook.labmanager_config.config['detaildb']['options']['compress_min_bytes']
        else:
            self.compress_details: bool = False
            self.compress_min_bytes: int = 0

    def _validate_tags(self, tags: List[str]) -> List[str]:
        """Method to clean and validate tags

        Args:
            tags(list): A list of strings

        Returns:
            (list): a list of strings
        """
        # allow for no tags
        if not tags:
            return []

        # Remove duplicate tags
        tags = list(set(tags))

        # Check total number of tags
        if len(tags) > self.max_num_tags:
            raise ValueError("{} tags provided, but a single Note can only have {} tags.".format(len(tags),
                                                                                                 self.max_num_tags))
        # Check tag length
        for tag in tags:
            if len(tag) > self.max_tag_length:
                msg = "tag `{}` has {} characters,".format(tag, len(tag))
                raise ValueError("{} but a  tag is limited to {} characters.".format(msg, self.max_tag_length))

        # Remove \`; as a very basic level of sanitization
        return [tag.strip().translate({ord(c): None for c in '\`;'}) for tag in tags]

    def _get_log_records(self, after: Optional[str]=None, before: Optional[str]=None,
                         first: Optional[int]=None, last: Optional[int]=None) -> List[str]:
        """Method to get ACTIVITY records from the git log

        Returns:
            list: List of log entries
        """
        log_entries = []
        kwargs = dict()

        # TODO: Add support for reverse paging
        if before:
            raise ValueError("Paging using the 'before' argument not yet supported.")
        if last:
            raise ValueError("Paging using the 'last' argument not yet supported.")

        if first:
            kwargs['max_count'] = first

        if after:
            path_info = after
        else:
            path_info = None

        for entry in self.labbook.git.log(path_info=path_info, **kwargs):
            m = self.note_regex.match(entry['message'])
            if m:
                log_entries.append(m.group(1))

        return log_entries

    def put_activity_record(self, record: ActivityRecord) -> ActivityRecord:
        """Method to write an activity record and its details to the git log and detaildb

        Args:
            record(ActivityRecord): A populated activity record

        Returns:
            ActivityRecord
        """
        # Verify log level is valid
        # NoteLogLevel(note_data['level'])

        # If there isn't a linked commit, generate a UUID to uniquely ID the data in levelDB that will never
        # collide with the actual git hash space by making it 32 char vs. 40 for git
        if not record.linked_commit:
            record.linked_commit = uuid.uuid4().hex

        # Write all ActivityDetailObjects to the datastore
        for idx, detail in enumerate(record.detail_objects):
            updated_detail = self.put_detail_record(detail)
            record.update_detail_object(updated_detail, idx)

        # Add everything in the LabBook activity/log directory
        self.labbook.git.add_all(os.path.expanduser(os.path.join(".gigantum", "activity", "log")))

        # Commit changes and update record
        record.commit = self.labbook.git.commit(record.log_str)

        return record

    def get_activity_record(self, commit: str) -> ActivityRecord:
        """Method to get a single ActivityRecord

        Args:
            commit(str): The commit hash of the activity record

        Returns:
            ActivityRecord
        """
        entry = self.labbook.git.log_entry(commit)
        m = self.note_regex.match(entry["message"])
        if m:
            log_str = m.group(1)
            return ActivityRecord.from_log_str(log_str)
        else:
            raise ValueError("Activity data not found in commit {}".format(commit))

    def get_activity_records(self, after: Optional[str]=None,
                             first: Optional[int]=None) -> List[Optional[ActivityRecord]]:
        """Method to get a list of activity records, with forward paging supported

        Args:
            after(str): Commit hash to page after
            first(int): Number of records to get

        Returns:
            List[ActivityRecord]
        """
        if first:
            # We typically have 2 commits per activity, 1 for the actual user changes and 1 for our changes.
            # To page properly, load up to 2x the number requested plus 10 to be safe
            first = (first * 2) + 10

        # Get data from the git log
        log_data = self._get_log_records(after=after, first=first)

        # If extra stuff came back due to extra padding on git log op, prune
        if len(log_data) > first:
            log_data = log_data[:first]

        if log_data:
            return [ActivityRecord.from_log_str(x) for x in log_data]
        else:
            return []

    def _encode_write_options(self) -> bytes:
        """Method to encode any options for writing details to a byte

        bit option
        0   compress/decompress data on storage
        1   reserved
        2   reserved
        3   reserved
        4   reserved
        5   reserved
        6   reserved
        7   reserved

        Returns:
            bytes
        """
        return self.compress_details.to_bytes(1, byteorder='little')

    @staticmethod
    def _decode_write_options(option_byte: bytes) -> dict:
        """Method to decode the write options header byte

        Args:
            option_byte(bytes): Byte containing option flags

        Returns:
            dict
        """
        return {"compress": bool(option_byte[0])}

    def put_detail_record(self, detail_obj: ActivityDetailRecord) -> ActivityDetailRecord:
        """Method to write a detail record to the activity detail db

        Args:
            detail_obj(ActivityDetailRecord): The detail record to write

        Returns:
            ActivityDetailRecord: the detail record updated with the key
        """
        # Write record and store key
        detail_obj.key = self.detaildb.put(self._encode_write_options() + detail_obj.to_bytes(self.compress_details))

        return detail_obj

    def get_detail_record(self, detail_key: str) -> ActivityDetailRecord:
        """Method to fetch a detail entry from the activity detail db

            Args:
                detail_key : the key returned from the activity detail DB when storing.

            Returns:
                 ActivityDetailRecord
        """
        # Get value from key-value store
        detail_bytes = self.detaildb.get(detail_key)

        # Remove header
        options = self._decode_write_options(bytes(detail_bytes[0]))

        # Create object
        record = ActivityDetailRecord.from_bytes(detail_bytes[2:], decompress_details=options['compress'])
        record.key = detail_key

        return record













    # def create_note(self, note_data: Dict[str, Any]) -> str:
    #     """Create a new note record in the LabBook
    #
    #         note_data Fields:
    #             note_detail_key(str): can be undefined. will be set by creation.
    #             linked_commit(str): Commit hash to the git commit the note is describing
    #             message(str): Short summary message, limited to 256 characters
    #             level(NoteLogLevel): The level in the note hierarchy
    #             tags(list): A list of strings for structured tagging and search
    #             free_text(str): A large free-text blob that is stored in levelDB
    #             objects(list): A list of NoteDetailObjects
    #
    #     Args:
    #         note_data(dict): Dictionary of note field data
    #
    #     Returns:
    #         str: The commit hash of the newly created note record
    #     """
    #     # Verify log level is valid
    #     NoteLogLevel(note_data['level'])
    #
    #     # If there isn't a linked commit, generate a UUID to uniquely ID the data in levelDB that will never
    #     # collide with the actual git hash space by making it 32 char vs. 40 for git
    #     if not note_data['linked_commit']:
    #         linked_commit_hash = uuid.uuid4().hex
    #     else:
    #         linked_commit_hash = str(note_data['linked_commit'])
    #
    #     # Create record using the linked_commit hash as the reference
    #     note_detail_key = self.put_detail_record(linked_commit_hash,
    #                            note_data['free_text'],
    #                            note_data['objects'])
    #
    #     note_data['note_detail_key'] = note_detail_key
    #
    #     # Add everything in the LabBook notes/log directory in case it is new or a new log file has been created
    #     self.labbook.git.add_all(os.path.expanduser(os.path.join(".gigantum", "notes", "log")))
    #
    #     # Prep log message
    #     note_metadata = {'level': note_data['level'],
    #                      'note_detail_key': note_detail_key,
    #                      'linked_commit': note_data['linked_commit'],
    #                      'tags': self._validate_tags(note_data['tags'])}
    #
    #     # format note metadata into message
    #     message = "gtmNOTE_: {}\ngtmjson_metadata_: {}".format(note_data['message'], json.dumps(note_metadata,
    #                                                                                             cls=NoteRecordEncoder))
    #
    #     # Commit the changes as you've updated the notes DB
    #     return self.labbook.git.commit(message)
    #
    # def summary_to_note(self, note: Dict[str, Any]) -> Dict[str, Any]:
    #     """Method to convert a single note summary into a full note
    #
    #     Args:
    #         note(dict): An existing not summary
    #
    #     Returns:
    #         dict: A dictionary of note data
    #     """
    #     # Merge detail record into dict
    #     note.update(self.get_detail_record(note["note_detail_key"]))
    #     return note
    #
    # def get_note(self, commit: str) -> Dict[str, Any]:
    #     """Method to get a single note record in dictionary form
    #
    #     Args:
    #         commit(str): The commit hash of the note record
    #
    #     Returns:
    #         dict: A dictionary of note data for the provided commit
    #     """
    #     # Get note summary
    #     note = self.get_note_summary(commit)
    #     return self.summary_to_note(note)
    #
    # def get_note_summary(self, commit) -> Dict[str, Any]:
    #     """Method to get a single note summary in dictionary form
    #
    #     Args:
    #         commit(str): The commit hash of the note record
    #
    #     Returns:
    #         dict: A dictionary of note data for the provided commit
    #     """
    #     entry = self.labbook.git.log_entry(commit)
    #     m = self.note_regex.match(entry["message"])
    #     if m:
    #         # summary data from git log
    #         message = m.group(1)
    #         note_metadata = json.loads(m.group(2))
    #
    #         # Sort tags if there are any
    #         if note_metadata['tags']:
    #             tags = sorted(note_metadata["tags"])
    #         else:
    #             tags = []
    #
    #         return {"note_commit": entry["commit"],
    #                 "linked_commit": note_metadata["linked_commit"],
    #                 "message": message,
    #                 "level": NoteLogLevel(note_metadata["level"]),
    #                 "note_detail_key": note_metadata['note_detail_key'],
    #                 "timestamp": entry["committed_on"],
    #                 "tags": tags,
    #                 "author": entry["author"]
    #                 }
    #     else:
    #         raise ValueError("Note commit {} not found".format(commit))
    #
    # def get_all_note_summaries(self) -> List[Dict[str, Any]]:
    #     """Naive implementation that gets a list of note summary dictionaries for all note entries
    #
    #         Note Summary Dictionary Fields:
    #             note_detail_key: key to look up the note detail
    #             note_commit(str): Commit hash of this note entry
    #             linked_commit(str): Commit hash to the git commit the note is describing
    #             message(str): Short summary message, limited to 256 characters
    #             level(NoteLogLevel): The level in the note hierarchy
    #             timestamp(datetime): The datetime of the commit
    #             tags(list): A list of strings for structured tagging and search
    #
    #     Returns:
    #         list: List of all note dictionaries without detail information
    #     """
    #     note_summaries = []
    #     for entry in self.labbook.git.log():
    #         m = self.note_regex.match(entry['message'])
    #         if m:
    #             # summary data from git log
    #             message = m.group(1)
    #             note_metadata = json.loads(m.group(2))
    #             note_summaries.append({"note_commit": entry["commit"],
    #                                    "linked_commit": note_metadata["linked_commit"],
    #                                    "message": message,
    #                                    "level": NoteLogLevel(note_metadata["level"]),
    #                                    "note_detail_key": note_metadata['note_detail_key'],
    #                                    "timestamp": entry["committed_on"],
    #                                    "tags": sorted(note_metadata["tags"]),
    #                                    "author": entry["author"]
    #                                    })
    #     return note_summaries
    #
    #
