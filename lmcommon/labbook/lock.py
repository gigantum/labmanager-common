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
from contextlib import contextmanager
from lmcommon.logging import LMLogger
from lmcommon.labbook import LabBook
import time

from redis import StrictRedis
import redis_lock

logger = LMLogger.get_logger()


@contextmanager
def lock_labbook(labbook: LabBook):
    """A context manager for locking labbook operations that is decorator compatible

    Manages the lock process along with catching and logging exceptions that may occur

    """
    lock: redis_lock.Lock = None
    try:
        config = labbook.labmanager_config.config['lock']

        # Get a redis client
        redis_client = StrictRedis(host=config['redis']['host'],
                                   port=config['redis']['port'],
                                   db=config['redis']['db'])

        # Get a lock
        # Todo switch to labbook identifier when available
        # key = labbook.key()
        key = 'labbook_lock'
        lock = redis_lock.Lock(redis_client, key,
                               expire=config['expire'],
                               auto_renewal=config['auto_renewal'],
                               strict=config['redis']['false'])

        if lock.acquire(timeout=config['timeout']):
            # Do the work
            start_time = time.time()
            yield
            if (time.time() - start_time) > config['expire']:
                logger.warning(f"LabBook task took more than {config['expire']}s. File locking possibly invalid.")
        else:
            raise IOError(f"Could not acquire LabBook lock within {LOCK_TIMEOUT} seconds.")

    except Exception as e:
        logger.error(e)
        raise
    finally:
        # Release the Lock
        if lock:
            lock.release()
