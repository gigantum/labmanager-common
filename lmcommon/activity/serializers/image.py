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
from typing import Any, Optional


class Base64ImageSerializer(MimeSerializer):
    """Class for serializing base64 encoded images"""
    extension: Optional[str] = None

    def jsonify(self, data: str) -> str:
        # Just the base64 str when jsonifying since it will serialize properly while pre-pending the data tag
        return f"data:image/{self.extension};base64,{data}"

    def serialize(self, data: Any) -> bytes:
        # Byte encode the string
        # TODO: base64 decode, load image, convert to bytes - will result in better compression and allow for resizing
        return data.encode('utf-8')

    def deserialize(self, data: bytes) -> str:
        # Decode the bytes to a string object
        return data.decode('utf-8')


class PngImageSerializer(Base64ImageSerializer):
    """Class for serializing png images"""
    extension = "png"


class JpegImageSerializer(Base64ImageSerializer):
    """Class for serializing png images"""
    extension = "jpeg"


class BmpImageSerializer(Base64ImageSerializer):
    """Class for serializing png images"""
    extension = "bmp"


class GifImageSerializer(Base64ImageSerializer):
    """Class for serializing png images"""
    extension = "gif"
