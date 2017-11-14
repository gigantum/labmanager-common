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
import re
import json
import base64
from redis import StrictRedis
import redis_lock


class NoteDetailDB():
    """File based representation of key values"""

    def __init__(self, path: str, config) -> None:
        """Constructor

        Args:
            path(str): note detail directory
        """
        self.dirpath = path

        # TODO derived from UUID/machine/something unique
        #       derive in a smart way for merge.
        self.basename = "labbook_notes_log_XX"
        assert(len(self.basename)==20)

        self.config = config

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
                    # this being correct depends upon each checkout being unique
                    # i.e. no way to get the same id when returning to a branch
                    self.latestfnum = 1
        else:
            # no logmeta file, first time open
            with open(self.logmdfname,"w+") as fp:
                self.latestfnum=1
                logmeta = {'basename': self.basename, 'filenumber': 1}
                json.dump(logmeta, fp)

    def _generate_detail_header(self, offset: int, length: int) -> bytes:
        """Helper function to generate a log-sequence header.  Must hold a lock when calling."""
        return b'__g__lsn' + self.latestfnum.to_bytes(4, byteorder='little') \
                                      + offset.to_bytes(4, byteorder='little') \
                                      + length.to_bytes(4, byteorder='little')

    def _parse_detail_header(self, detail_header: bytes) -> (int, int, int):
        """Helper function that returns offset and length from detail header

        Arguments: 
            detail_header: bytes

        Returns: (fnum, offset, length)
            fnum(int): file number in the rotation for this checkout
            offset(int): seek offset for record
            length(int): length of record
        
        """
        if detail_header[0:8] != b'__g__lsn':
            raise ValueError("Invalid log record header")
        else:
            fnum = int.from_bytes(detail_header[8:12],'little') 
            offset= int.from_bytes(detail_header[12:16],'little') 
            length = int.from_bytes(detail_header[16:20],'little') 

        return (fnum, offset, length)

    def _generate_detail_key(self, detail_header: bytes) -> str:
        """Helper function to turn a header in to a key.  Must hold a lock when calling."""
        return self.basename + base64.b64encode(detail_header).decode('utf-8')

    def _parse_detail_key(self, detail_key: str) -> (str, bytes):
        """Helper function to turn a header in to a key.  Must hold a lock when calling.

         Arguments:
            detail_key: key returns from previous entry

         Returns:
            basename(str): name of log file family that contains record
            detail_header(bytes): detail header to be parse for rotation #, offset, and length
        """
        basename = detail_key[0:20]
        detail_header = detail_key[20:]

        return basename, base64.b64decode(detail_header.encode('utf-8'))
        
    def _open_for_append_and_rotate(self):
        """ Return and open file handle.  Rotate the log as we need.
            Can't check the type -> file doesn't work

        Returns: file
        """
        fp = open(os.path.abspath(os.path.join(self.dirpath, self.basename+str(self.latestfnum))), "ba" )

        # rotate file when too big.  Set this at 4 MB override by config file
        # this will write one record after the limit, i.e. it's a soft limit
        sizelimit = self.config.config["logfilesize"] if "logfilesize" in self.config.config else 4000000
        if fp.tell() > sizelimit:
            self.latestfnum = self.latestfnum+1
            with open(self.logmdfname,"w+") as fp2:
                logmeta = {'basename': self.basename, 'filenumber': self.latestfnum}
                json.dump(logmeta, fp2)
            fp.close()
            # call recursively in case need to advance more than one
            return self._open_for_append_and_rotate()
        else:
            return fp
        
    def put(self, value: bytes) -> str:
        """Put a note into the files and return a key to access it

        Args:
            value(bytes): note detail objects

        Returns:
            note_key(str): key used to access and identify the object
        """
        conn = StrictRedis()
        
        # get a lock for all write I/O
        with redis_lock.Lock(conn, self.dirpath):
            fh = self._open_for_append_and_rotate()
            try:
                # get this file offset
                offset = fh.tell()
                length=len(value)

                detail_header = self._generate_detail_header(offset, length)

                # append the record to the active log
                fh.write(detail_header)
                fh.write(value)

            finally:
                fh.close()

            detail_key = self._generate_detail_key(detail_header)

        # unlock
        print(detail_key,type(detail_key))
        return detail_key

    def get(self, detail_key: bytes) -> bytes:
        """Return a detailed note.

        Args:
            detail_key: json encoded array that contains file_name, offsest, length

        Returns:
            detail_record(str): detail records stored by put
        """
        basename, detail_header = self._parse_detail_key(detail_key)
        fnum, offset, length = self._parse_detail_header(detail_header)
     
        with open(os.path.abspath(os.path.join(self.dirpath, basename+str(fnum))),"br") as fh:
            fh.seek(offset)
            retval = fh.read(length+20)   # plus the header length

        return retval
    

