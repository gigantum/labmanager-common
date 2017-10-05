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
import abc
from typing import (Any, Dict, List)

from lmcommon.notes.note_store import NoteLogLevel, NoteDetailObject


class StopProcessingException(Exception):
    """Custom exception to stop activity processing pipeline and bail out from activity process"""
    pass


class ActivityNote(object):
    """Class to store an activity note data"""

    def __init__(self, message: str = None, log_level: NoteLogLevel = None, tags: List[str] = None,
                 free_text: str = None, objects: List[NoteDetailObject] = None) -> None:
        # Set attributes
        self.message = message
        self.log_level = log_level
        self.tags = tags
        self.free_text = free_text
        self.objects = objects


class ActivityProcessor(metaclass=abc.ABCMeta):
    """Class to process activity and return content for a notes record"""

    def process(self, result_obj: ActivityNote, code: Dict[str, Any], result: Dict[str, Any],
                metadata: Dict[str, Any]) -> ActivityNote:
        """Method to update a result object based on code and result data

        Args:
            result_obj(ActivityNote): An object containing the note
            code(dict): A dict containing data specific to the dev env containing code that was executed
            result(dict): A dict containing data specific to the dev env containing the result of code execution
            metadata(str): A dictionary containing Dev Env specific or other developer defined data

        Returns:
            ActivityNote
        """
        raise NotImplemented
