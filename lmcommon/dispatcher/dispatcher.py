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
import datetime
import pickle

import rq_scheduler
import redis
import rq

import lmcommon.dispatcher.jobs
from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()


class Dispatcher(object):
    """Class to serve as an interface to the background job processing service.
    """

    DEFAULT_JOB_QUEUE = 'labmanager_jobs'
    SCHEDULER_JOB_QUEUE = 'labmanager_scheduled'

    def __init__(self, queue_name=DEFAULT_JOB_QUEUE, scheduled_queue_name=SCHEDULER_JOB_QUEUE):
        self._redis_conn = redis.Redis()
        self._job_queue = rq.Queue(queue_name, connection=self._redis_conn)
        self._scheduler = rq_scheduler.Scheduler(connection=self._redis_conn)

    @staticmethod
    def _is_job_in_registry(method_reference):
        """Return True if `method_reference` in the set of acceptable background jobs. """
        job_list = [getattr(lmcommon.dispatcher.jobs, n) for n in dir(lmcommon.dispatcher.jobs)]
        return any([method_reference == n for n in job_list])

    @property
    def all_jobs(self):
        """Return a list of dicts containing information about all jobs in the backend. """
        redis_keys = self._redis_conn.keys("rq:job:*")

        return {q.decode(): self.query_task(q) for q in redis_keys}

    @property
    def failed_jobs(self):
        """Return all explicity-failed jobs. """
        jobs = self.all_jobs
        failed = {}
        # Note - there might be a more clever one-liner to do this, but this is straightforward.
        for k in jobs.keys():
            if jobs[k]['status'] == 'failed':
                failed[k] = jobs[k]

        return failed

    @property
    def completed_jobs(self):
        """Return a list of all jobs that are considered "complete" (i.e., no error). """
        jobs = self.all_jobs
        complete = {}
        # Note - there might be a more clever one-liner to do this, but this is straightforward.
        for k in jobs.keys():
            if jobs[k]['status'] == 'finished':
                complete[k] = jobs[k]

        return complete

    def query_task(self, key) -> dict:
        """Return a dictionary of metadata pertaining to the given task's Redis key.

        Args:
            key(str): Redis key of job in format of rq:job:<unique-id>

        Returns:
            dict
        """
        logger.debug("Querying for task {}".format(key))

        # The job_dict is returned from redis is contains strictly binary data, to be more usable
        # it needs to be parsed and loaded as proper data types. The decoded data is stored in the
        # `decoded_dict`.
        job_dict = self._redis_conn.hgetall(key)
        decoded_dict = {}

        # Fetch the RQ job. There needs to be a little processing done on it first.
        rq_job = rq.job.Job.fetch(str(key).split(':')[-1].replace("'", ''), connection=redis.Redis())

        # Build the properly decoded dict, which will be returned.
        for k in job_dict.keys():
            decoded_dict[k.decode('utf-8')] = getattr(rq_job, k.decode())

        return decoded_dict

    def schedule_task(self, method_reference, args=(), kwargs={}, scheduled_time=None, repeat=0,
                      interval=None) -> str:
        """Schedule at task to run at a particular time in the future, and/or with certain recurrence.

        Args:
            method_reference(Callable): The method in dispatcher.jobs to run
            args(list): Arguments to method_reference
            kwargs(dict): Keyword Argument to method_reference
            scheduled_time(datetime.datetime): UTC timestamp of time to run this task, None indicates now
            repeat(int): Number of times to re-run the task (None indicates repeat forever)
            interval(int): Seconds between invocations of the task (None indicates no recurrence)

        Returns:
            str: unique key of dispatched task
        """
        # Only allowed and certified methods may be dispatched to the background.
        # These methods are in the jobs.py package.
        if not Dispatcher._is_job_in_registry(method_reference):
            raise ValueError("Method {} not in available registry".format(method_reference.__name__))

        if type(scheduled_time) not in (datetime.datetime, type(None)):
            raise ValueError("scheduled_time `{}` must be a Datetime object or None".format(scheduled_time))

        if type(repeat) not in (int, type(None)) or repeat < 0:
            raise ValueError('repeat `{}` must be a non-negative integer or none'.format(repeat))

        if type(interval) not in (int, type(None)) or interval <= 0:
            raise ValueError('interval `{}` must be a positive integer or none'.format(repeat))

        job_ref = self._scheduler.schedule(scheduled_time=scheduled_time,
                                           func=method_reference,
                                           args=args,
                                           kwargs=kwargs,
                                           interval=interval,
                                           repeat=repeat)

        logger.info("Scheduled job `{}`, job={}".format(method_reference.__name__, str(job_ref)))

        # job_ref.key is in bytes.. should be decode()-ed to form a python string.
        return job_ref.key.decode()

    def dispatch_task(self, method_reference, args=(), kwargs={}) -> str:
        """Dispatch new task to run in background, which runs as soon as it can.

        Args:
            method_reference(Callable): The method in dispatcher.jobs to run
            args(list): Arguments to method_reference
            kwargs(dict): Keyword Argument to method_reference

        Returns:
            str: unique key of dispatched task
        """

        if not callable(method_reference):
            raise ValueError("method_reference must be callable")

        # Only allowed and certified methods may be dispatched to the background.
        # These methods are in the jobs.py package.
        if not Dispatcher._is_job_in_registry(method_reference):
            raise ValueError("Method {} not in available registry".format(method_reference.__name__))

        job_ref = self._job_queue.enqueue(method_reference, args=args, kwargs=kwargs)
        logger.info(
            "Dispatched job `{}` to queue '{}', job={}".format(method_reference.__name__, self._job_queue.name,
                                                               str(job_ref)))

        # job.key is in bytes.. should be decode()-ed to form a python string.
        return job_ref.key.decode()
