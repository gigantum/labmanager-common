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

import time
import subprocess
from typing import List
from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()


def call_subprocess(cmd_tokens: List[str], cwd: str, check: bool = True) -> str:
    """Execute a subprocess call and properly benchmark and log

    Args:
        cmd_tokens: List of command tokens, e.g., ['ls', '-la']
        cwd: Current working directory
        check: Raise exception if command fails

    Returns:
        Decoded stdout of called process after completing

    Raises:
        subprocess.CalledProcessError
    """
    logger.debug(f"Executing `{' '.join(cmd_tokens)}` in {cwd}")
    start_time = time.time()
    try:
        r = subprocess.run(cmd_tokens, cwd=cwd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, check=check)
        finish_time = time.time()
        elapsed_time = finish_time - start_time
        logger.debug(f"Finished command `{' '.join(cmd_tokens)}` in {elapsed_time}s")
        if elapsed_time > 1.0:
            logger.warning(f"Successful command `{' '.join(cmd_tokens)}` took {elapsed_time}s")
        return (r.stdout or b"").decode()
    except subprocess.CalledProcessError as x:
        fail_time = time.time() - start_time
        logger.error(f"Command failed `{' '.join(cmd_tokens)}` after {fail_time}s: stderr={x.stderr}")
        raise
