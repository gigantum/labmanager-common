import re
import os

from whoosh.index import create_in, open_dir, exists_in    
from whoosh.fields import Schema, TEXT, KEYWORD, DATETIME
from whoosh.qparser import QueryParser 
from datetime import datetime

from git import Commit
from typing import Dict, Union, List, Any, Optional

from lmcommon.activity.records import ActivityRecord, ActivityDetailRecord
from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()

# Right now, we'll only index text and markdown.  We may want to index JSON going forward.
INDEXABLE_MIME_TYPES = ['text/plain','text/markdown']


class ActivitySearch:

    # TODO RB we should probably version this whoosh schema along with activity records.
    # mapping for activity records (schema for search)
    # only store the commit and linked commit
    ar_schema = Schema( \
                        commit=KEYWORD(stored=True), \
                        linked_commit=KEYWORD(stored=True), \
                        name=TEXT, \
                        email=TEXT, \
                        commit_message=TEXT, \
                        linked_commit_message=TEXT, \
                        record_type=KEYWORD, \
                        tags=KEYWORD, \
                        timestamp=DATETIME )


    ad_schema = Schema( \
                        key=KEYWORD(stored=True), \
                        commit=KEYWORD(stored=True), \
                        linked_commit=KEYWORD(stored=True), \
                        record_type=KEYWORD, \
                        tags=KEYWORD, \
                        mimetypes=KEYWORD, \
                        freetext=TEXT, \
                        timestamp=DATETIME )

    def __init__(self, root_dir:str, labbook) -> None:
        """Create a Activity Search object.
            This will load an existing index if it exists on the server.
            Otherwise, it will create an index, initializing the schema,
            for subsequent use in this labbook.

            Args:
                unique_name(str) -- name of the index 

                    We expect that the unique_name will be something like
                        user_owner_labbookname
                    if you give a path (i.e. with /\:) we will replace 
                    those symbols with _.  One should give the same name
                    for every invocation to connect to the same index.
        
            Returns:  None
        """
        self.labbook = labbook

        # remove special characters and delimiters from path name
        self.idx_name = re.sub('[\\\/\:]', '_', re.sub('^/', '', root_dir))
        self.index_dir = os.path.join(self.labbook.labmanager_config.config["git"]["working_directory"], \
                                      self.labbook.labmanager_config.config["whoosh"]["index_dir"])
        self.idxpath = os.path.join(self.index_dir, self.idx_name)

        # Open an existing index
        if exists_in (self.idxpath, indexname="activity"):
            self.aidx = open_dir(self.idxpath, indexname="activity")
            self.didx = open_dir(self.idxpath, indexname="details")

        # create a new index
        else:
            logger.info(f"Creating whoosh indexes in {self.idxpath}")
            if not os.path.exists(self.index_dir):
                os.makedirs(self.index_dir)
            if not os.path.exists(self.idxpath):
                os.mkdir(self.idxpath)

            self.aidx = create_in(self.idxpath, schema=self.ar_schema, indexname="activity")
            self.didx = create_in(self.idxpath, schema=self.ad_schema, indexname="details")
            
    def delete(self):
        logger.info(f"Deleting whoosh indexes {self.idxpath}")
        if exists_in (self.idxpath, indexname="activity"):
            import shutil
            shutil.rmtree(self.idxpath, ignore_errors=True)

    def refresh(self):
        """Optimize the indexes. This is expensive and should only be
            called when building indexes from scratch.  i.e.
            add all documents with commit(merge=False) and 
            then call optimize to compact.  For single updates, we
            use whooshes' merge algorithm.

            Returns:
                None
        """
        logger.info(f"Optimizing whoosh indexes")
        awriter = self.aidx.writer()
        dwriter = self.didx.writer()

        awriter.commit(optimize=True)
        dwriter.commit(optimize=True)

    def search(self, field: str, terms: str):
        """Simple search for terms in a field.
            If the field is not given (None), look in all fields.

            Args:
                field(str): field in which to search
                terms(str): terms to identify in the field
            
            Returns:
                iterable(dict)
        """
        # could check that field is in schema.  Not checking just gives empty results.
        query_parser = QueryParser(field, schema=self.ad_schema)
        query = query_parser.parse(terms)

        with self.aidx.searcher() as dsearch: 
            results = dsearch.search(query)
            ret_list = list()
            for result in results:
                ret_list.append( { 'linked_commit': result['linked_commit'], \
                                   'commit': result['linked_commit'] } )

            return ret_list


    def searchDetail(self, field: str, terms: str):
        """Simple search for terms in a field.
            If the field is not given (None), look in all fields.

            Args:
                field(str): field in which to search
                terms(str): terms to identify in the field
            
            Returns:
                iterable(dict)
        """
        # could check that field is in schema.  Not checking just gives empty results.
        query_parser = QueryParser(field, schema=self.ad_schema)
        query = query_parser.parse(terms)

        with self.didx.searcher() as dsearch: 
            results = dsearch.search(query)
            ret_list = list()
            for result in results:
                ret_list.append( { 'key': result['key'], \
                                   'linked_commit': result['linked_commit'], \
                                   'commit': result['linked_commit'] } )

            return ret_list
            
    def add(self, record: ActivityRecord) -> None:
        """
            Add an ActivityRecord to the search index.
            Configure index writers and calls the low-level method _add_record

            Args:
                record(ActivityRecord)

            Returns:
                None
        """
        # get index writer
        awr = self.aidx.writer()
        # get index detail writer
        dwr = self.didx.writer()
    
        self._add_record(awr, dwr, record)

        dwr.commit()
        awr.commit()

    def batch_add(self, records):
        """
            Add all ActivityRecords in generator to the search index.
            Configure index writers and calls the low-level method _add_record

            Args:
                records(generator of ActivityRecord)

            Returns:
                None
        """
        # get index writer
        awr = self.aidx.writer()
        # get index detail writer
        dwr = self.didx.writer()
    
        # get index searcher/reader
        with self.aidx.searcher() as dsearch: 
            # Build a query for commit
            query_parser = QueryParser("commit", schema=self.ad_schema)
            # for each record
            for record in records: 
                query = query_parser.parse(record.commit)
                # if it's not in index
                if len(dsearch.search(query))==0:
                    logger.debug(f"Adding record {record.commit}")
                    # add it to the index
                    self._add_record(awr, dwr, record)
                else:
                    logger.debug(f"Skipping record {record.commit}")
                 
        dwr.commit()
        awr.commit()

    def _add_record(self, awriter, dwriter, record: ActivityRecord) -> None:
        """
            Low-level method to put an activity record in the index.
            Used by synchronous and asynchronous writers.

            Args:
                awriter -- an open whoosh index writer for activty schema
                dwriter -- an open whoosh index writer for detail schema
                record(ActivityRecord)

            Returns:
                None
        """
        # populate the record with metadata from git log
        # if there's no linked commit, get metadata from current commit.
        if record.linked_commit == 'no-linked-commit':
            commit_record = self.labbook.git.log_entry(record.commit)
            awriter.add_document( commit=record.commit, \
                                  linked_commit=record.linked_commit, \
                                  name=commit_record['author']['name'], \
                                  email=commit_record['author']['email'], \
                                  commit_message=record.message, \
                                  linked_commit_message="",\
                                  record_type=record.type.name, \
                                  tags=record.tags, \
                                  timestamp=commit_record['committed_on'])

            # add details with no linked_commit
            for ob in record.detail_objects:
                self.addDetail(dwriter, record.commit, record.linked_commit, commit_record['committed_on'], ob[3])

        # otherwise used linked-commit and add linked-commit message also
        else:
            linked_commit_record = self.labbook.git.log_entry(record.linked_commit)
            awriter.add_document( commit=record.commit, \
                          linked_commit=record.linked_commit, \
                          name=linked_commit_record['author']['name'], \
                          email=linked_commit_record['author']['email'], \
                          commit_message=record.message, \
                          linked_commit_message=linked_commit_record['message'],\
                          record_type=record.type.name, \
                          tags=record.tags, \
                          timestamp=linked_commit_record['committed_on'])

            # add details with linked_commit
            for ob in record.detail_objects:
                self.addDetail(dwriter, record.commit, record.linked_commit, linked_commit_record['committed_on'], ob[3])

    def addDetail(self, dwriter, commit: Optional[str], linked_commit: Optional[str], timestamp: datetime, record: ActivityDetailRecord) -> None:
        """
            Add a detail record to the index.

            Args:
                dwriter: must have an open dwriter so that this function can be called many times
                            must also commit after call.  see ActivitySeach.add for use.
                commit: connect detail to original activity
                linked_commit: connect detail to activity record
                time_stamp: so we can search by time
                recordid(str): commit_hash of activity entry
                record(dict): with some subset of the fields
                    "properties": { 
                        "type":         { "type": "keyword" },
                        "tags":         { "type": "keyword" }, 
                        "mimetypes":    { "type": "keyword" }, 
                        "freetext":     { "type": "text" }
                    }
            
            Returns:
                None
        """
        mimetypes = list()
        freetext = str()


        # extract mimetypes and freetext
        for mime_type, dataobj in record.data.items():
          mimetypes.append(mime_type)
          if mime_type in INDEXABLE_MIME_TYPES:
            # flatten freetext into uni-str
            freetext = freetext + dataobj + "\n"

        dwriter.add_document( key=record.key, \
                      commit=commit, \
                      linked_commit=linked_commit, \
                      record_type=record.type.name, \
                      tags=record.tags, \
                      mimetypes=mimetypes, \
                      freetext=freetext, \
                      timestamp=timestamp)
