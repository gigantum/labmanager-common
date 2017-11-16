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
import tempfile
import os
import uuid
import shutil
import json

from lmcommon.fixtures import mock_labbook


class TestLabBookFavorites(object):
    def test_invalid_subdir(self, mock_labbook):
        """Test creating favorite in an invalid subdir"""
        with pytest.raises(ValueError):
            mock_labbook[2].create_favorite("blah", "test/file.file")

    def test_invalid_target(self, mock_labbook):
        """Test creating favorite for an invalid target file"""
        with pytest.raises(ValueError):
            mock_labbook[2].create_favorite("code", "asdfasd")

        with open(os.path.join(mock_labbook[1], 'code', 'test.txt'), 'wt') as test_file:
            test_file.write("blah")

        with pytest.raises(ValueError):
            mock_labbook[2].create_favorite("code", "test.txt", is_dir=True)

    def test_favorite_file(self, mock_labbook):
        """Test creating favorite for a file"""
        with open(os.path.join(mock_labbook[1], 'code', 'test.txt'), 'wt') as test_file:
            test_file.write("blah")

        favorites_dir = os.path.join(mock_labbook[1], '.gigantum', 'favorites')
        assert os.path.exists(favorites_dir) is False
        assert os.path.isdir(favorites_dir) is False
        assert os.path.exists(os.path.join(favorites_dir, 'code.json')) is False
        assert os.path.isfile(os.path.join(favorites_dir, 'code.json')) is False

        result = mock_labbook[2].create_favorite("code", "test.txt", description="My file with stuff")

        assert os.path.exists(favorites_dir) is True
        assert os.path.isdir(favorites_dir) is True
        assert os.path.exists(os.path.join(favorites_dir, 'code.json')) is True
        assert os.path.isfile(os.path.join(favorites_dir, 'code.json')) is True

        with open(os.path.join(favorites_dir, 'code.json'), 'rt') as ff:
            data = json.load(ff)

        assert len(data) == 1
        assert data[0]['key'] == "code/test.txt"
        assert data[0]['description'] == "My file with stuff"
        assert data[0]['is_dir'] is False
        assert data[0]['index'] == 0
        assert result['key'] == "code/test.txt"
        assert result['description'] == "My file with stuff"
        assert result['is_dir'] is False
        assert result['index'] == 0

    def test_duplicate_favorite_file(self, mock_labbook):
        """Test creating favorite for a file twice"""
        with open(os.path.join(mock_labbook[1], 'code', 'test.txt'), 'wt') as test_file:
            test_file.write("blah")

        favorites_dir = os.path.join(mock_labbook[1], '.gigantum', 'favorites')
        assert os.path.exists(favorites_dir) is False
        assert os.path.isdir(favorites_dir) is False
        assert os.path.exists(os.path.join(favorites_dir, 'code.json')) is False
        assert os.path.isfile(os.path.join(favorites_dir, 'code.json')) is False

        mock_labbook[2].create_favorite("code", "test.txt", description="My file with stuff")

        with pytest.raises(ValueError):
            mock_labbook[2].create_favorite("code", "test.txt", description="My file with stuff")

    def test_append_to_favorite_file(self, mock_labbook):
        """Test creating two favorites for a file"""
        with open(os.path.join(mock_labbook[1], 'code', 'test.txt'), 'wt') as test_file:
            test_file.write("blah")
        with open(os.path.join(mock_labbook[1], 'code', 'test2.txt'), 'wt') as test_file:
            test_file.write("blah2")

        mock_labbook[2].create_favorite("code", "test.txt", description="My file with stuff")
        result = mock_labbook[2].create_favorite("code", "test2.txt", description="My file with stuff 2")

        favorites_dir = os.path.join(mock_labbook[1], '.gigantum', 'favorites')
        assert os.path.exists(favorites_dir) is True
        assert os.path.isdir(favorites_dir) is True
        assert os.path.exists(os.path.join(favorites_dir, 'code.json')) is True
        assert os.path.isfile(os.path.join(favorites_dir, 'code.json')) is True

        with open(os.path.join(favorites_dir, 'code.json'), 'rt') as ff:
            data = json.load(ff)

        assert len(data) == 2
        assert data[0]['key'] == "code/test.txt"
        assert data[0]['description'] == "My file with stuff"
        assert data[0]['is_dir'] is False
        assert data[0]['index'] == 0
        assert data[1]['key'] == "code/test2.txt"
        assert data[1]['description'] == "My file with stuff 2"
        assert data[1]['is_dir'] is False
        assert data[1]['index'] == 1
        assert result['key'] == "code/test2.txt"
        assert result['description'] == "My file with stuff 2"
        assert result['is_dir'] is False
        assert result['index'] == 1

    def test_insert_favorite_file(self, mock_labbook):
        """Test creating two favorites for a file"""
        with open(os.path.join(mock_labbook[1], 'code', 'test1.txt'), 'wt') as test_file:
            test_file.write("blah1")
        with open(os.path.join(mock_labbook[1], 'code', 'test2.txt'), 'wt') as test_file:
            test_file.write("blah2")
        with open(os.path.join(mock_labbook[1], 'code', 'test3.txt'), 'wt') as test_file:
            test_file.write("blah3")

        mock_labbook[2].create_favorite("code", "test1.txt", description="My file with stuff 1")
        mock_labbook[2].create_favorite("code", "test2.txt", description="My file with stuff 2")

        favorites_dir = os.path.join(mock_labbook[1], '.gigantum', 'favorites')
        with open(os.path.join(favorites_dir, 'code.json'), 'rt') as ff:
            data = json.load(ff)

        assert len(data) == 2
        assert data[0]['key'] == "code/test1.txt"
        assert data[0]['description'] == "My file with stuff 1"
        assert data[0]['is_dir'] is False
        assert data[0]['index'] == 0
        assert data[1]['key'] == "code/test2.txt"
        assert data[1]['description'] == "My file with stuff 2"
        assert data[1]['is_dir'] is False
        assert data[1]['index'] == 1

        # Do an insert at invalid position
        with pytest.raises(ValueError):
            mock_labbook[2].create_favorite("code", "test3.txt", position=1000, description="My file with stuff 3")
        with pytest.raises(ValueError):
            mock_labbook[2].create_favorite("code", "test3.txt", position=-1, description="My file with stuff 3")

        # Do an insert at position 1
        result = mock_labbook[2].create_favorite("code", "test3.txt", position=1, description="My file with stuff 3")

        with open(os.path.join(favorites_dir, 'code.json'), 'rt') as ff:
            data = json.load(ff)

        assert len(data) == 3
        assert data[0]['key'] == "code/test1.txt"
        assert data[0]['description'] == "My file with stuff 1"
        assert data[0]['is_dir'] is False
        assert data[0]['index'] == 0
        assert data[1]['key'] == "code/test3.txt"
        assert data[1]['description'] == "My file with stuff 3"
        assert data[1]['is_dir'] is False
        assert data[1]['index'] == 1
        assert result['key'] == "code/test3.txt"
        assert result['description'] == "My file with stuff 3"
        assert result['is_dir'] is False
        assert result['index'] == 1
        assert data[2]['key'] == "code/test2.txt"
        assert data[2]['description'] == "My file with stuff 2"
        assert data[2]['is_dir'] is False
        assert data[2]['index'] == 2

    def test_favorite_dir(self, mock_labbook):
        """Test creating a favorite directory"""
        os.makedirs(os.path.join(mock_labbook[1], 'code', 'fav'))
        with open(os.path.join(mock_labbook[1], 'code', 'fav', 'test1.txt'), 'wt') as test_file:
            test_file.write("blah1")

        with pytest.raises(ValueError):
            mock_labbook[2].create_favorite("code", "fav/", description="Dir with stuff")

        mock_labbook[2].create_favorite("code", "fav/", description="Dir with stuff", is_dir=True)

        favorites_dir = os.path.join(mock_labbook[1], '.gigantum', 'favorites')
        with open(os.path.join(favorites_dir, 'code.json'), 'rt') as ff:
            data = json.load(ff)

        assert len(data) == 1
        assert data[0]['key'] == "code/fav/"
        assert data[0]['description'] == "Dir with stuff"
        assert data[0]['is_dir'] is True
        assert data[0]['index'] == 0

    def test_favorite_all_subdirs(self, mock_labbook):
        """Test creating favorites for each subdir type that is supported"""
        with open(os.path.join(mock_labbook[1], 'code', 'test1.txt'), 'wt') as test_file:
            test_file.write("blah1")
        with open(os.path.join(mock_labbook[1], 'input', 'test2.txt'), 'wt') as test_file:
            test_file.write("blah2")
        with open(os.path.join(mock_labbook[1], 'output', 'test3.txt'), 'wt') as test_file:
            test_file.write("blah3")

        mock_labbook[2].create_favorite("code", "test1.txt", description="My file with stuff 1")
        mock_labbook[2].create_favorite("input", "test2.txt", description="My file with stuff 2")
        mock_labbook[2].create_favorite("output", "test3.txt", description="My file with stuff 3")

        favorites_dir = os.path.join(mock_labbook[1], '.gigantum', 'favorites')
        assert os.path.exists(os.path.join(favorites_dir, 'code.json')) is True
        assert os.path.exists(os.path.join(favorites_dir, 'input.json')) is True
        assert os.path.exists(os.path.join(favorites_dir, 'output.json')) is True

        with open(os.path.join(favorites_dir, 'code.json'), 'rt') as ff:
            data = json.load(ff)
        assert len(data) == 1
        assert data[0]['key'] == "code/test1.txt"
        assert data[0]['description'] == "My file with stuff 1"
        assert data[0]['is_dir'] is False
        assert data[0]['index'] == 0

        with open(os.path.join(favorites_dir, 'input.json'), 'rt') as ff:
            data = json.load(ff)
        assert len(data) == 1
        assert data[0]['key'] == "input/test2.txt"
        assert data[0]['description'] == "My file with stuff 2"
        assert data[0]['is_dir'] is False
        assert data[0]['index'] == 0

        with open(os.path.join(favorites_dir, 'output.json'), 'rt') as ff:
            data = json.load(ff)
        assert len(data) == 1
        assert data[0]['key'] == "output/test3.txt"
        assert data[0]['description'] == "My file with stuff 3"
        assert data[0]['is_dir'] is False
        assert data[0]['index'] == 0

    def test_remove_favorite_errors(self, mock_labbook):
        """Test errors when removing"""
        with open(os.path.join(mock_labbook[1], 'code', 'test.txt'), 'wt') as test_file:
            test_file.write("blah")

        with pytest.raises(ValueError):
            mock_labbook[2].remove_favorite('code', 0)

        # Add a favorite
        mock_labbook[2].create_favorite("code", "test.txt", description="My file with stuff")

        with pytest.raises(ValueError):
            mock_labbook[2].remove_favorite('code', 1000)
        with pytest.raises(ValueError):
            mock_labbook[2].remove_favorite('code', -1)
        with pytest.raises(ValueError):
            mock_labbook[2].remove_favorite('asdfasdf', 0)

    def test_remove_favorite_file(self, mock_labbook):
        """Test removing a favorites file"""
        with open(os.path.join(mock_labbook[1], 'code', 'test.txt'), 'wt') as test_file:
            test_file.write("blah")
        with open(os.path.join(mock_labbook[1], 'code', 'test2.txt'), 'wt') as test_file:
            test_file.write("blah2")

        mock_labbook[2].create_favorite("code", "test.txt", description="My file with stuff")
        mock_labbook[2].create_favorite("code", "test2.txt", description="My file with stuff 2")

        favorites_dir = os.path.join(mock_labbook[1], '.gigantum', 'favorites')

        mock_labbook[2].remove_favorite("code", 0)

        with open(os.path.join(favorites_dir, 'code.json'), 'rt') as ff:
            data = json.load(ff)

        assert len(data) == 1
        assert data[0]['key'] == "code/test2.txt"
        assert data[0]['description'] == "My file with stuff 2"
        assert data[0]['is_dir'] is False
        assert data[0]['index'] == 0

    def test_get_favorites(self, mock_labbook):
        """Test getting favorites"""
        with open(os.path.join(mock_labbook[1], 'code', 'test1.txt'), 'wt') as test_file:
            test_file.write("blah1")
        with open(os.path.join(mock_labbook[1], 'code', 'test2.txt'), 'wt') as test_file:
            test_file.write("blah2")
        os.makedirs(os.path.join(mock_labbook[1], 'code', 'tester'))

        mock_labbook[2].create_favorite("code", "test1.txt", description="My file with stuff 1")
        mock_labbook[2].create_favorite("code", "test2.txt", description="My file with stuff 2")
        mock_labbook[2].create_favorite("code", "tester/", is_dir=True, description="My test dir")

        with pytest.raises(ValueError):
            mock_labbook[2].get_favorites('asdfadsf')

        data = mock_labbook[2].get_favorites('code')
        assert len(data) == 3
        assert data[0]['key'] == "code/test1.txt"
        assert data[0]['description'] == "My file with stuff 1"
        assert data[0]['is_dir'] is False
        assert data[0]['index'] == 0
        assert data[1]['key'] == "code/test2.txt"
        assert data[1]['description'] == "My file with stuff 2"
        assert data[1]['is_dir'] is False
        assert data[1]['index'] == 1
        assert data[2]['key'] == "code/tester/"
        assert data[2]['description'] == "My test dir"
        assert data[2]['is_dir'] is True
        assert data[2]['index'] == 2

    def test_update_description(self, mock_labbook):
        """Test updating a description"""
        with open(os.path.join(mock_labbook[1], 'code', 'test1.txt'), 'wt') as test_file:
            test_file.write("blah1")

        # Expect error since favorite doesn't exist yet
        with pytest.raises(ValueError):
            mock_labbook[2].update_favorite('code', 0, new_description="UPDATED")

        # Expect error since `codasdfasdfe` isn't a valid labbook section
        with pytest.raises(ValueError):
            mock_labbook[2].update_favorite('codasdfasdfe', 0, new_description="UPDATED")

        # Create favorite
        mock_labbook[2].create_favorite("code", "test1.txt", description="My fav thingy")

        # Expect errors due to index values
        with pytest.raises(ValueError):
            mock_labbook[2].update_favorite('code', 1, new_description="UPDATED")

        with pytest.raises(ValueError):
            mock_labbook[2].update_favorite('code', -1, new_description="UPDATED")

        fav = mock_labbook[2].update_favorite('code', 0, new_description="UPDATED")
        assert fav['key'] == "code/test1.txt"
        assert fav['description'] == "UPDATED"
        assert fav['is_dir'] is False

        data = mock_labbook[2].get_favorites('code')
        assert len(data) == 1
        assert data[0]['key'] == "code/test1.txt"
        assert data[0]['description'] == "UPDATED"
        assert data[0]['is_dir'] is False
        assert data[0]['index'] == 0

    def test_update_smaller_index_and_description(self, mock_labbook):
        """Test updating a description and index"""
        with open(os.path.join(mock_labbook[1], 'code', 'test1.txt'), 'wt') as test_file:
            test_file.write("blah1")
        with open(os.path.join(mock_labbook[1], 'code', 'test2.txt'), 'wt') as test_file:
            test_file.write("blah2")
        with open(os.path.join(mock_labbook[1], 'code', 'test3.txt'), 'wt') as test_file:
            test_file.write("blah3")
        os.makedirs(os.path.join(mock_labbook[1], 'code', 'tester'))

        mock_labbook[2].create_favorite("code", "test1.txt", description="My file with stuff 1")
        mock_labbook[2].create_favorite("code", "test2.txt", description="My file with stuff 2")
        mock_labbook[2].create_favorite("code", "test3.txt", description="My file with stuff 3")
        mock_labbook[2].create_favorite("code", "tester/", is_dir=True, description="My test dir")

        data = mock_labbook[2].get_favorites('code')
        assert len(data) == 4
        assert data[0]['key'] == "code/test1.txt"
        assert data[0]['description'] == "My file with stuff 1"
        assert data[0]['is_dir'] is False
        assert data[0]['index'] == 0
        assert data[1]['key'] == "code/test2.txt"
        assert data[1]['description'] == "My file with stuff 2"
        assert data[1]['is_dir'] is False
        assert data[1]['index'] == 1
        assert data[2]['key'] == "code/test3.txt"
        assert data[2]['description'] == "My file with stuff 3"
        assert data[2]['is_dir'] is False
        assert data[2]['index'] == 2
        assert data[3]['key'] == "code/tester/"
        assert data[3]['description'] == "My test dir"
        assert data[3]['is_dir'] is True
        assert data[3]['index'] == 3

        fav = mock_labbook[2].update_favorite('code', 2, new_description="UPDATED", new_index=1)
        assert fav['key'] == "code/test3.txt"
        assert fav['description'] == "UPDATED"
        assert fav['is_dir'] is False
        assert fav['index'] == 1

        data = mock_labbook[2].get_favorites('code')
        assert len(data) == 4
        assert data[0]['key'] == "code/test1.txt"
        assert data[0]['description'] == "My file with stuff 1"
        assert data[0]['is_dir'] is False
        assert data[0]['index'] == 0
        assert data[1]['key'] == "code/test3.txt"
        assert data[1]['description'] == "UPDATED"
        assert data[1]['is_dir'] is False
        assert data[1]['index'] == 1
        assert data[2]['key'] == "code/test2.txt"
        assert data[2]['description'] == "My file with stuff 2"
        assert data[2]['is_dir'] is False
        assert data[2]['index'] == 2
        assert data[3]['key'] == "code/tester/"
        assert data[3]['description'] == "My test dir"
        assert data[3]['is_dir'] is True
        assert data[3]['index'] == 3

    def test_update_larger_index_and_description(self, mock_labbook):
        """Test updating a description and index"""
        with open(os.path.join(mock_labbook[1], 'code', 'test1.txt'), 'wt') as test_file:
            test_file.write("blah1")
        with open(os.path.join(mock_labbook[1], 'code', 'test2.txt'), 'wt') as test_file:
            test_file.write("blah2")
        with open(os.path.join(mock_labbook[1], 'code', 'test3.txt'), 'wt') as test_file:
            test_file.write("blah3")
        os.makedirs(os.path.join(mock_labbook[1], 'code', 'tester'))

        mock_labbook[2].create_favorite("code", "test1.txt", description="My file with stuff 1")
        mock_labbook[2].create_favorite("code", "test2.txt", description="My file with stuff 2")
        mock_labbook[2].create_favorite("code", "test3.txt", description="My file with stuff 3")
        mock_labbook[2].create_favorite("code", "tester/", is_dir=True, description="My test dir")

        data = mock_labbook[2].get_favorites('code')
        assert len(data) == 4
        assert data[0]['key'] == "code/test1.txt"
        assert data[0]['description'] == "My file with stuff 1"
        assert data[0]['is_dir'] is False
        assert data[0]['index'] == 0
        assert data[1]['key'] == "code/test2.txt"
        assert data[1]['description'] == "My file with stuff 2"
        assert data[1]['is_dir'] is False
        assert data[1]['index'] == 1
        assert data[2]['key'] == "code/test3.txt"
        assert data[2]['description'] == "My file with stuff 3"
        assert data[2]['is_dir'] is False
        assert data[2]['index'] == 2
        assert data[3]['key'] == "code/tester/"
        assert data[3]['description'] == "My test dir"
        assert data[3]['is_dir'] is True
        assert data[3]['index'] == 3

        fav = mock_labbook[2].update_favorite('code', 0, new_description="UPDATED", new_index=2)
        assert fav['key'] == "code/test1.txt"
        assert fav['description'] == "UPDATED"
        assert fav['is_dir'] is False
        assert fav['index'] == 2

        data = mock_labbook[2].get_favorites('code')
        assert len(data) == 4
        assert data[0]['key'] == "code/test2.txt"
        assert data[0]['description'] == "My file with stuff 2"
        assert data[0]['is_dir'] is False
        assert data[0]['index'] == 0
        assert data[1]['key'] == "code/test3.txt"
        assert data[1]['description'] == "My file with stuff 3"
        assert data[1]['is_dir'] is False
        assert data[1]['index'] == 1
        assert data[2]['key'] == "code/test1.txt"
        assert data[2]['description'] == "UPDATED"
        assert data[2]['is_dir'] is False
        assert data[2]['index'] == 2
        assert data[3]['key'] == "code/tester/"
        assert data[3]['description'] == "My test dir"
        assert data[3]['is_dir'] is True
        assert data[3]['index'] == 3

        fav = mock_labbook[2].update_favorite('code', 0, new_description="UPDATED 2", new_index=3)
        assert fav['key'] == "code/test2.txt"
        assert fav['description'] == "UPDATED 2"
        assert fav['is_dir'] is False
        assert fav['index'] == 3

        data = mock_labbook[2].get_favorites('code')
        assert len(data) == 4
        assert data[0]['key'] == "code/test3.txt"
        assert data[0]['description'] == "My file with stuff 3"
        assert data[0]['is_dir'] is False
        assert data[0]['index'] == 0
        assert data[1]['key'] == "code/test1.txt"
        assert data[1]['description'] == "UPDATED"
        assert data[1]['is_dir'] is False
        assert data[1]['index'] == 1
        assert data[2]['key'] == "code/tester/"
        assert data[2]['description'] == "My test dir"
        assert data[2]['is_dir'] is True
        assert data[2]['index'] == 2
        assert data[3]['key'] == "code/test2.txt"
        assert data[3]['description'] == "UPDATED 2"
        assert data[3]['is_dir'] is False
        assert data[3]['index'] == 3

    def test_update_larger_index_and_description_and_key(self, mock_labbook):
        """Test updating a description and index and key"""
        with open(os.path.join(mock_labbook[1], 'code', 'test1.txt'), 'wt') as test_file:
            test_file.write("blah1")
        with open(os.path.join(mock_labbook[1], 'code', 'test2.txt'), 'wt') as test_file:
            test_file.write("blah2")
        with open(os.path.join(mock_labbook[1], 'code', 'test3.txt'), 'wt') as test_file:
            test_file.write("blah3")
        os.makedirs(os.path.join(mock_labbook[1], 'code', 'tester'))

        mock_labbook[2].create_favorite("code", "test1.txt", description="My file with stuff 1")
        mock_labbook[2].create_favorite("code", "test2.txt", description="My file with stuff 2")
        mock_labbook[2].create_favorite("code", "test3.txt", description="My file with stuff 3")
        mock_labbook[2].create_favorite("code", "tester/", is_dir=True, description="My test dir")

        data = mock_labbook[2].get_favorites('code')
        assert len(data) == 4
        assert data[0]['key'] == "code/test1.txt"
        assert data[0]['description'] == "My file with stuff 1"
        assert data[0]['is_dir'] is False
        assert data[0]['index'] == 0
        assert data[1]['key'] == "code/test2.txt"
        assert data[1]['description'] == "My file with stuff 2"
        assert data[1]['is_dir'] is False
        assert data[1]['index'] == 1
        assert data[2]['key'] == "code/test3.txt"
        assert data[2]['description'] == "My file with stuff 3"
        assert data[2]['is_dir'] is False
        assert data[2]['index'] == 2
        assert data[3]['key'] == "code/tester/"
        assert data[3]['description'] == "My test dir"
        assert data[3]['is_dir'] is True
        assert data[3]['index'] == 3

        # Expect error since rename hasn't happened yet.
        with pytest.raises(ValueError):
            mock_labbook[2].update_favorite('code', 0, new_description="UPDATED", new_index=2,
                                            new_key="code/UPDATED.txt")

        os.rename(os.path.join(mock_labbook[1], 'code', 'test1.txt'),
                  os.path.join(mock_labbook[1], 'code', 'UPDATED.txt'))
        fav = mock_labbook[2].update_favorite('code', 0, new_description="UPDATED", new_index=2,
                                              new_key="code/UPDATED.txt")
        assert fav['key'] == "code/UPDATED.txt"
        assert fav['description'] == "UPDATED"
        assert fav['is_dir'] is False
        assert fav['index'] == 2

        data = mock_labbook[2].get_favorites('code')
        assert len(data) == 4
        assert data[0]['key'] == "code/test2.txt"
        assert data[0]['description'] == "My file with stuff 2"
        assert data[0]['is_dir'] is False
        assert data[0]['index'] == 0
        assert data[1]['key'] == "code/test3.txt"
        assert data[1]['description'] == "My file with stuff 3"
        assert data[1]['is_dir'] is False
        assert data[1]['index'] == 1
        assert data[2]['key'] == "code/UPDATED.txt"
        assert data[2]['description'] == "UPDATED"
        assert data[2]['is_dir'] is False
        assert data[2]['index'] == 2
        assert data[3]['key'] == "code/tester/"
        assert data[3]['description'] == "My test dir"
        assert data[3]['is_dir'] is True
        assert data[3]['index'] == 3
