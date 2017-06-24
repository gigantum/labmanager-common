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
from elasticsearch import Elasticsearch
from elasticsearch.client import IndicesClient

from datetime import datetime

# TODO should implement complex searches.  Maybe make the user 
#   construct the query and pass is directly
#
#


class NoteSearch:

    def create (self, labbook_name):
        """Define index for this labbook.  Including mappings."""
        # mapping for labnotes
        # add level as a tag 
        mapping = {
          "mappings": {
            "note": { 
              "properties": { 
                "linkedcommit": { "type": "keyword" },
                "author":       { "type": "text" },
                "message":      { "type": "text" },
                "freetext":     { "type": "text" }, 
                "tags":         { "type": "keyword" }, 
                "timestamp":    { "type": "date", 
                                  "format": "strict_date_optional_time||epoch_millis"
                }
              }
            }
          }
        }

        es = Elasticsearch()
        ic = IndicesClient(es)

        notemap = ic.create(index=labbook_name, body=mapping)


    def delete(self, labbook_name):
        """Define index for this labbook.  Including mappings."""
        es = Elasticsearch()
        ic = IndicesClient(es)
        ic.delete(labbook_name)


    def refresh(self, labbook_name):
        """Refresh the index.  Makes search results available.

            Args:
                labbook_name(str): name of the labbook
            
            Returns:
                None
        """
        es = Elasticsearch()
        ic = IndicesClient(es)
        ic.refresh()
        

    def get (self, labbook_name, noteid ):
        """
            Get a note by id -- equal to the git commit hash

            Args:
                labbook_name(str): name of the labbook
                noteid(str): commit_hash of notes entry
            
            Returns:
                dict
        """
        es = Elasticsearch()
        return es.get(index=labbook_name, id=noteid, doc_type='note')


    def search ( self, labbook_name:str, field: str, terms: str ):
        """Simple search for terms in a field.
            If the field is not given (None), look in all fields.

            Args:
                labbook_name(str): name of the labbook
                field(str): field in which to search
                terms(str): terms to identify in the field
            
            Returns:
                iterable(dict)
        """
        # TODO need to implement None for field option
        es = Elasticsearch()
        query = {"query": {"match": {field : terms}}}
        res = es.search(index=labbook_name, body=query)
        return res
        



    def add (self, labbook_name, noteid, note):
        """
            Add a note to the index.

            Args:
                labbook_name(str): name of the labbook
                noteid(str): commit_hash of notes entry
                note(dict): with some subset of the fields
                    "linkedcommit": { "type": "string" },
                    "author":       { "type": "text" },
                    "message":      { "type": "text" },
                    "freetext":     { "type": "text" }, 
                    "tags":         { "type": "keyword" }, 
                    "timestamp":    { "type": "date"} 
            
            Returns:
                None
        """
        es = Elasticsearch()
        if noteid == None:
            es.index(index=labbook_name, doc_type='note', body=note)
        else:
            es.index(index=labbook_name, id=noteid, doc_type='note', body=note)
        

    def get (self, labbook_name, noteid ):
        """
            Get a note by id -- equal to the git commit hash

            Args:
                labbook_name(str): name of the labbook
                noteid(str): commit_hash of notes entry
            
            Returns:
                dict
        """
        es = Elasticsearch()
        return es.get(index=labbook_name, id=noteid, doc_type='note')


    def search ( self, labbook_name:str, field: str, terms: str ):
        """Simple search for terms in a field.
            If the field is not given (None), look in all fields.

            Args:
                labbook_name(str): name of the labbook
                field(str): field in which to search
                terms(str): terms to identify in the field
            
            Returns:
                iterable(dict)
        """
        # TODO need to implement None for field option
        es = Elasticsearch()
        query = {"query": {"match": {field : terms}}}
        res = es.search(index=labbook_name, body=query)
        return res
        

