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

import multiprocessing
import argparse
import os

from lmcommon.logging import LMLogger
from rq import Connection, Queue, Worker

logger = LMLogger.get_logger()


def start_rq_worker(queue_name: str) -> None:
    try:
        with Connection():
            q = Queue(name=queue_name)
            logger.info("Starting RQ worker for queue `{}` in pid {}".format(queue_name, os.getpid()))
            Worker(q).work()
    except Exception as e:
        logger.exception("Worker in pid {} failed with exception {}".format(os.getpid(), e))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run any number of RQ workers')
    parser.add_argument('count', type=int, help='Number of workers')

    try:
        args = parser.parse_args()
    except Exception as e:
        logger.exception(e)
        raise

    logger.info("Starting {} RQ workers...".format(args.count))
    procs = []
    for i in range(0, args.count):
        p = multiprocessing.Process(target=start_rq_worker, args=('labmanager_jobs',))
        p.start()
        procs.append(p)

    logger.info("Started {} worker processes".format(len(procs)))
    for p in procs:
        p.join()

