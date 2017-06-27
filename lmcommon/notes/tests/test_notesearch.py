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
import pytest
from datetime import datetime

from lmcommon.labbook import LabBook
from lmcommon.notes import NoteSearch


@pytest.fixture()
def test_notesearch():
    """A pytest fixture that creates a ElasticSearch index and deletes it after test"""
    # if previous test fails, you may have left index
    ns = NoteSearch()
    try:
        ns.delete('test_gig_index')
    except:
        pass
    ns.create('test_gig_index')
    yield ns
    ns.delete('test_gig_index')


class TestNoteStore():

    def test_add_and_search(self, test_notesearch):
        """Add a bunch of fields and make sure that search results match."""

        test_notesearch.add('test_gig_index', None, { 
                    'author':'randal burns', 
                    'message': 'foo bar', 
                    'timestamp': datetime.now(), 
                    'freetext' : 'and this bird you cannot',
                    'linkedcommit' : '123abcdef',
                    'tags': ['user','major']})

        test_notesearch.add('test_gig_index', None, { 
                    'author':'randal whitehouse', 
                    'timestamp': datetime.now(), 
                    'message': 'bar moo', 
                    'freetext' : 'whoa whoa whoa whoa waho and this bird',
                    'linkedcommit' : '456ghijkl',
                    'tags': ['user','minor']})

        test_notesearch.add('test_gig_index', None, { 
                    'author':'tyler burns', 
                    'timestamp': datetime.now(), 
                    'message': 'moo wah',
                    'freetext' : 'what song do y\'all wanna hear',
                    'tags': ['auto','major']})

        test_notesearch.add('test_gig_index', None, { 
                    'author':'tyler whitehouse', 
                    'timestamp': datetime.now(), 
                    'message': 'wah foo',
                    'freetext' : 'free bird',
                    'tags': ['auto','minor']})

        test_notesearch.refresh('test_gig_index')

        # 2 notes with foo
        res = test_notesearch.search("test_gig_index","message","foo")
        assert(res['hits']['total'] == 2)

        # 3 notes with message moo or wah
        res = test_notesearch.search("test_gig_index","message","moo wah")
        assert(res['hits']['total'] == 3)

        # 3 notes with message wah or moo
        res = test_notesearch.search("test_gig_index","message","wah moo")
        assert(res['hits']['total'] == 3 )

        # 2 notes with author tyler
        res = test_notesearch.search("test_gig_index","author","tyler")
        assert(res['hits']['total'] == 2 )

        res = test_notesearch.search("test_gig_index","author","whitehouse")
        assert ( res['hits']['total'] == 2 )

        res = test_notesearch.search("test_gig_index","tags","auto")
        assert ( res['hits']['total'] == 2 )

        res = test_notesearch.search("test_gig_index","tags","minor")
        assert ( res['hits']['total'] == 2 )

        res = test_notesearch.search("test_gig_index","freetext","bird")
        assert ( res['hits']['total'] == 3 )

        # text supports compound search
        res = test_notesearch.search("test_gig_index","freetext","[whoa,what]")
        assert ( res['hits']['total'] == 2 )

        # keyword doesn't
        res = test_notesearch.search("test_gig_index","tags","[user,minor]")
        assert ( res['hits']['total'] == 0 )

