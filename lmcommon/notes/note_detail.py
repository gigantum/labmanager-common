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

class NoteDetailDB():
    """File based representation of key values"""

    def __init__(self, path: str):
        """Constructor

        Args:
            path(str): note detail directory
        """
        self.dirpath = path
        self.curfile = "logfile"

        # TODO need to think about evaluating the currentfile everytime?  or keeping file metadata on it?

    def put(self, value: str) -> str:
        """Put a note into the files and return a key to access it

        Args:
            path(str): Key used to access and identify the object

        Returns:
            note_key(str): key used to access and identify the object
        """
        length = len(value)

        # TODO get a lock for all write I/O
        fh = open(os.path.abspath(os.path.join(self.dirpath,self.curfile)),"ba")
        try:
            # get this file offset
            offset = fh.tell()

            # TODO do something to advance the logfile as needed

            # append the record to the active log
            fh.write(value)

        finally:
            # TODO release the lock
            fh.close()

        return json.dumps([self.curfile, offset, length])

    def get(self, node_key: str) -> str:
        """Return a detailed note.

        Args:
            node_key: json encoded array that contains file_name, offsest, length

        Returns:
            detail_record(str): detail records stored by put
        """
        [ fname, offset, length ] = json.loads(node_key)
        try:
            fh = open(os.path.abspath(os.path.join(self.dirpath,self.curfile)),"br")
            offset = fh.seek(offset)
            retval = fh.read(length)
        finally:
            fh.close()

        return retval
    

