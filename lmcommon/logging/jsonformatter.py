# Copyright (c) 2018 FlashX, LLC
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

from logging import Formatter
import json
import traceback


class JsonFormatter(Formatter):

    def __init__(self):
        super(JsonFormatter, self).__init__()

    def format(self, record):
        exc_info = None
        if record.exc_info:
            exc_info = ''.join(traceback.format_exception(record.exc_info[0], record.exc_info[1], record.exc_info[2]))
        d = {
            'message': record.getMessage(),
            'levelname': record.levelname,
            'filename': record.filename,
            'funcName': record.funcName,
            'name': record.name,
            'created': record.created,
            'module': record.module,
            'process': record.process,
            'processName': record.processName,
            'pathname': record.pathname,
            'exc_text': repr(record.exc_text),
            'exc_info': exc_info,
            'stack_info': repr(record.stack_info),
            'lineno': record.lineno
        }
        return json.dumps(d)
