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

        # TODO derived from UUID/machine/something unique
        #       derive in a smart way for merge.
        self.basename = "labbook_notes_log_"

        # get the latest log on open
        self.logmdfname = os.path.abspath(os.path.join(path,'.logfilename'))
        if os.path.exists(self.logmdfname):
            # get most recently used file
            with open(self.logmdfname,"r") as fp: 
                logmeta = json.load(fp) 
                # opening an existing log
                if logmeta['basename']==self.basename:
                    self.latestfnum = logmeta['filenumber']
                # logging on a new node/system
                else:
                    self.latestfnum = 1
        
        else:
            # no logmeta file, first time open
            with open(self.logmdfname,"w+") as fp:
                self.latestfnum=1
                logmeta = {'basename': self.basename, 'filenumber': 1}
                json.dump(logmeta, fp)

    def _open_for_append_and_rotate(self):
        """ Return and open file handle.  Rotate the log as we need.
            Can't check the type -> file doesn't work

        Returns: file
        """
        fp = open(os.path.abspath(os.path.join(self.dirpath, self.basename+str(self.latestfnum))), "ba" )

        # rotate file when too big TODO get from settings
        # this will write one record after the limit, i.e. it's a soft limit
        if fp.tell() > 10000:
            self.latestfnum = self.latestfnum+1
            with open(self.logmdfname,"w+") as fp2:
                logmeta = {'basename': self.basename, 'filenumber': self.latestfnum}
                json.dump(logmeta, fp2)
            fp.close()
            # call recursively in case need to advance more than one
            return self._open_for_append_and_rotate()
        else:
            return fp
        
    def put(self, value: str) -> bytes:
        """Put a note into the files and return a key to access it

        Args:
            value(str): note detail objects

        Returns:
            note_key(str): key used to access and identify the object
        """
        
        # TODO get a lock for all write I/O
        fh = self._open_for_append_and_rotate()
        try:
            # get this file offset
            offset = fh.tell()
            length=len(value)

            # header in the log and key are the same byte string
            detail_header = b'_glm_lsn' + (self.latestfnum).to_bytes(4, byteorder='little') \
                                        + (offset).to_bytes(4, byteorder='little') \
                                        + (length).to_bytes(4, byteorder='little')

            # append the record to the active log
            fh.write(detail_header)
            fh.write(value)

        finally:
            # TODO release the lock
            fh.close()

        return detail_header

    def get(self, node_key: str) -> str:
        """Return a detailed note.

        Args:
            node_key: json encoded array that contains file_name, offsest, length

        Returns:
            detail_record(str): detail records stored by put
        """
        if node_key[0:8] != b'_glm_lsn':
            raise ValueError("Invalid log record header")
        else:
            fnum = int.from_bytes(node_key[8:12],'little') 
            offset= int.from_bytes(node_key[12:16],'little') 
            length = int.from_bytes(node_key[16:20],'little') 
     
        with open(os.path.abspath(os.path.join(self.dirpath, self.basename+str(fnum))),"r") as fh:
            offset = fh.seek(offset)
            retval = fh.read(length+20)   # TODO RB plus the header length

        return retval
    

