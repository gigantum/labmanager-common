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
from typing import Any

from lmcommon.activity.serializers import text


class Serializer(object):
    """Class to manage serialization of detail objects"""

    def __init__(self) -> None:
        """ Load the database for the specified labbook
        """
        self.serializers = {"text/plain": text.PlainSerializer(),
                            "text/markdown": text.MarkdownSerializer()}

    def jsonify(self, mime_type: str, data: Any) -> Any:
        """Method to jsonify an arbitrary data object

        Args:
            mime_type(str): the mime type of the object
            data(Any): A python object containing the data

        Returns:
            any
        """
        if mime_type not in self.serializers:
            raise ValueError(f"MIME type {mime_type} not supported.")

        return self.serializers[mime_type].jsonify(data)

    def serialize(self, mime_type: str, data: Any) -> bytes:
        """Method to serialize an arbitrary data object

        Args:
            mime_type(str): the mime type of the object
            data(Any): A python object containing the data

        Returns:
            bytes
        """
        if mime_type not in self.serializers:
            raise ValueError(f"MIME type {mime_type} not supported.")

        return self.serializers[mime_type].serialize(data)

    def deserialize(self, mime_type: str, data: bytes) -> Any:
        """Method to deserialize an arbitrary data object

        Args:
            mime_type(str): the mime type of the object
            data(bytes): Bytes to deserialize into an object

        Returns:
            Any
        """
        if mime_type not in self.serializers:
            raise ValueError(f"MIME type {mime_type} not supported.")

        return self.serializers[mime_type].deserialize(data)
