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

from lmcommon.logging import LMLogger

from lmcommon.activity.processors.processor import ActivityProcessor, StopProcessingException
from lmcommon.activity import ActivityRecord, ActivityType, ActivityDetailType, ActivityDetailRecord
from lmcommon.labbook import LabBook


logger = LMLogger.get_logger()


class BasicJupyterLabProcessor(ActivityProcessor):
    """Class to perform baseline processing for JupyterLab activity"""

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
        # If there was some code, assume a cell was executed
        if code:
            if code["code"]:
                # Create detail record to capture executed code
                adr_code = ActivityDetailRecord(ActivityDetailType.CODE_EXECUTED, show=True, importance=128)

                # TODO: Use kernel info to get the language and provide a text/html type that is styled
                adr_code.add_value('text/plain', code['code'])
                adr_code.add_value('text/markdown', f"```{code['code']}```")
                result_obj.add_detail_object(adr_code)

                # There shouldn't be anything staged yet so log a warning if that happens
                if len(status['staged']) > 0:
                    logger.warning("{} staged items found while processing activity. Nothing should be staged yet!")

                # Create detail records for file changes
                cnt = 0
                for filename in status['untracked']:
                    activity_type, activity_detail_type, section = LabBook.infer_section_from_relative_path(filename)
                    if activity_type == ActivityType.INPUT_DATA or activity_type == ActivityType.OUTPUT_DATA:
                        show = True
                    else:
                        show = False
                    adr = ActivityDetailRecord(activity_detail_type, show=show, importance=min(100+cnt, 255))
                    adr.add_value('text/plain', f"Created new {section} file {filename}")
                    adr.add_value('text/markdown', f"Created new {section} file `{filename}`")
                    result_obj.add_detail_object(adr)
                    cnt += 1

                cnt = 0
                for filename, change in status['unstaged']:
                    activity_type, activity_detail_type, section = LabBook.infer_section_from_relative_path(filename)
                    if activity_type == ActivityType.INPUT_DATA or activity_type == ActivityType.OUTPUT_DATA:
                        show = True
                    else:
                        show = False
                    adr = ActivityDetailRecord(activity_detail_type, show=show, importance=min(cnt, 255))
                    adr.add_value('text/plain', f"{change[0].upper() + change[1:]} {section} file {filename}")
                    adr.add_value('text/markdown', f"{change[0].upper() + change[1:]} {section} file `{filename}`")
                    result_obj.add_detail_object(adr)
                    cnt += 1

                # Create detail record for any printed/plain text result
                if result:
                    # Only store up to 4MB of result data (if the user printed a TON don't save it all)
                    truncate_at = 1000 * 4000
                    if len(result['data']["text/plain"]) > 0:
                        adr = ActivityDetailRecord(ActivityDetailType.RESULT, show=True, importance=200)

                        if len(result['data']["text/plain"]) <= truncate_at:
                            adr.add_value("text/plain", result['data']["text/plain"])
                        else:
                            adr.add_value("text/plain",
                                          result['data']["text/plain"][:truncate_at] + " ...\n\n <result truncated>")

                        result_obj.add_detail_object(adr)

                # Set Activity Record Message
                result_obj.message = "Executed cell in notebook {}".format(metadata['path'])

                return result_obj
            else:
                logger.info("Processed activity with no code executed")
                raise StopProcessingException("No code executed. Nothing to process")
        else:
            logger.info("Processed activity with no code executed")
            raise StopProcessingException("No code executed. Nothing to process")

