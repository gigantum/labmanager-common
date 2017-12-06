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
import re
import uuid
import datetime
from typing import (Any, Dict, List, Tuple, Optional)

from lmcommon.activity.detaildb import ActivityDetailDB
from lmcommon.activity.records import ActivityDetailRecord, ActivityRecord


class ActivityStore(object):
    """The ActivityStore class provides a centralized interface to activity data stored in both the git log and db.

    High-level information is stored directly in the git commit messages stored in the git log of a LabBook. For more
    detailed information and arbitrary information a custom checkout-aware file based key-value store is used.

    The ActivityStore class stores ActivityRecords in the git log and ActivityDetailRecords in the database after
    proper serialization. The linked commit indiciate which git record the ActivityRecord is annotating
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

        self.detaildb = ActivityDetailDB(labbook.root_dir, labbook.checkout_id,
                                         logfile_limit=labbook.labmanager_config.config['detaildb']['logfile_limit'])

        # Note record commit messages follow a special structure
        self.note_regex = re.compile(r"(?s)_GTM_ACTIVITY_START_.*?_GTM_ACTIVITY_END_")

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
            raise ValueError("{} tags provided, but a single Activity Record can only have {} tags.".format(len(tags),
                             self.max_num_tags))
        # Check tag length
        for tag in tags:
            if len(tag) > self.max_tag_length:
                msg = "tag `{}` has {} characters,".format(tag, len(tag))
                raise ValueError("{} but a  tag is limited to {} characters.".format(msg, self.max_tag_length))

        # Remove \`; as a very basic level of sanitization
        return [tag.strip().translate({ord(c): None for c in '\`;'}) for tag in tags]

    def _get_log_records(self, after: Optional[str]=None, before: Optional[str]=None,
                         first: Optional[int]=None, last: Optional[int]=None) -> List[Tuple[str, str, datetime.datetime]]:
        """Method to get ACTIVITY records from the git log with pagination support

        Returns:
            list: List of tuples of the format (log string, commit hash, commit datetime)
        """
        log_entries: List[Tuple[str, str, datetime.datetime]] = []
        kwargs = dict()

        # TODO: Add support for reverse paging
        if before:
            raise ValueError("Paging using the 'before' argument not yet supported.")
        if last:
            raise ValueError("Paging using the 'last' argument not yet supported.")

        if first:
            kwargs['max_count'] = first

        path_info: Optional[str] = None
        if after:
            path_info = after

        for entry in self.labbook.git.log(path_info=path_info, **kwargs):
            m = self.note_regex.match(entry['message'])
            if m:
                log_entries.append((m.group(0), entry['commit'], entry['committed_on']))

        return log_entries

    def create_activity_record(self, record: ActivityRecord) -> ActivityRecord:
        """Method to write an activity record and its details to the git log and detaildb

        Args:
            record(ActivityRecord): A populated activity record

        Returns:
            ActivityRecord
        """
        # If there isn't a linked commit, generate a UUID to uniquely ID the data in levelDB that will never
        # collide with the actual git hash space by making it 32 char vs. 40 for git
        if not record.linked_commit:
            record.linked_commit = uuid.uuid4().hex

        # Write all ActivityDetailObjects to the datastore
        for idx, detail in enumerate(record.detail_objects):
            updated_detail = self.put_detail_record(detail[3])
            record.update_detail_object(updated_detail, idx)

        # Add everything in the LabBook activity/log directory
        self.labbook.git.add_all(self.detaildb.root_path)

        # Commit changes and update record
        commit = self.labbook.git.commit(record.log_str)
        record.commit = commit.hexsha

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
            ar = ActivityRecord.from_log_str(m.group(0), commit, entry['committed_on'])
            return ar
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
        max_count = None
        if first:
            # We typically have 2 commits per activity, 1 for the actual user changes and 1 for our changes.
            # To page properly, load up to 2x the number requested plus 5 to be safe
            max_count = (first * 2) + 5

        # Get data from the git log
        log_data = self._get_log_records(after=after, first=max_count)

        if after:
            # If some data came back, the "after" record is included. Remove it due to standards on how paging works.
            if log_data:
                log_data = log_data[1:]

        # If extra stuff came back due to extra padding on git log op, prune
        if first:
            if len(log_data) > first:
                log_data = log_data[:first]

        if log_data:
            return [ActivityRecord.from_log_str(x[0], x[1], x[2]) for x in log_data]
        else:
            return []

    def _encode_write_options(self, compress: Optional[bool] = None) -> bytes:
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
        if compress is None:
            result = self.compress_details.to_bytes(1, byteorder='little')
        else:
            result = compress.to_bytes(1, byteorder='little')

        return result

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
        # Set compression option based on config and objects size
        compress = False
        if self.compress_details:
            if detail_obj.data_size >= self.compress_min_bytes:
                compress = True

        # Write record and store key
        detail_obj.key = self.detaildb.put(self._encode_write_options(compress=compress) +
                                           detail_obj.to_bytes(compress))

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
        options = self._decode_write_options(detail_bytes[:1])

        # Create object
        record = ActivityDetailRecord.from_bytes(detail_bytes[1:], decompress=options['compress'])
        record.key = detail_key

        return record

