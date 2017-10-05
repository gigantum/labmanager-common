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
import abc
import git
from lmcommon.logging import LMLogger
from typing import (Any, Dict, List, Optional)

from lmcommon.activity.processors.processor import ActivityNote
from lmcommon.activity.processors.processor import ActivityProcessor
from lmcommon.configuration import get_docker_client
from lmcommon.labbook import LabBook
from lmcommon.notes import NoteStore

logger = LMLogger.get_logger()


class ActivityMonitor(metaclass=abc.ABCMeta):
    """Class to monitor a kernel/IDE for activity to be processed."""

    def __init__(self, user: str, owner: str, labbook_name: str, monitor_key: str, config_file: str = None) -> None:
        """Constructor requires info to load the lab book

        Args:
            user(str): current logged in user
            owner(str): owner of the lab book
            labbook_name(str): name of the lab book
            monitor_key(str): Unique key for the activity monitor in redis
        """
        self.monitor_key = monitor_key

        # List of processor classes that will be invoked in order
        self.processors: List[ActivityProcessor] = []

        # Load Lab Book instance
        self.labbook = LabBook(config_file=config_file)
        self.labbook.from_name(user, owner, labbook_name)
        self.user = user
        self.owner = owner
        self.labbook_name = labbook_name

        # Create NoteStore instance
        self.note_db = NoteStore(self.labbook)

    def add_processor(self, processor_instance: ActivityProcessor) -> None:
        """

        Args:
            processor_instance(ActivityProcessor): A processor class to add to the pipeline

        Returns:
            None
        """
        self.processors.append(processor_instance)

    def commit_file(self, filename: str) -> str:
        """Method to commit changes to a file

        Args:
            filename(str): file to commit

        Returns:
            str
        """
        try:
            self.labbook.git.add(filename)
        except git.exc.GitCommandError:
            # TODO: REMOVE WHEN POLLING FIXED possible polling got in the way. try again just in case.
            self.labbook.git.add(filename)

        commit = self.labbook.git.commit("Auto-commit due to activity monitoring")
        return commit.hexsha

    def commit_labbook(self) -> str:
        """Method to commit changes to the entire labbook

        Returns:
            str
        """
        self.labbook.git.add_all()
        commit = self.labbook.git.commit("Auto-commit due to activity monitoring")
        return commit.hexsha

    def create_note(self, linked_commit: str, note_data: ActivityNote) -> str:
        """Method to commit changes to a file

        Args:
            linked_commit(str): Git commit this note is related to
            note_data(ActivityNote): The populated ActivityNote object returned by the processing pipeline

        Returns:
            str
        """
        note_data_dict = {'linked_commit': linked_commit,
                          'message': note_data.message,
                          'level': note_data.log_level,
                          'tags': note_data.tags,
                          'free_text': note_data.free_text,
                          'objects': note_data.objects}

        # Create a note record
        note_commit = self.note_db.create_note(note_data_dict)

        return note_commit

    def process(self, code: Dict[str, Any], result: Dict[str, Any], metadata: Dict[str, Any]) -> ActivityNote:
        """Method to update a result object based on code and result data

        Args:
            code(dict): A dict containing data specific to the dev env containing code that was executed
            result(dict): A dict containing data specific to the dev env containing the result of code execution
            metadata(str): A dictionary containing Dev Env specific or other developer defined data

        Returns:
            ActivityNote
        """
        note = ActivityNote()
        for p in self.processors:
            note = p.process(note, code, result, metadata)

        return note

    def get_container_ip(self) -> Optional[str]:
        """Method to get the monitored lab book container's IP address on the Docker bridge network

        Returns:
            str
        """
        client = get_docker_client()
        ip = None
        for container in client.containers.list():
            if container.name == '{}-{}-{}'.format(self.user, self.owner, self.labbook_name):
                details = client.api.inspect_container(container.id)
                ip = details['NetworkSettings']['IPAddress']

                logger.info("container {} IP: {}".format(container.name, ip))
                break

        return ip

    def start(self, data: Dict[str, Any]) -> None:
        """Method called in a long running scheduled async worker that should monitor for activity, committing files
        and creating notes as needed.

        Args:
            data(dict): A dictionary of data to start the activity monitor

        Returns:
            None
        """
        raise NotImplemented

