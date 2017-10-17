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
import os
import json
import re
from enum import Enum
import base64
import uuid
from typing import (Any, Dict, List, Union)

from lmcommon.labbook import LabBook
from lmcommon.notes.note_detail import NoteDetailDB


class NoteLogLevel(Enum):
    """Enumeration representing the note 'level' in the hierarchy"""
    # User generated Notes
    USER_NOTE = 10
    USER_MAJOR = 11
    USER_MINOR = 12

    # Automatic "system" generated notes
    AUTO_MAJOR = 21
    AUTO_MINOR = 22
    AUTO_DETAIL = 23


class NoteRecordEncoder(json.JSONEncoder):
    """Custom JSON encoder to properly serialize NodeDetailObject and NoteLogLevel instances

    Binary blobs are encoded as base64 when serializing to json

    """
    def default(self, obj):
        if isinstance(obj, NoteDetailObject):
            # If a NoteDetailObject generate a dict
            obj_dict = obj.to_dict()
            if type(obj_dict["value"]) == bytes:
                obj_dict["value"] = base64.b64encode(obj_dict["value"]).decode("UTF-8")
            return obj_dict
        if isinstance(obj, NoteLogLevel):
            return obj.value

        return json.JSONEncoder.default(self, obj)


class NoteDetailObject(object):
    """A class to represent note detail objects that can be stored in a note entry"""
    def __init__(self, key: str, blob_type: str, value: bytes) -> None:
        """Constructor

        Args:
            key(str): Key used to access and identify the object
            blob_type(str): The type of object (useful for converting from byte array to actual thing)
            value(bytes): A byte array of the object to store. Can be any binary type from file to serialized dict
        """
        self.key: str = key
        self.type: str = blob_type
        self.value: bytes = value

    @staticmethod
    def from_json(json_str: str) -> 'NoteDetailObject':
        """Static method to create a NoteDetailObject instance from a json string

        Args:
            json_str(str): The json representation of a NoteDetailObject

        Returns:
            NoteDetailObject
        """
        data = json.loads(json_str)

        # Decode object from base64 back to a bytes object
        value = base64.b64decode(data["value"])
        return NoteDetailObject(data["key"], data["type"], value)

    @staticmethod
    def from_image(image_file: str) -> None:
        """Static method to create a NoteDetailObject instance from an image file

        Args:
            image_file(str): Absolute path to an image file that can be opened by Pillow

        Returns:
            NoteDetailObject
        """
        # an example of how this can be augmented with time to help devs manage objects
        raise NotImplemented

    def to_dict(self) -> Dict[str, Union[str, bytes]]:
        """Method to dump an object to a dictionary"""
        return {"key": self.key,
                "type": self.type,
                "value": self.value}

    def to_json(self) -> str:
        """Method to dump an object to a json string for storage"""
        data = {"key": self.key,
                "type": self.type,
                "value": base64.b64encode(self.value).decode("UTF-8")}
        return json.dumps(data)


