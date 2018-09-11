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
import importlib
import json
import os
import time
from typing import Optional
import subprocess
import shutil

from rq import get_current_job

from lmcommon.activity.monitors.devenv import DevEnvMonitorManager
from lmcommon.configuration import Configuration
from lmcommon.configuration.utils import call_subprocess
from lmcommon.labbook import LabBook
from lmcommon.logging import LMLogger
from lmcommon.workflows import sync_locally, GitWorkflow
from lmcommon.container.core import (build_docker_image as build_image,
                                     start_labbook_container as start_container,
                                     stop_labbook_container as stop_container)


# PLEASE NOTE -- No global variables!
#
# None of the following methods can use global variables.
# ANY use of globals will cause the following methods to fail.


def publish_labbook(labbook_path: str, username: str, access_token: str,
                    remote: Optional[str] = None, public: bool = False) -> None:
    p = os.getpid()
    logger = LMLogger.get_logger()
    logger.info(f"(Job {p}) Starting publish_labbook({labbook_path})")

    try:
        labbook: LabBook = LabBook()
        labbook.from_directory(labbook_path)

        wf = GitWorkflow(labbook)
        wf.publish(username=username, access_token=access_token, remote=remote or "origin",
                   public=public)
    except Exception as e:
        logger.exception(f"(Job {p}) Error on publish_labbook: {e}")
        raise


def sync_labbook(labbook_path: str, username: str, remote: str = "origin",
                 force: bool = False) -> int:
    p = os.getpid()
    logger = LMLogger.get_logger()
    logger.info(f"(Job {p}) Starting sync_labbook({labbook_path})")

    try:
        labbook: LabBook = LabBook()
        labbook.from_directory(labbook_path)

        wf = GitWorkflow(labbook)
        cnt = wf.sync(username=username, remote=remote, force=force)
        return cnt
    except Exception as e:
        logger.exception(f"(Job {p}) Error on sync_labbook: {e}")
        raise


def export_labbook_as_zip(labbook_path: str, lb_export_directory: str) -> str:
    """Return path to archive file of exported labbook. """
    p = os.getpid()
    logger = LMLogger.get_logger()
    logger.info(f"(Job {p}) Starting export_labbook_as_zip({labbook_path})")

    try:
        if not os.path.exists(os.path.join(labbook_path, '.gigantum')):
            # A gigantum labbook will contain a .gigantum hidden directory inside it.
            raise ValueError(f'(Job {p}) Directory at {labbook_path} does not appear to be a Gigantum LabBook')

        if not os.path.isdir(lb_export_directory):
            os.makedirs(lb_export_directory, exist_ok=True)
            # raise ValueError(f'(Job {p}) Export directory at `{lb_export_directory}` not found')

        labbook: LabBook = LabBook()
        labbook.from_directory(labbook_path)
        sync_locally(labbook)

        labbook_dir, _ = labbook.root_dir.rsplit(os.path.sep, 1)

        logger.info(f"(Job {p}) Exporting `{labbook.root_dir}` to `{lb_export_directory}`")
        if not os.path.exists(lb_export_directory):
            logger.warning(f"(Job {p}) Creating Lab Manager export directory at `{lb_export_directory}`")
            os.makedirs(lb_export_directory)

        lb_zip_name = f'{labbook.name}_{datetime.datetime.now().strftime("%Y-%m-%d")}'
        zip_path = os.path.join(lb_export_directory, lb_zip_name)

        # zip data
        call_subprocess(['zip', '-r', zip_path, labbook.name], cwd=labbook_dir, check=True)

        logger.info(f"(Job {p}) Finished exporting {str(labbook)} to {zip_path}.zip")
        return f"{zip_path}.zip"
    except Exception as e:
        logger.exception(f"(Job {p}) Error on export_labbook_as_zip: {e}")
        raise


