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
from datetime import datetime
from typing import (Any, Callable, cast, Dict, List, Optional, Tuple)

import redis
import rq
import rq_scheduler

import lmcommon.dispatcher.jobs
from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()


class JobKey(object):
    """ Represents a key for a background job in Redis. """
    def __init__(self, key: str) -> None:
        try:
            self._validate(key)
        except AssertionError as e:
            logger.error(e)
            raise
        self._key_str: str = key

    def __str__(self) -> str:
        return self._key_str

    def __repr__(self):
        return self._key_str

    def __eq__(self, other: object) -> bool:
        return type(other) == type(self) and str(self) == str(other)

    def _validate(self, key):
        assert key, f"Key '{key}' cannot be None or empty"
        assert isinstance(key, str), f"`key` must be str, not {type(key)}"
        assert len(key.split(':')) == 3, "Key must be in format of `rq:job:<uuid>`"

    @property
    def key_str(self):
        return self._key_str


class JobStatus(object):
    """ Represents a background job known to the backend processing system. """
    def __init__(self, redis_dict: Dict[str, object]) -> None:
        self.job_key: JobKey = JobKey(cast(str, redis_dict['_key']))
        self.status: Optional[str] = cast(str, redis_dict.get('status'))
        self.result: Optional[object] = cast(str, redis_dict.get('result'))
        self.description: Optional[str] = cast(str, redis_dict.get('description'))
        self.meta: Dict[str, str] = cast(Dict[str, str], redis_dict.get('meta') or {})
        self.started_at: Optional[datetime] = cast(datetime, redis_dict.get('started_at'))
        self.finished_at: Optional[datetime] = cast(datetime, redis_dict.get('finished_at'))

    def __str__(self) -> str:
        return f'<BackgroundJob {str(self.job_key)}>'

    def __eq__(self, other: object) -> bool:
        return type(other) == type(self) and str(self) == str(other)


