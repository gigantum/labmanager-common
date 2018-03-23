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
import os
import json
from collections import OrderedDict

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
        # commit
        mock_labbook[2].git.add(os.path.join(mock_labbook[1], 'code', 'test.txt'))
        mock_labbook[2].git.commit("test file")

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

        assert len(data.keys()) == 1
        assert 'test.txt' in data
        assert data["test.txt"]['key'] == "test.txt"
        assert data["test.txt"]['description'] == "My file with stuff"
        assert data["test.txt"]['is_dir'] is False
        assert data["test.txt"]['index'] == 0
        assert result['key'] == "test.txt"
        assert result['description'] == "My file with stuff"
        assert result['is_dir'] is False
        assert result['index'] == 0

        assert mock_labbook[2].is_repo_clean is True

    def test_duplicate_favorite_file(self, mock_labbook):
        """Test creating favorite for a file twice"""
        with open(os.path.join(mock_labbook[1], 'code', 'test.txt'), 'wt') as test_file:
            test_file.write("blah")
        # commit
        mock_labbook[2].git.add(os.path.join(mock_labbook[1], 'code', 'test.txt'))
        mock_labbook[2].git.commit("test file")

        favorites_dir = os.path.join(mock_labbook[1], '.gigantum', 'favorites')
        assert os.path.exists(favorites_dir) is False
        assert os.path.isdir(favorites_dir) is False
        assert os.path.exists(os.path.join(favorites_dir, 'code.json')) is False
        assert os.path.isfile(os.path.join(favorites_dir, 'code.json')) is False

        mock_labbook[2].create_favorite("code", "test.txt", description="My file with stuff")

        with pytest.raises(ValueError):
            mock_labbook[2].create_favorite("code", "test.txt", description="My file with stuff")

        assert mock_labbook[2].is_repo_clean is True

    def test_append_to_favorite_file(self, mock_labbook):
        """Test creating two favorites for a file"""
        with open(os.path.join(mock_labbook[1], 'code', 'test.txt'), 'wt') as test_file:
            test_file.write("blah")
        # commit
        mock_labbook[2].git.add(os.path.join(mock_labbook[1], 'code', 'test.txt'))
        mock_labbook[2].git.commit("test file")
        with open(os.path.join(mock_labbook[1], 'code', 'test2.txt'), 'wt') as test_file:
            test_file.write("blah2")
        # commit
        mock_labbook[2].git.add(os.path.join(mock_labbook[1], 'code', 'test2.txt'))
        mock_labbook[2].git.commit("test file")

        mock_labbook[2].create_favorite("code", "test.txt", description="My file with stuff")
        result = mock_labbook[2].create_favorite("code", "test2.txt", description="My file with stuff 2")

        favorites_dir = os.path.join(mock_labbook[1], '.gigantum', 'favorites')
        assert os.path.exists(favorites_dir) is True
        assert os.path.isdir(favorites_dir) is True
        assert os.path.exists(os.path.join(favorites_dir, 'code.json')) is True
        assert os.path.isfile(os.path.join(favorites_dir, 'code.json')) is True

        with open(os.path.join(favorites_dir, 'code.json'), 'rt') as ff:
            data = json.load(ff)

        assert len(data.keys()) == 2
        assert 'test.txt' in data
        assert data["test.txt"]['key'] == "test.txt"
        assert data["test.txt"]['description'] == "My file with stuff"
        assert data["test.txt"]['is_dir'] is False
        assert data["test.txt"]['index'] == 0
        assert data["test2.txt"]['key'] == "test2.txt"
        assert data["test2.txt"]['description'] == "My file with stuff 2"
        assert data["test2.txt"]['is_dir'] is False
        assert data["test2.txt"]['index'] == 1
        assert result['key'] == "test2.txt"
        assert result['description'] == "My file with stuff 2"
        assert result['is_dir'] is False
        assert result['index'] == 1

        assert mock_labbook[2].is_repo_clean is True

    def test_favorite_dir(self, mock_labbook):
        """Test creating a favorite directory"""
        os.makedirs(os.path.join(mock_labbook[1], 'code', 'fav'))
        with open(os.path.join(mock_labbook[1], 'code', 'fav', 'test1.txt'), 'wt') as test_file:
            test_file.write("blah1")
        # commit
        mock_labbook[2].git.add_all()
        mock_labbook[2].git.commit("test file")

        with pytest.raises(ValueError):
            mock_labbook[2].create_favorite("code", "fav/", description="Dir with stuff")

        mock_labbook[2].create_favorite("code", "fav/", description="Dir with stuff", is_dir=True)

        favorites_dir = os.path.join(mock_labbook[1], '.gigantum', 'favorites')
        with open(os.path.join(favorites_dir, 'code.json'), 'rt') as ff:
            data = json.load(ff)

        assert len(data.keys()) == 1
        assert 'fav/' in data
        assert data["fav/"]['key'] == "fav/"
        assert data["fav/"]['description'] == "Dir with stuff"
        assert data["fav/"]['is_dir'] is True
        assert data["fav/"]['index'] == 0

        assert mock_labbook[2].is_repo_clean is True

    def test_favorite_all_subdirs(self, mock_labbook):
        """Test creating favorites for each subdir type that is supported"""
        with open(os.path.join(mock_labbook[1], 'code', 'test1.txt'), 'wt') as test_file:
            test_file.write("blah1")
        with open(os.path.join(mock_labbook[1], 'input', 'test2.txt'), 'wt') as test_file:
            test_file.write("blah2")
        with open(os.path.join(mock_labbook[1], 'output', 'test3.txt'), 'wt') as test_file:
            test_file.write("blah3")
        # commit
        mock_labbook[2].git.add_all()
        mock_labbook[2].git.commit("test file")

        mock_labbook[2].create_favorite("code", "test1.txt", description="My file with stuff 1")
        mock_labbook[2].create_favorite("input", "test2.txt", description="My file with stuff 2")
        mock_labbook[2].create_favorite("output", "test3.txt", description="My file with stuff 3")

        favorites_dir = os.path.join(mock_labbook[1], '.gigantum', 'favorites')
        assert os.path.exists(os.path.join(favorites_dir, 'code.json')) is True
        assert os.path.exists(os.path.join(favorites_dir, 'input.json')) is True
        assert os.path.exists(os.path.join(favorites_dir, 'output.json')) is True

        with open(os.path.join(favorites_dir, 'code.json'), 'rt') as ff:
            data = json.load(ff)

        assert len(data.keys()) == 1
        assert 'test1.txt' in data
        assert data["test1.txt"]['key'] == "test1.txt"
        assert data["test1.txt"]['description'] == "My file with stuff 1"
        assert data["test1.txt"]['is_dir'] is False
        assert data["test1.txt"]['index'] == 0

        with open(os.path.join(favorites_dir, 'input.json'), 'rt') as ff:
            data = json.load(ff)
        assert 'test2.txt' in data
        assert data["test2.txt"]['key'] == "test2.txt"
        assert data["test2.txt"]['description'] == "My file with stuff 2"
        assert data["test2.txt"]['is_dir'] is False
        assert data["test2.txt"]['index'] == 0

        with open(os.path.join(favorites_dir, 'output.json'), 'rt') as ff:
            data = json.load(ff)
        assert 'test3.txt' in data
        assert data["test3.txt"]['key'] == "test3.txt"
        assert data["test3.txt"]['description'] == "My file with stuff 3"
        assert data["test3.txt"]['is_dir'] is False
        assert data["test3.txt"]['index'] == 0

        assert mock_labbook[2].is_repo_clean is True

    def test_remove_favorite_errors(self, mock_labbook):
        """Test errors when removing"""
        with open(os.path.join(mock_labbook[1], 'code', 'test.txt'), 'wt') as test_file:
            test_file.write("blah")
        # commit
        mock_labbook[2].git.add_all()
        mock_labbook[2].git.commit("test file")

        with pytest.raises(ValueError):
            mock_labbook[2].remove_favorite('code', "test.txt")

        # Add a favorite
        mock_labbook[2].create_favorite("code", "test.txt", description="My file with stuff")

        with pytest.raises(ValueError):
            mock_labbook[2].remove_favorite('code', "asdfasdf")
        with pytest.raises(ValueError):
            mock_labbook[2].remove_favorite('input', "test.txt")
        with pytest.raises(ValueError):
            mock_labbook[2].remove_favorite('asdfasdf', "test.txt")

        assert mock_labbook[2].is_repo_clean is True

    def test_remove_favorite_file(self, mock_labbook):
        """Test removing a favorites file"""
        with open(os.path.join(mock_labbook[1], 'code', 'test.txt'), 'wt') as test_file:
            test_file.write("blah")
        with open(os.path.join(mock_labbook[1], 'code', 'test2.txt'), 'wt') as test_file:
            test_file.write("blah2")
        with open(os.path.join(mock_labbook[1], 'code', 'test3.txt'), 'wt') as test_file:
            test_file.write("blah3")
        # commit
        mock_labbook[2].git.add_all()
        mock_labbook[2].git.commit("test file")

        mock_labbook[2].create_favorite("code", "test.txt", description="My file with stuff")
        mock_labbook[2].create_favorite("code", "test3.txt", description="My file with stuff 3")
        mock_labbook[2].create_favorite("code", "test2.txt", description="My file with stuff 2")

        assert mock_labbook[2].is_repo_clean is True

        favorites_dir = os.path.join(mock_labbook[1], '.gigantum', 'favorites')

        mock_labbook[2].remove_favorite("code", "test3.txt")

        with open(os.path.join(favorites_dir, 'code.json'), 'rt') as ff:
            data = json.load(ff)

        assert len(data.keys()) == 2
        assert 'test2.txt' in data
        assert 'test.txt' in data
        assert data["test.txt"]['key'] == "test.txt"
        assert data["test.txt"]['description'] == "My file with stuff"
        assert data["test.txt"]['is_dir'] is False
        assert data["test.txt"]['index'] == 0
        assert data["test2.txt"]['key'] == "test2.txt"
        assert data["test2.txt"]['description'] == "My file with stuff 2"
        assert data["test2.txt"]['is_dir'] is False
        assert data["test2.txt"]['index'] == 1

        assert mock_labbook[2].is_repo_clean is True

    def test_get_favorites(self, mock_labbook):
        """Test getting favorites"""
        with open(os.path.join(mock_labbook[1], 'code', 'test1.txt'), 'wt') as test_file:
            test_file.write("blah1")
        with open(os.path.join(mock_labbook[1], 'code', 'test2.txt'), 'wt') as test_file:
            test_file.write("blah2")
        os.makedirs(os.path.join(mock_labbook[1], 'code', 'tester'))
        # commit
        mock_labbook[2].git.add_all()
        mock_labbook[2].git.commit("test file")

        mock_labbook[2].create_favorite("code", "test2.txt", description="My file with stuff 2")
        mock_labbook[2].create_favorite("code", "tester/", is_dir=True, description="My test dir")
        mock_labbook[2].create_favorite("code", "test1.txt", description="My file with stuff 1")

        with pytest.raises(ValueError):
            mock_labbook[2].get_favorites('asdfadsf')

        data = mock_labbook[2].get_favorites('code')

        assert type(data) == OrderedDict
        assert len(data.keys()) == 3
        assert list(data.keys()) == ["test2.txt", "tester/", "test1.txt"]

        assert data["test1.txt"]['key'] == "test1.txt"
        assert data["test1.txt"]['description'] == "My file with stuff 1"
        assert data["test1.txt"]['is_dir'] is False
        assert data["test1.txt"]['index'] == 2

        assert data["test2.txt"]['key'] == "test2.txt"
        assert data["test2.txt"]['description'] == "My file with stuff 2"
        assert data["test2.txt"]['is_dir'] is False
        assert data["test2.txt"]['index'] == 0

        assert data["tester/"]['key'] == "tester/"
        assert data["tester/"]['description'] == "My test dir"
        assert data["tester/"]['is_dir'] is True
        assert data["tester/"]['index'] == 1

        assert mock_labbook[2].is_repo_clean is True

    def test_update_description(self, mock_labbook):
        """Test updating a description"""
        with open(os.path.join(mock_labbook[1], 'code', 'test1.txt'), 'wt') as test_file:
            test_file.write("blah1")
        # commit
        mock_labbook[2].git.add_all()
        mock_labbook[2].git.commit("test file")

        # Expect error since favorite doesn't exist yet
        with pytest.raises(ValueError):
            mock_labbook[2].update_favorite('code', 'test1.txt', new_description="UPDATED")

        # Expect error since `codasdfasdfe` isn't a valid labbook section
        with pytest.raises(ValueError):
            mock_labbook[2].update_favorite('codasdfasdfe', 'test1.txt', new_description="UPDATED")

        # Create favorite
        mock_labbook[2].create_favorite("code", "test1.txt", description="My fav thingy")

        fav = mock_labbook[2].update_favorite('code', 'test1.txt', new_description="UPDATED")
        assert fav['key'] == "test1.txt"
        assert fav['index'] == 0
        assert fav['description'] == "UPDATED"
        assert fav['is_dir'] is False

        data = mock_labbook[2].get_favorites('code')

        assert len(data.keys()) == 1
        assert data["test1.txt"]['key'] == "test1.txt"
        assert data["test1.txt"]['description'] == "UPDATED"
        assert data["test1.txt"]['is_dir'] is False
        assert data["test1.txt"]['index'] == 0

        assert mock_labbook[2].is_repo_clean is True

    def test_update_invalid_index(self, mock_labbook):
        """Test updating an index to an invalid value raises exception"""
        with open(os.path.join(mock_labbook[1], 'code', 'test1.txt'), 'wt') as test_file:
            test_file.write("blah1")
        with open(os.path.join(mock_labbook[1], 'code', 'test2.txt'), 'wt') as test_file:
            test_file.write("blah2")
        # commit
        mock_labbook[2].git.add_all()
        mock_labbook[2].git.commit("test file")

        mock_labbook[2].create_favorite("code", "test1.txt", description="My file with stuff 1")
        mock_labbook[2].create_favorite("code", "test2.txt", description="My file with stuff 2")

        with pytest.raises(ValueError):
            mock_labbook[2].update_favorite('code', "test1.txt", new_index=-1)

        with pytest.raises(ValueError):
            mock_labbook[2].update_favorite('code', "test1.txt", new_index=2)

        with pytest.raises(ValueError):
            mock_labbook[2].update_favorite('code', "test1.txt", new_index=200)

        assert mock_labbook[2].is_repo_clean is True

    def test_update_smaller_index_and_description(self, mock_labbook):
        """Test updating a description and index"""
        with open(os.path.join(mock_labbook[1], 'code', 'test1.txt'), 'wt') as test_file:
            test_file.write("blah1")
        with open(os.path.join(mock_labbook[1], 'code', 'test2.txt'), 'wt') as test_file:
            test_file.write("blah2")
        with open(os.path.join(mock_labbook[1], 'code', 'test3.txt'), 'wt') as test_file:
            test_file.write("blah3")
        os.makedirs(os.path.join(mock_labbook[1], 'code', 'tester'))
        # commit
        mock_labbook[2].git.add_all()
        mock_labbook[2].git.commit("test file")

        mock_labbook[2].create_favorite("code", "test1.txt", description="My file with stuff 1")
        mock_labbook[2].create_favorite("code", "test2.txt", description="My file with stuff 2")
        mock_labbook[2].create_favorite("code", "test3.txt", description="My file with stuff 3")
        mock_labbook[2].create_favorite("code", "tester/", is_dir=True, description="My test dir")

        data = mock_labbook[2].get_favorites('code')

        assert type(data) == OrderedDict
        assert len(data.keys()) == 4
        assert list(data.keys()) == ["test1.txt", "test2.txt", "test3.txt", "tester/"]

        assert data["test1.txt"]['key'] == "test1.txt"
        assert data["test1.txt"]['description'] == "My file with stuff 1"
        assert data["test1.txt"]['is_dir'] is False
        assert data["test1.txt"]['index'] == 0

        assert data["test2.txt"]['key'] == "test2.txt"
        assert data["test2.txt"]['description'] == "My file with stuff 2"
        assert data["test2.txt"]['is_dir'] is False
        assert data["test2.txt"]['index'] == 1

        assert data["test3.txt"]['key'] == "test3.txt"
        assert data["test3.txt"]['description'] == "My file with stuff 3"
        assert data["test3.txt"]['is_dir'] is False
        assert data["test3.txt"]['index'] == 2

        assert data["tester/"]['key'] == "tester/"
        assert data["tester/"]['description'] == "My test dir"
        assert data["tester/"]['is_dir'] is True
        assert data["tester/"]['index'] == 3

        fav = mock_labbook[2].update_favorite('code', "tester/", new_description="UPDATED", new_index=1)
        assert fav['key'] == "tester/"
        assert fav['description'] == "UPDATED"
        assert fav['is_dir'] is True
        assert fav['index'] == 1

        data = mock_labbook[2].get_favorites('code')
        assert len(data.keys()) == 4
        assert list(data.keys()) == ["test1.txt", "tester/", "test2.txt", "test3.txt"]

        assert data["test1.txt"]['key'] == "test1.txt"
        assert data["test1.txt"]['description'] == "My file with stuff 1"
        assert data["test1.txt"]['is_dir'] is False
        assert data["test1.txt"]['index'] == 0

        assert data["test2.txt"]['key'] == "test2.txt"
        assert data["test2.txt"]['description'] == "My file with stuff 2"
        assert data["test2.txt"]['is_dir'] is False
        assert data["test2.txt"]['index'] == 2

        assert data["test3.txt"]['key'] == "test3.txt"
        assert data["test3.txt"]['description'] == "My file with stuff 3"
        assert data["test3.txt"]['is_dir'] is False
        assert data["test3.txt"]['index'] == 3

        assert data["tester/"]['key'] == "tester/"
        assert data["tester/"]['description'] == "UPDATED"
        assert data["tester/"]['is_dir'] is True
        assert data["tester/"]['index'] == 1

        assert mock_labbook[2].is_repo_clean is True

    def test_update_larger_index_and_description(self, mock_labbook):
        """Test updating a description and index"""
        with open(os.path.join(mock_labbook[1], 'code', 'test1.txt'), 'wt') as test_file:
            test_file.write("blah1")
        with open(os.path.join(mock_labbook[1], 'code', 'test2.txt'), 'wt') as test_file:
            test_file.write("blah2")
        with open(os.path.join(mock_labbook[1], 'code', 'test3.txt'), 'wt') as test_file:
            test_file.write("blah3")
        os.makedirs(os.path.join(mock_labbook[1], 'code', 'tester'))
        # commit
        mock_labbook[2].git.add_all()
        mock_labbook[2].git.commit("test file")

        mock_labbook[2].create_favorite("code", "test1.txt", description="My file with stuff 1")
        mock_labbook[2].create_favorite("code", "test2.txt", description="My file with stuff 2")
        mock_labbook[2].create_favorite("code", "test3.txt", description="My file with stuff 3")
        mock_labbook[2].create_favorite("code", "tester/", is_dir=True, description="My test dir")

        data = mock_labbook[2].get_favorites('code')

        assert type(data) == OrderedDict
        assert len(data.keys()) == 4
        assert list(data.keys()) == ["test1.txt", "test2.txt", "test3.txt", "tester/"]

        assert data["test1.txt"]['key'] == "test1.txt"
        assert data["test1.txt"]['description'] == "My file with stuff 1"
        assert data["test1.txt"]['is_dir'] is False
        assert data["test1.txt"]['index'] == 0

        assert data["test2.txt"]['key'] == "test2.txt"
        assert data["test2.txt"]['description'] == "My file with stuff 2"
        assert data["test2.txt"]['is_dir'] is False
        assert data["test2.txt"]['index'] == 1

        assert data["test3.txt"]['key'] == "test3.txt"
        assert data["test3.txt"]['description'] == "My file with stuff 3"
        assert data["test3.txt"]['is_dir'] is False
        assert data["test3.txt"]['index'] == 2

        assert data["tester/"]['key'] == "tester/"
        assert data["tester/"]['description'] == "My test dir"
        assert data["tester/"]['is_dir'] is True
        assert data["tester/"]['index'] == 3

        fav = mock_labbook[2].update_favorite('code', "test1.txt", new_description="UPDATED", new_index=2)
        assert fav['key'] == "test1.txt"
        assert fav['description'] == "UPDATED"
        assert fav['is_dir'] is False
        assert fav['index'] == 2

        data = mock_labbook[2].get_favorites('code')

        assert type(data) == OrderedDict
        assert len(data.keys()) == 4
        assert list(data.keys()) == ["test2.txt", "test3.txt", "test1.txt", "tester/"]

        assert data["test1.txt"]['key'] == "test1.txt"
        assert data["test1.txt"]['description'] == "UPDATED"
        assert data["test1.txt"]['is_dir'] is False
        assert data["test1.txt"]['index'] == 2

        assert data["test2.txt"]['key'] == "test2.txt"
        assert data["test2.txt"]['description'] == "My file with stuff 2"
        assert data["test2.txt"]['is_dir'] is False
        assert data["test2.txt"]['index'] == 0

        assert data["test3.txt"]['key'] == "test3.txt"
        assert data["test3.txt"]['description'] == "My file with stuff 3"
        assert data["test3.txt"]['is_dir'] is False
        assert data["test3.txt"]['index'] == 1

        assert data["tester/"]['key'] == "tester/"
        assert data["tester/"]['description'] == "My test dir"
        assert data["tester/"]['is_dir'] is True
        assert data["tester/"]['index'] == 3

        fav = mock_labbook[2].update_favorite('code', "test2.txt", new_description="UPDATED 2", new_index=3)
        assert fav['key'] == "test2.txt"
        assert fav['description'] == "UPDATED 2"
        assert fav['is_dir'] is False
        assert fav['index'] == 3

        data = mock_labbook[2].get_favorites('code')

        assert type(data) == OrderedDict
        assert len(data.keys()) == 4
        assert list(data.keys()) == ["test3.txt", "test1.txt", "tester/", "test2.txt"]

        assert data["test1.txt"]['key'] == "test1.txt"
        assert data["test1.txt"]['description'] == "UPDATED"
        assert data["test1.txt"]['is_dir'] is False
        assert data["test1.txt"]['index'] == 1

        assert data["test2.txt"]['key'] == "test2.txt"
        assert data["test2.txt"]['description'] == "UPDATED 2"
        assert data["test2.txt"]['is_dir'] is False
        assert data["test2.txt"]['index'] == 3

        assert data["test3.txt"]['key'] == "test3.txt"
        assert data["test3.txt"]['description'] == "My file with stuff 3"
        assert data["test3.txt"]['is_dir'] is False
        assert data["test3.txt"]['index'] == 0

        assert data["tester/"]['key'] == "tester/"
        assert data["tester/"]['description'] == "My test dir"
        assert data["tester/"]['is_dir'] is True
        assert data["tester/"]['index'] == 2

        assert mock_labbook[2].is_repo_clean is True

    def test_update_same_index(self, mock_labbook):
        """Test updating with the same index"""
        with open(os.path.join(mock_labbook[1], 'code', 'test1.txt'), 'wt') as test_file:
            test_file.write("blah1")
        with open(os.path.join(mock_labbook[1], 'code', 'test2.txt'), 'wt') as test_file:
            test_file.write("blah2")
        with open(os.path.join(mock_labbook[1], 'code', 'test3.txt'), 'wt') as test_file:
            test_file.write("blah3")
        os.makedirs(os.path.join(mock_labbook[1], 'code', 'tester'))
        # commit
        mock_labbook[2].git.add_all()
        mock_labbook[2].git.commit("test file")

        mock_labbook[2].create_favorite("code", "test1.txt", description="My file with stuff 1")
        mock_labbook[2].create_favorite("code", "test2.txt", description="My file with stuff 2")
        mock_labbook[2].create_favorite("code", "test3.txt", description="My file with stuff 3")
        mock_labbook[2].create_favorite("code", "tester/", is_dir=True, description="My test dir")

        data = mock_labbook[2].get_favorites('code')

        assert type(data) == OrderedDict
        assert len(data.keys()) == 4
        assert list(data.keys()) == ["test1.txt", "test2.txt", "test3.txt", "tester/"]

        assert data["test1.txt"]['key'] == "test1.txt"
        assert data["test1.txt"]['description'] == "My file with stuff 1"
        assert data["test1.txt"]['is_dir'] is False
        assert data["test1.txt"]['index'] == 0

        assert data["test2.txt"]['key'] == "test2.txt"
        assert data["test2.txt"]['description'] == "My file with stuff 2"
        assert data["test2.txt"]['is_dir'] is False
        assert data["test2.txt"]['index'] == 1

        assert data["test3.txt"]['key'] == "test3.txt"
        assert data["test3.txt"]['description'] == "My file with stuff 3"
        assert data["test3.txt"]['is_dir'] is False
        assert data["test3.txt"]['index'] == 2

        assert data["tester/"]['key'] == "tester/"
        assert data["tester/"]['description'] == "My test dir"
        assert data["tester/"]['is_dir'] is True
        assert data["tester/"]['index'] == 3

        fav = mock_labbook[2].update_favorite('code', "test2.txt", new_description="UPDATED", new_index=1)
        assert fav['key'] == "test2.txt"
        assert fav['description'] == "UPDATED"
        assert fav['is_dir'] is False
        assert fav['index'] == 1

        data = mock_labbook[2].get_favorites('code')

        assert data["test1.txt"]['key'] == "test1.txt"
        assert data["test1.txt"]['description'] == "My file with stuff 1"
        assert data["test1.txt"]['is_dir'] is False
        assert data["test1.txt"]['index'] == 0

        assert data["test2.txt"]['key'] == "test2.txt"
        assert data["test2.txt"]['description'] == "UPDATED"
        assert data["test2.txt"]['is_dir'] is False
        assert data["test2.txt"]['index'] == 1

        assert data["test3.txt"]['key'] == "test3.txt"
        assert data["test3.txt"]['description'] == "My file with stuff 3"
        assert data["test3.txt"]['is_dir'] is False
        assert data["test3.txt"]['index'] == 2

        assert data["tester/"]['key'] == "tester/"
        assert data["tester/"]['description'] == "My test dir"
        assert data["tester/"]['is_dir'] is True
        assert data["tester/"]['index'] == 3

        assert mock_labbook[2].is_repo_clean is True

    def test_favorite_data_prop(self, mock_labbook):
        """Test accessing the favorites cached data property"""
        with open(os.path.join(mock_labbook[1], 'code', 'test1.txt'), 'wt') as test_file:
            test_file.write("blah1")
        with open(os.path.join(mock_labbook[1], 'input', 'test2.txt'), 'wt') as test_file:
            test_file.write("blah2")
        with open(os.path.join(mock_labbook[1], 'output', 'test3.txt'), 'wt') as test_file:
            test_file.write("blah3")

        os.makedirs(os.path.join(mock_labbook[1], 'code', 'subdir1'))
        os.makedirs(os.path.join(mock_labbook[1], 'input', 'subdir2'))
        # commit
        mock_labbook[2].git.add_all()
        mock_labbook[2].git.commit("test file")

        mock_labbook[2].create_favorite("code", "test1.txt", description="My file with stuff 1")
        mock_labbook[2].create_favorite("input", "test2.txt", description="My file with stuff 2")
        mock_labbook[2].create_favorite("output", "test3.txt", description="My file with stuff 3")
        mock_labbook[2].create_favorite("code", "subdir1/", is_dir=True, description="Test dir 1")
        mock_labbook[2].create_favorite("input", "subdir2/", is_dir=True, description="Test dir 2")

        assert mock_labbook[2]._favorite_keys is None

        favs = mock_labbook[2].favorite_keys
        assert len(favs['code']) == 2
        assert len(favs['input']) == 2
        assert len(favs['output']) == 1

        assert favs['code'][0] == 'test1.txt'
        assert favs['code'][1] == 'subdir1/'
        assert favs['input'][0] == 'test2.txt'
        assert favs['input'][1] == 'subdir2/'
        assert favs['output'][0] == 'test3.txt'

        mock_labbook[2]._favorite_keys['code'].append("test value added")
        favs_again = mock_labbook[2].favorite_keys
        assert "test value added" in favs_again['code']

        assert mock_labbook[2].is_repo_clean is True