def import_labboook_from_zip(archive_path: str, username: str, owner: str,
                             config_file: Optional[str] = None, base_filename: Optional[str] = None,
                             remove_source: bool = True) -> str:
    """Method to import a labbook from a zip file

    Args:
        archive_path(str): Path to the uploaded zip
        username(str): Username
        owner(str): Owner username
        config_file(str): Optional path to a labmanager config file
        base_filename(str): The desired basename for the upload, without an upload ID prepended
        remove_source(bool): Flag indicating if the source file should removed after import

    Returns:
        str: directory path of imported labbook
    """

    def update_meta(msg):
        job = get_current_job()
        if not job:
            return
        job.meta['feedback'] = msg
        job.save_meta()

    p = os.getpid()
    logger = LMLogger.get_logger()
    logger.info(f"(Job {p}) Starting import_labbook_from_zip(archive_path={archive_path},"
                f"username={username}, owner={owner}, config_file={config_file})")

    lb: Optional[LabBook] = None
    new_lb_path = ""
    try:
        statusmsg = "Initializing..."
        update_meta(statusmsg)

        if not os.path.isfile(archive_path):
            raise ValueError(f'Archive at {archive_path} is not a file or does not exist')

        if '.zip' not in archive_path and '.lbk' not in archive_path:
            raise ValueError(f'Archive at {archive_path} does not have .zip (or legacy .lbk) extension')

        logger.info(f"(Job {p}) Using {config_file or 'default'} LabManager configuration.")
        lm_config = Configuration(config_file)
        lm_working_dir: str = os.path.expanduser(lm_config.config['git']['working_directory'])

        # Infer the final labbook name
        inferred_labbook_name = os.path.basename(archive_path).split('_')[0]
        if base_filename:
            inferred_labbook_name = base_filename.split('_')[0]
        lb_containing_dir: str = os.path.join(lm_working_dir, username, owner, 'labbooks')

        if os.path.isdir(os.path.join(lb_containing_dir, inferred_labbook_name)):
            raise ValueError(
                f'(Job {p}) LabBook {inferred_labbook_name} already exists at {lb_containing_dir}, cannot overwrite.')

        logger.info(f"(Job {p}) Extracting LabBook from archive {archive_path} into {lb_containing_dir}")
        if lb_containing_dir[-1] != os.path.sep:
            dest_path = lb_containing_dir + os.path.sep
        else:
            dest_path = lb_containing_dir

        statusmsg = f'{statusmsg}\nUnzipping Project Archive...'
        update_meta(statusmsg)

        call_subprocess(['unzip', archive_path, '-d', dest_path], cwd=lm_working_dir, check=True)

        statusmsg = f'{statusmsg}\nFinished Unzip, checking integrity...'
        update_meta(statusmsg)

        new_lb_path = os.path.join(lb_containing_dir, inferred_labbook_name)
        if not os.path.isdir(new_lb_path):
            raise ValueError(f"(Job {p}) Expected LabBook not found at {new_lb_path}")
        
        # Make sure you actually unzipped a Project archive
        if not os.path.exists(os.path.join(new_lb_path, '.gigantum', 'labbook.yaml')):
            # Delete bad import
            logger.warning(f'Imported invalid project archive. Deleting {new_lb_path}.')
            shutil.rmtree(new_lb_path)
            raise ValueError("Malformed Project archive. Verify you uploaded the correct file.")

        logger.info(f'(Job {p}) Extracted imported archive to {new_lb_path}')
        # Make the user also the new owner of the Labbook on import.
        lb = LabBook(config_file)
        lb.from_directory(new_lb_path)
        logger.info(f'(Job {p}) Extracted archive resolves to new LabBook {str(lb)}')

        # Ignore execution bit changes (due to moving between windows/mac/linux)
        subprocess.check_output("git config core.fileMode false", cwd=lb.root_dir, shell=True)

        statusmsg = f'{statusmsg}\nCreating workspace branch...'
        update_meta(statusmsg)

        # This makes sure the working directory is set properly.
        sync_locally(lb, username=username)

        if not lb._data:
            raise ValueError(f'Could not load data from imported LabBook {lb}')
        lb._data['owner']['username'] = owner

        lb._save_labbook_data()
        if not lb.is_repo_clean:
            lb.git.add('.gigantum/labbook.yaml')
            lb.git.commit(message="Updated owner in labbook.yaml")

        if lb._data['owner']['username'] != owner:
            raise ValueError(f'Error importing LabBook {lb} - cannot set owner')

        # Also, remove any lingering remotes. If it gets re-published, it will be to a new remote.
        if lb.has_remote:
            lb.git.remove_remote('origin')

        statusmsg = f'{statusmsg}\nImport Complete'
        update_meta(statusmsg)

        logger.info(f"(Job {p}) LabBook {inferred_labbook_name} imported to {new_lb_path}")

    except Exception as e:
        logger.exception(f"(Job {p}) Error on import_labbook_from_zip({archive_path}): {e}")
        raise
    finally:
        if remove_source:
            if lb is not None:
                try:
                    logger.info(f'Deleting uploaded archive for {str(lb)}')
                    os.remove(archive_path)
                except FileNotFoundError as e:
                    logger.error(f'Could not delete archive for {str(lb)} at `{archive_path}`: {e}')

    return new_lb_path


def build_labbook_image(path: str, username: Optional[str] = None,
                        tag: Optional[str] = None, nocache: bool = False) -> str:
    """Return a docker image ID of given LabBook.

    Args:
        path: Pass-through arg to labbook root.
        username: Username of active user.
        tag: Pass-through arg to tag of docker image.
        nocache(bool): Pass-through arg to docker build.

    Returns:
        Docker image ID
    """

    logger = LMLogger.get_logger()
    logger.info(f"Starting build_labbook_image({path}, {username}, {tag}, {nocache}) in pid {os.getpid()}")

    try:
        job = get_current_job()

        def save_metadata_callback(line: str) -> None:
            try:
                if not line:
                    return
                job.meta['feedback'] = (job.meta.get('feedback') or '') + line + '\n'
                job.save_meta()
            except Exception as e:
                logger.error(e)

        image_id = build_image(path, override_image_tag=tag, nocache=nocache, username=username,
                               feedback_callback=save_metadata_callback)

        logger.info(f"Completed build_labbook_image in pid {os.getpid()}: {image_id}")
        return image_id
    except Exception as e:
        logger.error(f"Error on build_labbook_image in pid {os.getpid()}: {e}")
        raise


