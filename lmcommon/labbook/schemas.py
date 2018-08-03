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
from typing import Any, Dict, Optional
from schema import Schema, SchemaError

from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()

# The current LabBook schema version
CURRENT_SCHEMA = 2

LABBOOK_SCHEMA_VERSIONS = {
    # Note: Each time a new schema version is needed, add it into this dictionary
    # with its version number as its key.
    #
    # These are all the supported schemas
    1: {
        'labbook': {
            'id': str,
            'name': str,
            'description': str
        },
        'owner': {
            'username': str
        },
        'schema': int
    },
    2: {
        'cuda_version': str,
        'labbook': {
            'id': str,
            'name': str,
            'description': str
        },
        'owner': {
            'username': str
        },
        'schema': int
    },
}

# TODO: Add validation methods and formalized schemas for Environment Component Definitions


def validate_labbook_schema(schema_version: int, lb_data: Optional[Dict[str, Any]]) -> bool:
    """ Validate a labbook's data against a known schema. Returns true if schema matches
    version appropriately.

    Args:
        schema_version(int): Schema version to validate against
        lb_data(Dict): Labbook's data dict.

    Returns:
        bool: True if schema validates, False otherwise.

    """
    if not schema_version or schema_version not in LABBOOK_SCHEMA_VERSIONS.keys():
        logger.error(f"schema_version {schema_version} not found in schema versions")
        return False

    if not lb_data:
        logger.error(f"lb_data is None or empty")
        return False

    schema = Schema(LABBOOK_SCHEMA_VERSIONS[schema_version])
    try:
        schema.validate(lb_data)
        return True
    except SchemaError as e:
        logger.error(e)
        return False