class NoteStore(object):
    """The NoteStore class provides a centralized interface to note data stored in both the git log and levelDB.

    High-level information is stored directly in the git commit messages stored in the git log of a LabBook. For more
    detailed information and arbitrary information an embedded levelDB is used with detailed notes records stored
    through a key/value interface.

    Detailed notes records are stored and accessed by the LINKED COMMIT hash (str) and are encoded as JSON objects.
    The linked commit is the commit hash of the original commit that contained the changes made to the repository.
    """

    def __init__(self, labbook: LabBook) -> None:
        """ Load the database for the specified labbook

        Args:
            labbook(LabBook): A lmcommon.labbook.LabBook instance
        """
        # Configuration parameters
        self.max_num_tags: int = 100
        self.max_tag_length: int = 256

        self.labbook: LabBook = labbook

        # Note record commit messages follow a special structure
        self.note_regex = re.compile(r"gtmNOTE_: ([\w\s\S]+)\ngtmjson_metadata_: (.*)")

        # instantiate notes levelDB at _root_dir/.gigantum/notes/
        self._entries_path: str = os.path.join(labbook.root_dir, ".gigantum", "notes", "log")

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

    def create_note(self, note_data: Dict[str, Any]) -> str:
        """Create a new note record in the LabBook

            note_data Fields:
                note_detail_key(bytes): can be undefined. will be set by creation.
                linked_commit(str): Commit hash to the git commit the note is describing
                message(str): Short summary message, limited to 256 characters
                level(NoteLogLevel): The level in the note hierarchy
                tags(list): A list of strings for structured tagging and search
                free_text(str): A large free-text blob that is stored in levelDB
                objects(list): A list of NoteDetailObjects

        Args:
            note_data(dict): Dictionary of note field data

        Returns:
            str: The commit hash of the newly created note record
        """
        # Verify log level is valid
        NoteLogLevel(note_data['level'])

        # If there isn't a linked commit, generate a UUID to uniquely ID the data in levelDB that will never
        # collide with the actual git hash space by making it 32 char vs. 40 for git
        if not note_data['linked_commit']:
            linked_commit_hash = uuid.uuid4().hex
        else:
            linked_commit_hash = str(note_data['linked_commit'])

        # Create record using the linked_commit hash as the reference
        note_detail_key = self.put_detail_record(linked_commit_hash,
                               note_data['free_text'],
                               note_data['objects'])

        note_data['note_detail_key'] = note_detail_key

        # Add everything in the LabBook notes/log directory in case it is new or a new log file has been created
        self.labbook.git.add_all(os.path.expanduser(os.path.join(".gigantum", "notes", "log")))
        
        # Prep log message
        note_metadata = {'level': note_data['level'],
                         'note_detail_key': base64.b64encode(note_detail_key).decode('utf-8'),
                         'linked_commit': note_data['linked_commit'], 
                         'tags': self._validate_tags(note_data['tags'])}

        # format note metadata into message
        message = "gtmNOTE_: {}\ngtmjson_metadata_: {}".format(note_data['message'], json.dumps(note_metadata,
                                                                                                cls=NoteRecordEncoder))

        # Commit the changes as you've updated the notes DB
        return self.labbook.git.commit(message)

    def summary_to_note(self, note: Dict[str, Any]) -> Dict[str, Any]:
        """Method to convert a single note summary into a full note

        Args:
            note(dict): An existing not summary

        Returns:
            dict: A dictionary of note data
        """
        # Merge detail record into dict
        note.update(self.get_detail_record(note["note_detail_key"]))
        return note

    def get_note(self, commit: str) -> Dict[str, Any]:
        """Method to get a single note record in dictionary form

        Args:
            commit(str): The commit hash of the note record

        Returns:
            dict: A dictionary of note data for the provided commit
        """
        # Get note summary
        note = self.get_note_summary(commit)
        return self.summary_to_note(note)

    def get_note_summary(self, commit) -> Dict[str, Any]:
        """Method to get a single note summary in dictionary form

        Args:
            commit(str): The commit hash of the note record

        Returns:
            dict: A dictionary of note data for the provided commit
        """
        entry = self.labbook.git.log_entry(commit)
        m = self.note_regex.match(entry["message"])
        if m:
            # summary data from git log
            message = m.group(1)
            note_metadata = json.loads(m.group(2))

            # Sort tags if there are any
            if note_metadata['tags']:
                tags = sorted(note_metadata["tags"])
            else:
                tags = []

            return {"note_commit": entry["commit"],
                    "linked_commit": note_metadata["linked_commit"],
                    "message": message,
                    "level": NoteLogLevel(note_metadata["level"]),
                    "note_detail_key": base64.b64decode(note_metadata['note_detail_key'].encode('utf-8')),
                    "timestamp": entry["committed_on"],
                    "tags": tags,
                    "author": entry["author"]
                    }
        else:
            raise ValueError("Note commit {} not found".format(commit))

    def get_all_note_summaries(self) -> List[Dict[str, Any]]:
        """Naive implementation that gets a list of note summary dictionaries for all note entries

            Note Summary Dictionary Fields:
                note_detail_key: key to look up the note detail
                note_commit(str): Commit hash of this note entry
                linked_commit(str): Commit hash to the git commit the note is describing
                message(str): Short summary message, limited to 256 characters
                level(NoteLogLevel): The level in the note hierarchy
                timestamp(datetime): The datetime of the commit
                tags(list): A list of strings for structured tagging and search

        Returns:
            list: List of all note dictionaries without detail information
        """
        note_summaries = []
        for entry in self.labbook.git.log():
            m = self.note_regex.match(entry['message'])
            if m:
                # summary data from git log
                message = m.group(1)
                note_metadata = json.loads(m.group(2))
                note_summaries.append({"note_commit": entry["commit"],
                                       "linked_commit": note_metadata["linked_commit"],
                                       "message": message,
                                       "level": NoteLogLevel(note_metadata["level"]),
                                       "note_detail_key": base64.b64decode(note_metadata['note_detail_key'].encode('utf-8')),
                                       "timestamp": entry["committed_on"],
                                       "tags": sorted(note_metadata["tags"]),
                                       "author": entry["author"]
                                       })
        return note_summaries

    def put_detail_record(self, linked_commit_hash: str, free_text: str, objects: list) -> bytes: 
        """
            Put a notes detailed entry into a levelDB.

            Args:
                linked_commit_hash(string): commit hash of the commit the note entry references
                free_text(str): a free text string
                objects(list): a list of NoteDetailObjects

            Returns:
                None

            Raises:
                Exception
        """
        # Open outside try (can't close if this fails)
        note_detail_db = NoteDetailDB(self._entries_path)

        # level db wants binary
        binary_value = json.dumps({"linked_commit": linked_commit_hash,
                                   "free_text": free_text,
                                   "objects": objects}, cls=NoteRecordEncoder).encode('utf8')
        # Write record
        note_key = note_detail_db.put(binary_value)
        return note_key

    def get_detail_record(self, note_key: bytes) -> Dict[str, Any]:
        """
            Fetch a notes detailed entry from a levelDB by commit hash

            Args:
                note_key : the key returned from the notes DB when storing.

            Returns:
                 dict
        """
        # Create DB connection
        note_detail_db = NoteDetailDB(self._entries_path)

        # Get value from key-value store
        note_record = note_detail_db.get(note_key)
        # TODO RB how big is the header programmatically
        binary_value = note_record[20:]

        # Load into dictionary
        value = json.loads(binary_value.decode('utf8'))

        # Populate Objects
        objects = []
        if value["objects"]:
            for obj_data in value["objects"]:
                objects.append(NoteDetailObject(obj_data["key"],
                                                obj_data["type"],
                                                base64.b64decode(obj_data["value"])))
        return {"free_text": value["free_text"], "objects": objects}
