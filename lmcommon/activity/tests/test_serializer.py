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
from lmcommon.activity.serializers import Serializer
from lmcommon.activity.serializers.text import PlainSerializer


class TestSerializer(object):

    def test_constructor(self):
        """Test the constructor"""
        s = Serializer()

        assert type(s) == Serializer
        assert type(s.serializers['text/plain']) == PlainSerializer

    def test_bad_mime_type(self):
        """Test the constructor"""
        s = Serializer()

        with pytest.raises(ValueError):
            s.serialize('text/asdfasdfasdfasdf', 'asdfasdfasd')

    def test_text_plain(self):
        """Test the text/plain serializer"""
        s = Serializer()

        start_text = "This is a \n\n string with some \r stuff in it23894590*AS^&90R32UXZ02.66"

        test_bytes = s.serialize('text/plain', start_text)
        assert type(test_bytes) == bytes

        test_str = s.deserialize('text/plain', test_bytes)

        assert start_text == test_str
        assert type(test_str) == str

        test_str_2 = s.jsonify('text/plain', start_text)

        assert start_text == test_str_2
        assert type(test_str_2) == str

    def test_image_base64_png(self):
        """Test the image base64 serializers - png"""
        s = Serializer()

        example_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5/hPwAIAgL/4d1j8wAAAABJRU5ErkJggg=="

        test_bytes = s.serialize('image/png', example_png)
        assert type(test_bytes) == bytes

        test_str = s.deserialize('image/png', test_bytes)
        assert type(test_str) == str

    def test_image_jsonify_legacy(self):
        s = Serializer()

        example_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5/hPwAIAgL/4d1j8wAAAABJRU5ErkJggg=="
        test_str_2 = s.jsonify('image/png', example_png)

        assert test_str_2 == f"data:image/png;base64,{example_png}"

    def test_image_jsonify_not_legacy(self):
        s = Serializer()

        example_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5/hPwAIAgL/4d1j8wAAAABJRU5ErkJggg=="

        test_bytes = s.serialize('image/png', example_png)
        assert type(test_bytes) == bytes

        test_str = s.deserialize('image/png', test_bytes)

        test_str_2 = s.jsonify('image/png', test_str)
        assert test_str_2 == f"data:image/jpeg;base64,{test_str}"
