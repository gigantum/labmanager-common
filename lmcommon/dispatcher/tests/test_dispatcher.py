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
import getpass
import threading
import json
import time
import shutil
import pytest
import datetime

import multiprocessing
import tempfile
import uuid
import os

import rq_scheduler
import rq

from lmcommon.imagebuilder import ImageBuilder
from lmcommon.configuration import get_docker_client
from lmcommon.environment import ComponentManager, RepositoryManager
from lmcommon.dispatcher import Dispatcher
from lmcommon.labbook import LabBook

import lmcommon.dispatcher.jobs as bg_jobs


@pytest.fixture()
def temporary_worker():
    """A pytest fixture that creates a temporary directory and a config file to match. Deletes directory after test"""
    def run_worker():
        with rq.Connection():
            qs = 'labmanager_unittests'
            w = rq.Worker(qs)
            w.work()

    # This task is used to kill the worker. Sometimes if tests fail the worker runs forever and
    # holds up the entire process. This gives each test 25 seconds to run before killing the worker
    # and forcing the test to fail.
    def watch_proc(p):
        count = 0
        while count < 15:
            count = count + 1
            time.sleep(1)

        try:
            p.terminate()
        except:
            pass

    worker_proc = multiprocessing.Process(target=run_worker)
    worker_proc.start()

    watchdog_thread = threading.Thread(target=watch_proc, args=(worker_proc,))
    watchdog_thread.start()

    dispatcher = Dispatcher('labmanager_unittests')
    yield worker_proc, dispatcher


@pytest.fixture()
def mock_config_file():
    """A pytest fixture that creates a temporary directory and a config file to match. Deletes directory after test"""
    # Create a temporary working directory
    temp_dir = os.path.join(tempfile.tempdir, uuid.uuid4().hex)
    os.makedirs(temp_dir)

    with tempfile.NamedTemporaryFile(mode="wt") as fp:
        # Write a temporary config file
        fp.write("""core:
  team_mode: false 

environment:
  repo_url:
    - "https://github.com/gig-dev/environment-components.git"

git:
  backend: 'filesystem'
  working_directory: '{}'""".format(temp_dir))
        fp.seek(0)

        yield fp.name, temp_dir  # provide the fixture value

    # Remove the temp_dir
    shutil.rmtree(temp_dir)


