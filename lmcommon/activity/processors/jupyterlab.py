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
from typing import (Any, Dict, List)

from lmcommon.logging import LMLogger
from lmcommon.activity.processors.processor import ActivityProcessor, ExecutionData
from lmcommon.activity import ActivityRecord, ActivityDetailType, ActivityDetailRecord, ActivityAction
from lmcommon.labbook import LabBook

logger = LMLogger.get_logger()


class JupyterLabCodeProcessor(ActivityProcessor):
    """Class to process code records into activity detail records"""

    def process(self, result_obj: ActivityRecord, data: List[ExecutionData],
                status: Dict[str, Any], metadata: Dict[str, Any]) -> ActivityRecord:
        """Method to update a result object based on code and result data

        Args:
            result_obj(ActivityNote): An object containing the note
            data(list): A list of ExecutionData instances containing the data for this record
            status(dict): A dict containing the result of git status from gitlib
            metadata(str): A dictionary containing Dev Env specific or other developer defined data

        Returns:
            ActivityRecord
        """
        # If there was some code, assume a cell was executed
        result_cnt = 0
        for cell_cnt, cell in enumerate(data):
            for result_entry in reversed(cell.code):
                if result_entry.get('code'):
                    # Create detail record to capture executed code
                    adr_code = ActivityDetailRecord(ActivityDetailType.CODE_EXECUTED, show=False,
                                                    action=ActivityAction.EXECUTE,
                                                    importance=max(255-result_cnt, 0))

                    adr_code.add_value('text/markdown', f"```\n{result_entry.get('code')}\n```")
                    adr_code.tags = cell.tags

                    result_obj.add_detail_object(adr_code)

                    result_cnt += 1

        # Set Activity Record Message
        cell_str = f"{cell_cnt} cells" if cell_cnt > 1 else "cell"
        result_obj.message = f"Executed {cell_str} in notebook {metadata['path']}"

        return result_obj


class JupyterLabFileChangeProcessor(ActivityProcessor):
    """Class to process file changes based on git-status into activity detail records"""

    def process(self, result_obj: ActivityRecord, data: List[ExecutionData],
                status: Dict[str, Any], metadata: Dict[str, Any]) -> ActivityRecord:
        """Method to update a result object based on code and result data

        Args:
            result_obj(ActivityNote): An object containing the note
            data(list): A list of ExecutionData instances containing the data for this record
            status(dict): A dict containing the result of git status from gitlib
            metadata(str): A dictionary containing Dev Env specific or other developer defined data

        Returns:
            ActivityRecord
        """
        for cnt, filename in enumerate(status['untracked']):
            # skip any file in .git or .gigantum dirs
            if ".git" in filename or ".gigantum" in filename:
                continue

            activity_type, activity_detail_type, section = LabBook.infer_section_from_relative_path(filename)

            adr = ActivityDetailRecord(activity_detail_type, show=False, importance=max(255-cnt, 0),
                                       action=ActivityAction.CREATE)
            if section == "LabBook Root":
                msg = f"Created new file `{filename}` in the LabBook Root."
                msg = f"{msg}Note, it is best practice to use the Code, Input, and Output sections exclusively."
            else:
                msg = f"Created new {section} file `{filename}`"
            adr.add_value('text/markdown', msg)
            result_obj.add_detail_object(adr)

        cnt = 0
        for filename, change in status['unstaged']:
            # skip any file in .git or .gigantum dirs
            if ".git" in filename or ".gigantum" in filename:
                continue

            activity_type, activity_detail_type, section = LabBook.infer_section_from_relative_path(filename)

            if change == "deleted":
                action = ActivityAction.DELETE
            elif change == "added":
                action = ActivityAction.CREATE
            elif change == "modified":
                action = ActivityAction.EDIT
            elif change == "renamed":
                action = ActivityAction.EDIT
            else:
                action = ActivityAction.NOACTION

            adr = ActivityDetailRecord(activity_detail_type, show=False, importance=max(255-cnt, 0), action=action)
            adr.add_value('text/markdown', f"{change[0].upper() + change[1:]} {section} file `{filename}`")
            result_obj.add_detail_object(adr)
            cnt += 1

        return result_obj


class JupyterLabPlaintextProcessor(ActivityProcessor):
    """Class to process plaintext result entries into activity detail records"""

    def process(self, result_obj: ActivityRecord, data: List[ExecutionData],
                status: Dict[str, Any], metadata: Dict[str, Any]) -> ActivityRecord:
        """Method to update a result object based on code and result data

        Args:
            result_obj(ActivityNote): An object containing the note
            data(list): A list of ExecutionData instances containing the data for this record
            status(dict): A dict containing the result of git status from gitlib
            metadata(str): A dictionary containing Dev Env specific or other developer defined data

        Returns:
            ActivityNote
        """
        # Only store up to 64kB of plain text result data (if the user printed a TON don't save it all)
        truncate_at = 64 * 1000
        max_show_len = 280

        result_cnt = 0
        for cell in data:
            for result_entry in reversed(cell.result):
                if 'metadata' in result_entry:
                    if 'source' in result_entry['metadata']:
                        if result_entry['metadata']['source'] == "display_data":
                            # Don't save plain-text representations of displayed data by default.
                            continue

                if 'data' in result_entry:
                    if 'text/plain' in result_entry['data']:
                        text_data = result_entry['data']['text/plain']

                        if len(text_data) > 0:
                            adr = ActivityDetailRecord(ActivityDetailType.RESULT,
                                                       show=True if len(text_data) < max_show_len else False,
                                                       action=ActivityAction.CREATE,
                                                       importance=max(255-result_cnt-100, 0))

                            if len(text_data) <= truncate_at:
                                adr.add_value("text/plain", text_data)
                            else:
                                adr.add_value("text/plain", text_data[:truncate_at] + " ...\n\n <result truncated>")

                            # Set cell data to tag
                            adr.tags = cell.tags
                            result_obj.add_detail_object(adr)

                            result_cnt += 1

        return result_obj


class JupyterLabImageExtractorProcessor(ActivityProcessor):
    """Class to perform image extraction for JupyterLab activity"""

    def process(self, result_obj: ActivityRecord, data: List[ExecutionData],
                status: Dict[str, Any], metadata: Dict[str, Any]) -> ActivityRecord:
        """Method to update a result object based on code and result data

        Args:
            result_obj(ActivityNote): An object containing the note
            data(list): A list of ExecutionData instances containing the data for this record
            status(dict): A dict containing the result of git status from gitlib
            metadata(str): A dictionary containing Dev Env specific or other developer defined data

        Returns:
            ActivityNote
        """
        supported_image_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/bmp']

        # If a supported image exists in the result, grab it and create a detail record
        result_cnt = 0
        for cell in data:
            for result_entry in reversed(cell.result):
                if 'data' in result_entry:
                    for mime_type in result_entry['data']:
                        if mime_type in supported_image_types:
                            # You got an image
                            adr_img = ActivityDetailRecord(ActivityDetailType.RESULT, show=True,
                                                           action=ActivityAction.CREATE,
                                                           importance=max(255-result_cnt, 0))

                            adr_img.add_value(mime_type, result_entry['data'][mime_type])

                            adr_img.tags = cell.tags
                            result_obj.add_detail_object(adr_img)

                            # Set Activity Record Message
                            result_obj.message = "Executed cell in notebook {} and generated a result".format(
                                metadata['path'])

                            result_cnt += 1

        return result_obj