def start_labbook_container(root: str, config_path: str, username: Optional[str] = None,
                            override_image_id: Optional[str] = None) -> str:
    """Return the ID of the LabBook Docker container ID.

    Args:
        root: Root directory of labbook
        config_path: Path to config file (labbook.labmanager_config.config_file)
        username: Username of active user
        override_image_id: Force using this name of docker image (do not infer)

    Returns:
        Docker container ID
    """

    logger = LMLogger.get_logger()
    logger.info(f"Starting start_labbook_container(root={root}, config_path={config_path}, username={username}, "
                f"override_image_id={override_image_id}) in pid {os.getpid()}")

    try:
        c_id = start_container(labbook_root=root, config_path=config_path,
                               override_image_id=override_image_id, username=username)
        logger.info(f"Completed start_labbook_container in pid {os.getpid()}: {c_id}")
        return c_id
    except Exception as e:
        logger.error("Error on launch_docker_container in pid {}: {}".format(os.getpid(), e))
        raise


def stop_labbook_container(container_id: str):
    """Return a dictionary of metadata pertaining to the given task's Redis key.

    TODO - Take labbook as argument rather than image tag.

    Args:
        image_tag(str): Container to stop

    Returns:
        0 to indicate no failure
    """

    logger = LMLogger.get_logger()
    logger.info(f"Starting stop_labbook_container({container_id}) in pid {os.getpid()}")

    try:
        stop_container(container_id)
        return 0
    except Exception as e:
        logger.error("Error on stop_labbook_container in pid {}: {}".format(os.getpid(), e))
        raise


def run_dev_env_monitor(dev_env_name, key) -> int:
    """Run method to check if new Activity Monitors for a given dev env need to be started/stopped

        Args:
            dev_env_name(str): Name of the dev env to monitor
            key(str): The unique string used as the key in redis to track this DevEnvMonitor instance

    Returns:
        0 to indicate no failure
    """

    logger = LMLogger.get_logger()
    logger.debug("Checking Dev Env `{}` for activity monitors in PID {}".format(dev_env_name, os.getpid()))

    try:
        demm = DevEnvMonitorManager()
        dev_env = demm.get_monitor_instance(dev_env_name)
        if not dev_env:
            raise ValueError('dev_env is None')
        dev_env.run(key)
        return 0
    except Exception as e:
        logger.error("Error on run_dev_env_monitor in pid {}: {}".format(os.getpid(), e))
        raise e


def start_and_run_activity_monitor(module_name, class_name, user, owner, labbook_name, monitor_key, author_name,
                                   author_email, session_metadata):
    """Run method to run the activity monitor. It is a long running job.

        Args:


    Returns:
        0 to indicate no failure
    """
    logger = LMLogger.get_logger()
    logger.info("Starting Activity Monitor `{}` in PID {}".format(class_name, os.getpid()))

    try:
        # Import the monitor class
        m = importlib.import_module(module_name)
        # get the class
        monitor_cls = getattr(m, class_name)

        # Instantiate monitor class
        monitor = monitor_cls(user, owner, labbook_name, monitor_key,
                              author_name=author_name, author_email=author_email)

        # Start the monitor
        monitor.start(session_metadata)

        return 0
    except Exception as e:
        logger.error("Error on start_and_run_activity_monitor in pid {}: {}".format(os.getpid(), e))
        raise e


def index_labbook_filesystem():
    """To be implemented later. """
    raise NotImplemented


def test_exit_success():
    """Used only for testing -- vacuous method to always succeed and return 0. """
    return 0


def test_exit_fail():
    """Used only for testing -- always throws an exception"""
    raise Exception("Intentional Exception from job `test_exit_fail`")


def test_sleep(n):
    """Used only for testing -- example method with argument. """
    logger = LMLogger.get_logger()
    logger.info("Starting test_sleep({}) in pid {}".format(n, os.getpid()))

    try:
        job = get_current_job()
        job.meta['sample'] = 'test_sleep metadata'
        job.save_meta()

        time.sleep(n)
        logger.info("Completed test_sleep in pid {}".format(os.getpid()))
        return 0
    except Exception as e:
        logger.error("Error on test_sleep in pid {}: {}".format(os.getpid(), e))
        raise


def test_incr(path):
    logger = LMLogger.get_logger()
    logger.info("Starting test_incr({}) in pid {}".format(path, os.getpid()))

    try:
        amt = 1
        if not os.path.exists(path):
            logger.info("Creating {}".format(path))
            with open(path, 'w') as fp:
                json.dump({'amt': amt}, fp)
        else:
            logger.info("Loading {}".format(path))
            with open(path, 'r') as fp:
                amt_dict = json.load(fp)
            logger.info("Amt = {}")
            with open(path, 'w') as fp:
                amt_dict['amt'] = amt_dict['amt'] + 1
                json.dump(amt_dict, fp)
            logger.info("Set amt = {} in {}".format(amt_dict['amt'], path))
    except Exception as e:
        logger.error("Error on test_incr in pid {}: {}".format(os.getpid(), e))
        raise
