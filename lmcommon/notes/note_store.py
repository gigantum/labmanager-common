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
import plyvel
import json


class NoteStore(object):
    """
    NoteStore contains the detailed notes records stored through a key/value interface.

    They are stored and accessed by commit hash (str) and are encoded as JSON objects.
    """

    def __init__(self, labbook):
        """ Load the database for the specified labbook """

        # instantiate notes at _root_dir/.gigantum/notes/
        # get the path from the config
        self._entries_path = os.path.join(labbook.root_dir, ".gigantum", "notes", "log")

    def put_entry(self, key: str, value: dict) -> None:
        """
            Put a notes detailed entry into a levelDB.

            Args:
                key(string): commit_hash of notes entry
                value(dict): any JSON serializable dictionary (not interpreted)
            
            Returns:
                None.  Throws an exception.
        """
        # Open outside try (can't close if this fails)
        edb = plyvel.DB(self._entries_path, create_if_missing=True)

        try:
            # level db wants binary
            bkey = key.encode('utf8')
            bvalue = json.dumps(value).encode('utf8')
            edb.put(bkey, bvalue)
        except:
            raise
        finally:
            edb.close()

    def get_entry(self, key: str) -> dict:
        """
            Fetch a notes detailed entry from a levelDB by commit hash
            Args:
                key(string): commit_hash of notes entry

            Returns:
                 dict
        """
        # Open outside try (can't close if this fails)
        edb = plyvel.DB(self._entries_path, create_if_missing=True)

        try:
            bkey = key.encode('utf8')
            bvalue = edb.get(bkey)
            value = json.loads(bvalue.decode('utf8')) 
        except:
            raise

        return value

