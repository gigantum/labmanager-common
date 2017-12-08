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
from lmcommon.activity.serializers.mime import MimeSerializer
from typing import Any


class PlainSerializer(MimeSerializer):
    """Class for serializing plain text"""

    def jsonify(self, data: str) -> str:
        # Just return the text when jsonifying since it will serialize properly
        return data

    def serialize(self, data: Any) -> bytes:
        # Byte encode the string
        return data.encode('utf-8')

    def deserialize(self, data: bytes) -> str:
        # Decode the bytes to a string object
        return data.decode('utf-8')


class MarkdownSerializer(MimeSerializer):
    """Class for serializing markdown text"""

    def jsonify(self, data: str) -> str:
        # Just return the text when jsonifying since it will serialize properly
        return data

    def serialize(self, data: Any) -> bytes:
        # Byte encode the string
        return data.encode('utf-8')

    def deserialize(self, data: bytes) -> str:
        # Decode the bytes to a string object
        return data.decode('utf-8')