class Dispatcher(object):
    """Class to serve as an interface to the background job processing service.
    """

    DEFAULT_JOB_QUEUE: str = 'labmanager_jobs'

    def __init__(self, queue_name: str = DEFAULT_JOB_QUEUE) -> None:
        self._redis_conn = redis.Redis()
        self._job_queue = rq.Queue(queue_name, connection=self._redis_conn)
        self._scheduler = rq_scheduler.Scheduler(queue_name=queue_name, connection=self._redis_conn)

    def __str__(self) -> str:
        return "<Dispatcher: queue={}>".format(self._job_queue)

    @staticmethod
    def _is_job_in_registry(method_reference: Callable) -> bool:
        """Return True if `method_reference` in the set of acceptable background jobs. """
        job_list = [getattr(lmcommon.dispatcher.jobs, n) for n in dir(lmcommon.dispatcher.jobs)]
        return any([method_reference == n for n in job_list])

    @property
    def all_jobs(self) -> List[JobStatus]:
        """Return a list of dicts containing information about all jobs in the backend. """
        redis_keys = self._redis_conn.keys("rq:job:*")

        return [self.query_task(JobKey(q.decode())) for q in redis_keys]

    @property
    def failed_jobs(self) -> List[JobStatus]:
        """Return all explicity-failed jobs. """
        return [job for job in self.all_jobs if job.status == 'failed']

    @property
    def finished_jobs(self) -> List[JobStatus]:
        """Return a list of all jobs that are considered "complete" (i.e., no error). """
        return [job for job in self.all_jobs if job.status == 'finished']

    def get_jobs_for_labbook(self, labbook_key: str) -> List[JobStatus]:
        """Return all background job keys pertaining to the given labbook, as indexed by its root_directory. """
        def is_match(job):
            return job.meta and job.meta.get('labbook') == labbook_key

        labbook_jobs = [job for job in self.all_jobs if is_match(job)]
        if not labbook_jobs:
            logger.warning(f"No background jobs found for labbook `{labbook_key}`")

        return labbook_jobs

    def query_task(self, job_key: JobKey) -> JobStatus:
        """Return a JobStatus containing all info pertaining to background job.

        Args:
            job_key(JobKey): JobKey containing redis key of job.

        Returns:
            JobStatus
        """
        logger.debug("Querying for task {}".format(job_key))

        # The job_dict is returned from redis is contains strictly binary data, to be more usable
        # it needs to be parsed and loaded as proper data types. The decoded data is stored in the
        # `decoded_dict`.
        job_dict = self._redis_conn.hgetall(job_key.key_str)
        decoded_dict = {}

        # Fetch the RQ job. There needs to be a little processing done on it first.
        rq_job = rq.job.Job.fetch(job_key.key_str.split(':')[-1].replace("'", ''), connection=redis.Redis())

        # Build the properly decoded dict, which will be returned.
        for k in job_dict.keys():
            decoded_dict[k.decode('utf-8')] = getattr(rq_job, k.decode())

        decoded_dict.update({'_key': job_key.key_str})
        return JobStatus(decoded_dict)

    def unschedule_task(self, job_key: JobKey) -> bool:
        """Cancel a scheduled task. Note, this does NOT cancel "dispatched" tasks, only ones created
           via `schedule_task`.

        Args:
            job_key(str): ID of the task that was returned via `schedule_task`.

        Returns:
            bool: True if task scheduled successfully, False if task not found.
        """

        if not job_key:
            raise ValueError("job_key cannot be None or empty")

        if not type(job_key) == JobKey:
            raise ValueError("job_ikey must be type JobKey")

        # Encode job_id as byes from regular string, strip off the "rq:job" prefix.
        enc_job_id = job_key.key_str.split(':')[-1].encode()
        
        if enc_job_id in self._scheduler:
            logger.info("Job (encoded id=`{}`) found in scheduler, cancelling".format(enc_job_id))
            self._scheduler.cancel(enc_job_id)
            logger.info("Unscheduled job (encoded id=`{}`)".format(enc_job_id))
            return True
        else:
            logger.warning("Job (encoded id=`{}`) NOT FOUND in scheduler, nothing to cancel".format(enc_job_id))
            return False

    def schedule_task(self, method_reference: Callable, args: Optional[Tuple[Any]] = None,
                      kwargs: Optional[Dict[str, Any]] = None,
                      scheduled_time: Optional[datetime] = None, repeat: Optional[int] = 0,
                      interval: Optional[int] = None) -> JobKey:
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
            raise ValueError("Method `{}` not in available registry".format(method_reference.__name__))

        job_args = args or tuple()
        job_kwargs = kwargs or {}
        rq_job_ref = self._scheduler.schedule(scheduled_time=scheduled_time or datetime.utcnow(),
                                              func=method_reference,
                                              args=job_args,
                                              kwargs=job_kwargs,
                                              interval=interval,
                                              repeat=repeat)

        logger.info(f"Scheduled job `{method_reference.__name__}`, job={str(rq_job_ref)}")

        # job_ref.key is in bytes.. should be decode()-ed to form a python string.
        return JobKey(rq_job_ref.key.decode())

    def dispatch_task(self, method_reference: Callable, args: Tuple[Any, ...] = None, kwargs: Dict[str, Any] = None,
                      metadata: Dict[str, Any] = None, persist: bool = False) -> JobKey:
        """Dispatch new task to run in background, which runs as soon as it can.

        Args:
            method_reference(Callable): The method in dispatcher.jobs to run
            args(list): Arguments to method_reference
            kwargs(dict): Keyword Argument to method_reference
            metadata(dict): Optional dict of metadata
            persist(bool): Never timeout if True, otherwise abort after 5 minutes.

        Returns:
            str: unique key of dispatched task
        """

        if not callable(method_reference):
            raise ValueError("method_reference must be callable")

        # Only allowed and certified methods may be dispatched to the background.
        # These methods are in the jobs.py package.
        if not Dispatcher._is_job_in_registry(method_reference):
            raise ValueError("Method {} not in available registry".format(method_reference.__name__))

        if not args:
            args = ()

        if not kwargs:
            kwargs = {}

        if not metadata:
            metadata = {}

        if persist:
            # Currently, one month.
            timeout = '730h'
        else:
            timeout = '45m'

        logger.info(
            f"Dispatching {'persistent' if persist else 'ephemeral'} task `{method_reference.__name__}` to queue")

        try:
            rq_job_ref = self._job_queue.enqueue(method_reference, args=args, kwargs=kwargs, timeout=timeout)
        except Exception as e:
            logger.error("Cannot enqueue job `{}`: {}".format(method_reference.__name__, e))
            raise

        rq_job_ref.meta = metadata
        rq_job_ref.save_meta()
        rq_job_key_str = rq_job_ref.key.decode()
        logger.info(
            "Dispatched job `{}` to queue '{}', job={}".format(method_reference.__name__, self._job_queue.name,
                                                               rq_job_key_str))

        try:
            assert rq_job_key_str
            jk = JobKey(rq_job_key_str)
        except Exception as e:
            logger.exception(e)
            raise

        # job.key is in bytes.. should be decode()-ed to form a python string.
        return jk
