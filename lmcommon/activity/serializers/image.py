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
import base64
from PIL import Image
import io


class Base64ImageSerializer(MimeSerializer):
    """Class for serializing base64 encoded images"""
    def __init__(self, mime_type):
        if mime_type in ['image/png', 'image/jpg', 'image/jpeg', 'image/bmp']:
            self.mime_type = mime_type
        else:
            raise ValueError(f"Unsupported mime type: {mime_type}")

    def jsonify(self, data: str) -> str:
        # Just the base64 str when jsonifying since it will serialize properly while pre-pending the data tag
        if data[:5] == "iVBOR":
            # If the data has a png header, it's a legacy image that has not been re-encoded as a jpeg
            return f"data:image/png;base64,{data}"
        else:
            return f"data:image/jpeg;base64,{data}"

    def serialize(self, data: Any) -> bytes:
        # Base64 decode string to bytes
        data_bytes = base64.b64decode(data.encode('utf-8'))

        # Load into image
        image_obj = Image.open(io.BytesIO(data_bytes))

        # Resize if needed
        image_obj.thumbnail((1024, 1024))

        image_bytes = io.BytesIO()
        if image_obj.mode == "RGBA":
            # Discard alpha if needed
            image_obj.load()

            rgb_img = Image.new("RGB", image_obj.size, (255, 255, 255))
            rgb_img.paste(image_obj, mask=image_obj.split()[3])

            # Serialize to bytes, encoded as jpeg
            rgb_img.save(image_bytes, format='JPEG', quality=90, optimize=True)
        else:
            # Serialize to bytes, encoded as jpeg
            image_obj.save(image_bytes, format='JPEG', quality=90, optimize=True)

        return image_bytes.getvalue()

    def deserialize(self, data: bytes) -> str:
        # Decode the bytes from store to base64 encoded image string
        try:
            decoded = data.decode("utf-8")
            # If you can decode directly, you've got a legacy image that is stored base64 encoded
            return decoded
        except UnicodeDecodeError:
            # If you fail to decode directly, it means you have a bytestream from the activity DB
            return base64.b64encode(data).decode("utf-8")


class GifImageSerializer(MimeSerializer):
    """Class for serializing gif images that are already base64 encoded strings

    Can't re-encode because multiple frames can be present.
    """
    def __init__(self):
        self.mime_type = "image/gif"

    def jsonify(self, data: str) -> str:
        # Just the base64 str when jsonifying since it will serialize properly while pre-pending the data tag
        return f"data:image/gif;base64,{data}"

    def serialize(self, data: Any) -> bytes:
        # Byte encode the string
        return data.encode('utf-8')

    def deserialize(self, data: bytes) -> str:
        # Decode the bytes to base64 encoded png
        return data.decode('utf-8')
