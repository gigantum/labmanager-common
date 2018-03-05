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
import zipfile
import shutil

from rq import get_current_job
from docker.errors import NotFound

from lmcommon.activity.monitors.devenv import DevEnvMonitorManager
from lmcommon.configuration import get_docker_client, Configuration
from lmcommon.labbook import LabBook
from lmcommon.labbook import shims as labbook_shims
from lmcommon.logging import LMLogger

from lmcommon.container.core import (build_docker_image as build_image,
                                     start_labbook_container as start_container,
                                     stop_labbook_container as stop_container)


# PLEASE NOTE -- No global variables!
#
# None of the following methods can use global variables.
# ANY use of globals will cause the following methods to fail.


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
        labbook.local_sync()

        logger.info(f"(Job {p}) Exporting `{labbook.root_dir}` to `{lb_export_directory}`")
        if not os.path.exists(lb_export_directory):
            logger.warning(f"(Job {p}) Creating Lab Manager export directory at `{lb_export_directory}`")
            os.makedirs(lb_export_directory)

        lb_zip_name = f'{labbook.name}_{datetime.datetime.now().strftime("%Y-%m-%d")}.lbk'
        zip_path = os.path.join(lb_export_directory, lb_zip_name)
        with zipfile.ZipFile(zip_path, 'w') as lb_archive:
            basename = os.path.basename(labbook_path)
            for root, dirs, files in os.walk(labbook_path):
                for file_ in files:
                    rel_path = os.path.join(root, file_).replace(labbook_path, basename)
                    logger.debug(f"Adding file `{os.path.join(root, file_)}` as `{rel_path}`")
                    lb_archive.write(os.path.join(root, file_), arcname=rel_path)

        logger.info(f"(Job {p}) Finished exporting {str(labbook)} to {zip_path}")
        return zip_path
    except Exception as e:
        logger.exception(f"(Job {p}) Error on export_labbook_as_zip: {e}")
        raise


def import_labboook_from_zip(archive_path: str, username: str, owner: str,
                             config_file: Optional[str] = None, base_filename: Optional[str] = None) -> str:
    """Method to import a labbook from a zip file

    Args:
        archive_path(str): Path to the uploaded zip
        username(str): Username
        owner(str): Owner username
        config_file(str): Optional path to a labmanager config file
        base_filename(str): The desired basename for the upload, without an upload ID prepended

    Returns:
        str: directory path of imported labbook
    """
    p = os.getpid()
    logger = LMLogger.get_logger()
    logger.info(f"(Job {p}) Starting import_labbook_from_zip(archive_path={archive_path},"
                f"username={username}, owner={owner}, config_file={config_file})")

    try:
        if not os.path.isfile(archive_path):
            raise ValueError(f'Archive at {archive_path} is not a file or does not exist')

        if '.lbk' not in archive_path:
            raise ValueError(f'Archive at {archive_path} does not have .lbk extension')

        logger.info(f"(Job {p}) Using {config_file or 'default'} LabManager configuration.")
        lm_config = Configuration(config_file)
        lm_working_dir: str = os.path.expanduser(lm_config.config['git']['working_directory'])

        # Infer the final labbook name
        inferred_labbook_name = os.path.basename(archive_path).split('_')[0]
        if base_filename:
            inferred_labbook_name = base_filename.split('_')[0]
        lb_containing_dir: str = os.path.join(lm_working_dir, username, owner, 'labbooks')

        if os.path.isdir(os.path.join(lb_containing_dir, inferred_labbook_name)):
            raise ValueError(f'(Job {p}) LabBook {inferred_labbook_name} already exists at {lb_containing_dir}, cannot overwrite.')

        logger.info(f"(Job {p}) Extracting LabBook from archive {archive_path} into {lb_containing_dir}")
        with zipfile.ZipFile(archive_path) as lb_zip:
            lb_zip.extractall(path=lb_containing_dir)

        new_lb_path = os.path.join(lb_containing_dir, inferred_labbook_name)
        if not os.path.isdir(new_lb_path):
            raise ValueError(f"(Job {p}) Expected LabBook not found at {new_lb_path}")

        # Make the user also the new owner of the Labbook on import.
        lb = LabBook(config_file)
        lb.from_directory(new_lb_path)
        if not lb._data:
            raise ValueError(f'Could not load data from imported LabBook {lb}')
        lb._data['owner']['username'] = owner

        # Also, remove any lingering remotes. If it gets re-published, it will be to a new remote.
        if lb.has_remote:
            lb.git.remove_remote('origin')
        # This makes sure the working directory is set properly.
        lb.local_sync(username=username)

        if not lb.is_repo_clean:
            raise ValueError(f'Imported LabBook {lb} should have clean repo after import')

        lb._save_labbook_data()
        if not lb.is_repo_clean:
            lb.git.add('.gigantum/labbook.yaml')
            lb.git.commit(message="Updated owner in labbook.yaml")

        if lb._data['owner']['username'] != owner:
            raise ValueError(f'Error importing LabBook {lb} - cannot set owner')

        logger.info(f"(Job {p}) LabBook {inferred_labbook_name} imported to {new_lb_path}")

        try:
            logger.info(f'Deleting archive for {str(lb)} at `{archive_path}`')
            os.remove(archive_path)
        except FileNotFoundError as e:
            logger.error(f'Could not delete archive for {str(lb)} at `{archive_path}`: {e}')
        return new_lb_path
    except Exception as e:
        logger.exception(f"(Job {p}) Error on import_labbook_from_zip({archive_path}): {e}")
        raise


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

        image_id = build_image(path, override_image_tag=tag, nocache=nocache, username=username)
        logger.info(f"Completed build_labbook_image in pid {os.getpid()}: {image_id}")
        return image_id
    except Exception as e:
        logger.error(f"Error on build_labbook_image in pid {os.getpid()}: {e}")
        raise


def start_labbook_container(root: str, config_path:str, username: Optional[str] = None,
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
        c_id, pmap = start_container(labbook_root=root, config_path=config_path,
                                    override_image_id=override_image_id, username=username)
        logger.info(f"Completed start_labbook_container in pid {os.getpid()}: {c_id}, port mapping={str(pmap)}")
        return c_id
    except Exception as e:
        logger.error("Error on launch_docker_container in pid {}: {}".format(os.getpid(), e))
        raise


def stop_labbook_container(image_tag: str):
    """Return a dictionary of metadata pertaining to the given task's Redis key.

    TODO - Take labbook as argument rather than image tag.

    Args:
        image_tag(str): Container to stop

    Returns:
        0 to indicate no failure
    """

    logger = LMLogger.get_logger()
    logger.info(f"Starting stop_labbook_container({image_tag}) in pid {os.getpid()}")

    try:
        stop_container(image_tag)
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
            dev_env_name(str): Name of the dev env to monitor
            key(str): The unique string used as the key in redis to track this DevEnvMonitor instance

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