class TestDispatcher(object):

    def test_unallowed_task_not_run(self, temporary_worker):
        w, d = temporary_worker

        def oh_no(cats, dogs, bees):
            raise RuntimeError("This should never happen!")

        try:
            # Only allowed tasks may be dispatched.
            d.dispatch_task(oh_no, args=('x', 1, None))
        except ValueError as e:
            assert 'not in available' in str(e), "Attempt should result in ValueError"
        else:
            assert False, "Method not in registry should not have been allowed to run"

        w.terminate()

    def test_simple_task(self, temporary_worker):
        w, d = temporary_worker
        job_ref = d.dispatch_task(bg_jobs.test_exit_success)
        time.sleep(1)

        res = d.query_task(job_ref)
        assert res
        assert res.get('status') == 'finished'
        assert res.get('result') == 0

        w.terminate()

    def test_failing_task(self, temporary_worker):
        w, d = temporary_worker
        job_ref = d.dispatch_task(bg_jobs.test_exit_fail)
        time.sleep(1)

        res = d.query_task(job_ref)
        assert res
        assert res.get('status') == 'failed'

        w.terminate()

    def test_query_failed_tasks(self, temporary_worker):
        w, d = temporary_worker
        job_ref = d.dispatch_task(bg_jobs.test_exit_fail)

        time.sleep(1)

        assert job_ref in d.failed_jobs
        assert job_ref not in d.completed_jobs
        w.terminate()

    def test_query_complete_tasks(self, temporary_worker):
        w, d = temporary_worker
        job_ref = d.dispatch_task(bg_jobs.test_exit_success)

        time.sleep(1)

        assert job_ref in d.completed_jobs
        assert job_ref not in d.failed_jobs

    @pytest.mark.skipif(getpass.getuser() == 'circleci', reason="Cannot build images on CircleCI")
    def test_build_docker_image(self, temporary_worker, mock_config_file):
        w, d = temporary_worker

        erm = RepositoryManager(mock_config_file[0])
        erm.update_repositories()
        erm.index_repositories()

        # Create a labook
        lb = LabBook(mock_config_file[0])

        labbook_dir = lb.new(name="catbook-test-dockerbuild", description="Testing docker building.",
                             owner={"username": "test"})

        # Create Component Manager
        cm = ComponentManager(lb)

        # Add a component
        cm.add_component("base_image", "gig-dev_environment-components", "gigantum", "ubuntu1604-python3", "0.4")
        cm.add_component("dev_env", "gig-dev_environment-components", "gigantum", "jupyter-ubuntu", "0.1")

        ib = ImageBuilder(lb.root_dir)
        unit_test_tag = "background-unit-test-delete-this"

        docker_kwargs = {
            'path': os.path.join(labbook_dir, '.gigantum', 'env'),
            'tag': unit_test_tag ,
            'pull': True,
            'nocache': True
        }

        job_ref = d.dispatch_task(bg_jobs.build_docker_image, kwargs=docker_kwargs)

        elapsed_time = 0
        while True:
            status = d.query_task(job_ref)['status']
            print(status)
            if status in ['success', 'failed', 'finished']:
                break
            if elapsed_time > 30:
                w.terminate()
                assert False, "timed out {}".format(status)
            elapsed_time = elapsed_time + 1
            time.sleep(1)

        w.terminate()

        res = d.query_task(job_ref)
        assert res
        assert res.get('status') == 'finished'

    @pytest.mark.skipif(getpass.getuser() == 'circleci', reason="Cannot build images on CircleCI")
    def test_start_and_stop_docker_container(self, temporary_worker, mock_config_file):
        # start_docker_container(docker_image_id, exposed_ports, volumes_dict) -> str:
        w, d = temporary_worker

        erm = RepositoryManager(mock_config_file[0])
        erm.update_repositories()
        erm.index_repositories()

        # Create a labook
        lb = LabBook(mock_config_file[0])

        labbook_dir = lb.new(name="catbook-test-dockerbuild", description="Testing docker building.",
                             owner={"username": "test"})

        # Create Component Manager
        cm = ComponentManager(lb)

        # Add a component
        cm.add_component("base_image", "gig-dev_environment-components", "gigantum", "ubuntu1604-python3", "0.4")
        cm.add_component("dev_env", "gig-dev_environment-components", "gigantum", "jupyter-ubuntu", "0.1")

        ib = ImageBuilder(lb.root_dir)
        unit_test_tag = "background-unit-test-delete-this"

        ## Start building image.

        docker_kwargs = {
            'path': os.path.join(labbook_dir, '.gigantum', 'env'),
            'tag': unit_test_tag,
            'pull': True,
            'nocache': True
        }

        client = get_docker_client()
        img_list = client.images.list()

        try:
            client.images.remove("{}".format(unit_test_tag))
        except:
            pass

        m = {'method': 'build_image',
             'labbook': 'test-test-catbook-test-dockerbuild'}

        job_ref = d.dispatch_task(bg_jobs.build_docker_image, kwargs=docker_kwargs, metadata=m)

        j = d.query_task(job_ref)
        assert 'meta' in j.keys()
        assert j.get('meta').get('labbook') == 'test-test-catbook-test-dockerbuild'

        elapsed_time = 0
        while True:
            status = d.query_task(job_ref)['status']
            print(status)
            if status in ['success', 'failed', 'finished']:
                break
            if elapsed_time > 30:
                w.terminate()
                assert False, "timed out {}".format(status)
            elapsed_time = elapsed_time + 1
            time.sleep(1)

        #w.terminate()

        res = d.query_task(job_ref)
        assert res
        assert res.get('status') == 'finished'

        ## Finish building image

        docker_kwargs = {
            'docker_image_id': "{}".format(unit_test_tag),
            'ports': {},
            'volumes': {}
        }

        ## Start the docker container, and then wait till it's done.
        start_ref = d.dispatch_task(bg_jobs.start_docker_container, kwargs=docker_kwargs)

        elapsed_time = 0
        while True:
            status = d.query_task(start_ref)['status']
            print(status)
            if status in ['success', 'failed', 'finished']:
                break
            if elapsed_time > 8:
                w.terminate()
                assert False, "timed out {}".format(status)
            elapsed_time = elapsed_time + 1
            time.sleep(1)

        res = d.query_task(start_ref)
        assert res
        assert res.get('status') == 'finished'

        ## Stop the docker container, and wait until that is done.
        stop_ref = d.dispatch_task(bg_jobs.stop_docker_container, args=(unit_test_tag,))

        elapsed_time = 0
        while True:
            status = d.query_task(stop_ref)['status']
            print(status)
            if status in ['success', 'failed', 'finished']:
                break
            if elapsed_time > 8:
                w.terminate()
                assert False, "timed out {}".format(status)
            elapsed_time = elapsed_time + 1
            time.sleep(1)

        res = d.query_task(stop_ref)
        assert res
        assert res.get('status') == 'finished'

        w.terminate()

    def test_simple_scheduler(self, temporary_worker, mock_config_file):
        # Run a simple tasks that increments the integer contained in a file.
        w, d = temporary_worker

        path = "/tmp/labmanager-unit-test-{}".format(os.getpid())
        if os.path.exists(path):
            os.remove(path)

        d.schedule_task(bg_jobs.test_incr, args=(path,), repeat=3, interval=2)

        time.sleep(8)

        try:
            with open(path) as fp:
                assert json.load(fp)['amt'] == 3
        except Exception as e:
            raise e
        finally:
            pass

    def test_run_only_once(self, temporary_worker, mock_config_file):
        # Assert that this method only gets called once.
        w, d = temporary_worker

        path = "/tmp/labmanager-unit-test-{}".format(os.getpid())
        if os.path.exists(path):
            os.remove(path)

        future_t = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)
        jr = d.schedule_task(bg_jobs.test_incr, scheduled_time=future_t, args=(path,), repeat=0)

        time.sleep(4)

        try:
            with open(path) as fp:
                assert json.load(fp)['amt'] == 1
        except Exception as e:
            raise e
        finally:
            w.terminate()
            pass

    def test_schedule_with_repeat_is_zero(self, temporary_worker, mock_config_file):
        # When repeat is zero, it should run only once.
        w, d = temporary_worker

        path = "/tmp/labmanager-unit-test-{}".format(os.getpid())
        if os.path.exists(path):
            os.remove(path)

        try:
            jr = d.schedule_task(bg_jobs.test_incr, args=(path,), repeat=0, interval=4)
            time.sleep(6)
            n = d.unschedule_task(jr)
            time.sleep(5)
            with open(path) as fp:
                assert json.load(fp)['amt'] in [1], "When repeat=0, the task should run only once."
        finally:
            w.terminate()

    def test_unschedule_task(self, temporary_worker, mock_config_file):
        w, d = temporary_worker

        path = "/tmp/labmanager-unit-test-{}".format(os.getpid())
        if os.path.exists(path):
            os.remove(path)

        try:
            future_t = datetime.datetime.utcnow() + datetime.timedelta(seconds=5)
            jr = d.schedule_task(bg_jobs.test_incr, scheduled_time=future_t, args=(path,), repeat=4, interval=1)
            time.sleep(2)
            n = d.unschedule_task(jr)
            assert n, "Task should have been cancelled, instead it was not found."
            time.sleep(5)
            assert not os.path.exists(path=path)
        finally:
            w.terminate()

    def test_unschedule_midway_through(self, temporary_worker, mock_config_file):
        w, d = temporary_worker

        path = "/tmp/labmanager-unit-test-{}".format(os.getpid())
        if os.path.exists(path):
            os.remove(path)

        try:
            future_t = None  # i.e., start right now.
            jr = d.schedule_task(bg_jobs.test_incr, scheduled_time=future_t, args=(path,), repeat=6, interval=5)
            time.sleep(8)
            n = d.unschedule_task(jr)
            assert n, "Task should have been cancelled, instead it was not found."
            time.sleep(5)
            with open(path) as fp:
                assert json.load(fp)['amt'] in [2]
        finally:
            w.terminate()
