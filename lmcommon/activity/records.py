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
import json
from enum import Enum
from typing import (Any, List, Optional)


class ActivityType(Enum):
    """Enumeration representing the type of Activity Record"""
    NOTE = 0
    ENVIRONMENT = 1
    CODE = 2
    INPUT_DATA = 3
    OUTPUT_DATA = 4
    MILESTONE = 5
    BRANCH = 6


class ActivityDetailType(Enum):
    """Enumeration representing the type of Activity Detail Record"""
    # User generated Notes
    CODE_EXECUTED = 0
    RESULT = 1
    ENVIRONMENT = 2
    CODE = 3
    INPUT_DATA = 4
    OUTPUT_DATA = 5


class ActivityDetailRecord(object):
    """A class to represent an activity detail entry that can be stored in an activity entry"""

    def __init__(self, detail_type: ActivityDetailType, key: Optional[str] = None, show: bool = True,
                 importance: Optional[int] = None) -> None:
        """Constructor

        Args:
            key(str): Key used to access and identify the object
        """
        # Key used to load detail record from the embedded detail DB
        self.key = key

        # Flag indicating if this record object has been populated with data (used primarily during lazy loading)
        self.is_loaded = False

        # Storage for detail record data, organized by MIME type to support proper rendering
        self.data: dict = dict()

        # Type indicating the category of detail
        self.type = detail_type

        # Boolean indicating if this item should be "shown" or "hidden"
        self.show = show

        # A score indicating the importance, currently expected to range from 0-255
        self.importance = importance

        # A list of tags for the record
        self.tags: Optional[List[str]] = None

    @property
    def log_str(self) -> str:
        """Method to create the identifying string stored in the git log

        Returns:
            str
        """
        if not self.key:
            raise ValueError("Detail Object key must be set before accessing the log str.")

        return "{},{},{},{}".format(self.type.value, int(self.show), self.importance, self.key)

    @staticmethod
    def from_log_str(log_str: str) -> 'ActivityDetailRecord':
        """Static method to create a ActivityDetailRecord instance from the identifying string stored in the git log

        Args:
            log_str(str): the identifying string stored in the git lo

        Returns:
            ActivityDetailRecord
        """
        type_int, show_int, importance, key = log_str.split(',')

        return ActivityDetailRecord(ActivityDetailType(type_int), show=bool(show_int), importance=importance, key=key)

    def add_value(self, mime_type: str, value: Any) -> None:
        """Method to add data to this record by MIME type

        Args:
            mime_type(str): The MIME type of the representation of the object
            value(Any): The value for this record

        Returns:
            None
        """
        if mime_type in self.data:
            raise ValueError("Attempting to duplicate a MIME type while adding detail data")

        # Store value
        self.data[mime_type] = value

        # Since you added data, it can be accessed now
        self.is_loaded = True


class ActivityRecord(object):
    """Class representing an Activity Record"""

    def __init__(self, activity_type: Optional[ActivityType] = None, show: bool = True, message: str = None,
                 importance: Optional[int] = None, tags: Optional[List[str]] = None) -> None:
        """Constructor

        Args:
            key(str): Key used to access and identify the object
        """
        # Commit hash of this record in the git log
        self.linked_commit = None

        # Commit hash of the commit this references
        self.linked_commit = None

        # Message summarizing the event
        self.message = message

        # String stored in the git log
        self._log_str: Optional[str] = None

        # Storage for detail objects in a tuple of (type, show, importance, object)
        self.detail_objects: Optional[List[tuple]] = list()

        # Type indicating the category of detail
        self.type = activity_type

        # Boolean indicating if this item should be "shown" or "hidden"
        self.show = show

        # A score indicating the importance, currently expected to range from 0-255
        self.importance = importance

        # A list of tags for the entire record
        self.tags = tags

    @staticmethod
    def from_log_str(log_str: str) -> 'ActivityRecord':
        """Static method to create a ActivityRecord instance from the identifying string stored in the git log

        Args:
            log_str(str): the identifying string stored in the git lo

        Returns:
            ActivityRecord
        """
        # Validate it is a record
        if log_str[0:20] == "_GTM_ACTIVITY_START_" and log_str[-18:] == "_GTM_ACTIVITY_END_":
            lines = log_str.split("**\n")
            message = lines[1][4:]
            metadata = json.loads(lines[2][9:])
            tags = json.loads(lines[3][5:])

            # Create record
            activity_record = ActivityRecord(ActivityType(metadata["type_id"]), message=message,
                                             show=metadata["show"],
                                             importance=metadata["importance"],
                                             tags=tags)

            # Add detail records
            for line in lines[5:]:
                if line == "_GTM_ACTIVITY_END_":
                    break

                # Append records
                activity_record.add_detail_object(ActivityDetailRecord.from_log_str(line))

            return activity_record
        else:
            raise ValueError("Malformed git log record. Cannot parse.")

    @property
    def log_str(self) -> str:
        """A property to create the identifying string stored in the git log

        Returns:
            str
        """
        if self.message:
            log_str = f"_GTM_ACTIVITY_START_**\nmsg:{self.message}**\n"
        else:
            raise ValueError("Message required when creating an activity object")

        meta = {"show": self.show, "importance": self.importance or 0,
                "type_name": self.type, "type_id": self.type.value}
        log_str = f"{log_str}metadata:{json.dumps(meta)}**\n"

        log_str = f"{log_str}tags:{json.dumps(self.tags)}**\n"

        log_str = f"{log_str}details:**\n"
        if self.detail_objects:
            for d in self.detail_objects:
                log_str = f"{log_str}{d.log_str}**\n"

        log_str = f"{log_str}_GTM_ACTIVITY_END_"

        return log_str

    def add_detail_object(self, obj: ActivityDetailRecord) -> None:
        """Method to add a detail object

        Args:
            obj(ActivityDetailRecord): detail record to add

        Returns:
            None
        """
        self.detail_objects.append((obj.type.value, obj.show, obj.importance, obj))

    def update_detail_object(self, obj: ActivityDetailRecord, index: int) -> None:
        """Method to update a detail object in place

        Args:
            obj(ActivityDetailRecord): detail record to add
            index(int): index to update

        Returns:
            None
        """
        if index < 0 or index >= len(self.detail_objects):
            raise ValueError("Index out of range when updating detail object")

        self.detail_objects.insert(index, (obj.type.value, obj.show, obj.importance, obj))
