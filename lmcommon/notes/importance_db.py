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
import dbm.gnu as gdbm


class ImportanceObject():
    """Object/structure that describes importance/visibility of a detail record"""
    def __init__(importance: int, weight: float=0.0, visible: bool=True) -> None:
        self.importance = importance
        self.weight = weight
        self.visibile = visible

class ImportanceDB():
    """Key value store (in a file) to keep importance information for UI."""

    def __init__(self, path: str) -> None:
        """Constructor

        Args:
            path(str): activity directory
        """
        # TODO derived from UUID/machine/something unique
        #       derive in a smart way for merge.
        self.basename= "labbook_importance_db_"

        # get the latest log on open
        self.dbfilename = os.path.abspath(os.path.join(path,self.basename))

        # create the importance database or make sure it's there
        with gdbm.open(self.dbfilename,"c"):
            pass

    def addList(hexsha: str, importance: List(ImportanceObject)) -> None:
        NotImplemented

    def add(hexsha: str, importance: ImportanceObject) -> None:
        """Add an importance structure in the database for the commit at hexsha.
            For adding importance items one at a time.
    
        Args:
            hexsha(str): hexsha from the associated git commit
            importance(Importancestruct): single object to add to hexsha

        """
        with gdbm.open(self.dbfilename,"w") as idb:
            # access old list, add record, store new list
            try:
                implist = idb.get(hexsha)
            except E
            implist.append(importance)
            idb.store(hexsha,implist)

    def items(commitsha: str) -> ImportanceStruct:
        """Generator of importance items for a hexsha"""
        with gdbm.open(self.dbfilename,"r"):
            implist = idb.get()
            for importance in implist:
                yield implist
