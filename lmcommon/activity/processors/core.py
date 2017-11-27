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
from typing import (Any, Dict)

from lmcommon.activity.processors.processor import ActivityProcessor
from lmcommon.activity import ActivityRecord, ActivityDetailType


class ActivityShowBasicProcessor(ActivityProcessor):
    """Class to simply hide an activity record if it doesn't have any detail records that are set to show=True"""

    def process(self, result_obj: ActivityRecord, code: Dict[str, Any], result: Dict[str, Any], status: Dict[str, Any],
                metadata: Dict[str, Any]) -> ActivityRecord:
        """Method to update a result object based on code and result data

        Args:
            result_obj(ActivityNote): An object containing the note
            code(dict): A dict containing data specific to the dev env containing code that was executed
            result(dict): A dict containing data specific to the dev env containing the result of code execution
            status(dict): A dict containing the result of git status from gitlib
            metadata(str): A dictionary containing Dev Env specific or other developer defined data

        Returns:
            ActivityNote
        """
        result_obj.show = False
        for detail in result_obj.detail_objects:
            # Don't take CODE_EXECUTED details into account, as we always set those to show
            if detail[1] == ActivityDetailType.CODE_EXECUTED.value:
                continue

            if detail[0]:
                result_obj.show = True
                break

        return result_obj
