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
import abc
from typing import Any


class MimeSerializer(metaclass=abc.ABCMeta):
    """Abstract class for serializers for specific MIME types"""

    @abc.abstractmethod
    def jsonify(self, data: Any) -> Any:
        """Method to convert object to something that is able to be sent in a JSON object

        E.g., no op for text, serialization and base64 encoding for an image

        Args:
            data(any): Data to convert to something that is able to be encoded by JSON

        Returns:
            Any
        """
        raise NotImplemented

    @abc.abstractmethod
    def serialize(self, data: Any) -> bytes:
        """Method to serialize to binary, primarily for file storage

        Args:
            data(any): Data to convert to byte array

        Returns:
            bytes
        """
        raise NotImplemented

    @abc.abstractmethod
    def deserialize(self, data: bytes) -> Any:
        """Method to deserialize from byte array to object type

        Args:
            data(any): Byte array to convert

        Returns:
            Any
        """
        raise NotImplemented
