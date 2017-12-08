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
from lmcommon.fixtures import mock_labbook, mock_config_with_detaildb
from lmcommon.activity.detaildb import ActivityDetailDB


class TestDetailDB(object):

    def test_constructor(self, mock_labbook):
        """Test the constructor"""
        db = ActivityDetailDB(mock_labbook[2].root_dir, mock_labbook[2].checkout_id, 4000000)

        assert type(db) == ActivityDetailDB
        assert db.logfile_limit == 4000000
        assert db.checkout_id == mock_labbook[2].checkout_id

    def test_file_number(self, mock_config_with_detaildb):
        """Test the file_number property"""
        assert mock_config_with_detaildb[0].file_number == 0
        assert mock_config_with_detaildb[0].file_number == 0

    def test_file_number_reload(self, mock_config_with_detaildb):
        """Test the file_number property"""
        assert mock_config_with_detaildb[0].file_number == 0
        mock_config_with_detaildb[0]._write_metadata_file(increment=True)
        assert mock_config_with_detaildb[0].file_number == 1

        # reset locally stored file_number
        new_detail_db_instance = ActivityDetailDB(mock_config_with_detaildb[1].root_dir,
                                                  mock_config_with_detaildb[1].checkout_id)

        assert new_detail_db_instance.file_number == 1

    def test_file_number_new_checkout_context(self, mock_config_with_detaildb):
        """Test the file_number property if a new branch has been created"""
        assert mock_config_with_detaildb[0].file_number == 0
        mock_config_with_detaildb[0]._write_metadata_file(increment=True)
        assert mock_config_with_detaildb[0].file_number == 1

        # reset locally stored file_number by changing the checkout ID
        mock_config_with_detaildb[0].checkout_id = "adsl;jkadksflj;"
        assert mock_config_with_detaildb[0].file_number == 0

    def test_increment_metadata(self, mock_config_with_detaildb):
        """Test the file_number property if a new branch has been created"""
        assert mock_config_with_detaildb[0].file_number == 0

        mock_config_with_detaildb[0]._write_metadata_file(increment=False)
        assert mock_config_with_detaildb[0].file_number == 0

        mock_config_with_detaildb[0]._write_metadata_file(increment=True)
        assert mock_config_with_detaildb[0].file_number == 1

    def test_generate_detail_header(self, mock_config_with_detaildb):
        """Test generating a detail header"""
        assert mock_config_with_detaildb[0]._generate_detail_header(10, 20) == \
               b'__g__lsn\x00\x00\x00\x00\n\x00\x00\x00\x14\x00\x00\x00'

        # Increment the file number a bunch
        for _ in range(49):
            mock_config_with_detaildb[0]._write_metadata_file(increment=True)

        assert mock_config_with_detaildb[0]._generate_detail_header(511564, 6455412) == \
               b'__g__lsn1\x00\x00\x00L\xce\x07\x00t\x80b\x00'

    def test_parse_detail_header(self, mock_config_with_detaildb):
        """Test parsing a detail header"""
        assert mock_config_with_detaildb[0]._parse_detail_header(b'__g__lsn\x00\x00\x00\x00\n\x00\x00\x00\x14\x00\x00\x00') == \
               (0, 10, 20)

        assert mock_config_with_detaildb[0]._parse_detail_header(b'__g__lsn1\x00\x00\x00L\xce\x07\x00t\x80b\x00') == \
               (49, 511564, 6455412)

    def test_parse_detail_key(self, mock_config_with_detaildb):
        """Test generating a detail key"""
        basename, detail_header = mock_config_with_detaildb[0]._parse_detail_key('log_eb9167d60c9d11cfff3d14aaa7165552X19nX19sc24AAAAACgAAABQAAAA=')

        assert type(basename) == str
        assert len(basename) == 36
        assert detail_header == b'__g__lsn\x00\x00\x00\x00\n\x00\x00\x00\x14\x00\x00\x00'

    def test_file_rotate(self, mock_labbook):
        """Test rotating the file"""
        db = ActivityDetailDB(mock_labbook[2].root_dir, mock_labbook[2].checkout_id, 2000)

        fp = db._open_for_append_and_rotate()
        fp.write(("blah").encode())
        fp.close()

        # assert file exists
        assert os.path.join(db.root_path, db.basename + '_0') == fp.name
        assert os.path.exists(os.path.join(db.root_path, db.basename + '_0')) is True
        assert os.path.exists(os.path.join(db.root_path, db.basename + '_1')) is False

        fp = db._open_for_append_and_rotate()
        fp.write(("blah" * 3000).encode())
        fp.close()

        # assert same file exists
        assert os.path.join(db.root_path, db.basename + '_0') == fp.name
        assert os.path.exists(os.path.join(db.root_path, db.basename + '_0')) is True
        assert os.path.exists(os.path.join(db.root_path, db.basename + '_1')) is False

        fp = db._open_for_append_and_rotate()

        # assert it rolled
        assert os.path.join(db.root_path, db.basename + '_1') == fp.name
        assert os.path.exists(os.path.join(db.root_path, db.basename + '_0')) is True
        assert os.path.exists(os.path.join(db.root_path, db.basename + '_1')) is True

    def test_put_get(self, mock_config_with_detaildb):
        """Test putting and getting a record"""
        my_val = b'thisisastreamofstuff'

        detail_key = mock_config_with_detaildb[0].put(my_val)
        basename, detail_header = mock_config_with_detaildb[0]._parse_detail_key(detail_key)
        file_num, offset, length = mock_config_with_detaildb[0]._parse_detail_header(detail_header)

        assert file_num == 0
        assert offset == 0
        assert length == len(my_val)

        return_val = mock_config_with_detaildb[0].get(detail_key)
        assert return_val == my_val

    def test_put_get_errors(self, mock_config_with_detaildb):
        """Test putting and getting a record with validation errors"""

        with pytest.raises(ValueError):
            detail_key = mock_config_with_detaildb[0].put("astringvalue")

        with pytest.raises(ValueError):
            detail_key = mock_config_with_detaildb[0].get(None)

        with pytest.raises(ValueError):
            detail_key = mock_config_with_detaildb[0].get("")

        with pytest.raises(ValueError):
            detail_key = mock_config_with_detaildb[0].get(b"abytekey")
