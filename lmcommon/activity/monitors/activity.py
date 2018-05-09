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
from lmcommon.logging import LMLogger
from typing import (Any, Dict, List, Optional)

from lmcommon.activity import ActivityRecord, ActivityStore, ActivityType
from lmcommon.activity.processors.processor import ActivityProcessor, ExecutionData
from lmcommon.configuration import get_docker_client
from lmcommon.labbook import LabBook
from lmcommon.gitlib.git import GitAuthor
from lmcommon.container.utils import infer_docker_image_name


logger = LMLogger.get_logger()


class ActivityMonitor(metaclass=abc.ABCMeta):
    """Class to monitor a kernel/IDE for activity to be processed."""

    def __init__(self, user: str, owner: str, labbook_name: str, monitor_key: str, config_file: str = None,
                 author_name: Optional[str] = None, author_email: Optional[str] = None) -> None:
        """Constructor requires info to load the lab book

        Args:
            user(str): current logged in user
            owner(str): owner of the lab book
            labbook_name(str): name of the lab book
            monitor_key(str): Unique key for the activity monitor in redis
            author_name(str): Name of the user starting this activity monitor
            author_email(str): Email of the user starting this activity monitor
        """
        self.monitor_key = monitor_key

        # List of processor classes that will be invoked in order
        self.processors: List[ActivityProcessor] = []

        # Populate GitAuthor instance if available
        if author_name:
            author: Optional[GitAuthor] = GitAuthor(name=author_name, email=author_email)
        else:
            author = None

        # Load Lab Book instance
        self.labbook = LabBook(config_file=config_file, author=author)
        self.labbook.from_name(user, owner, labbook_name)
        self.user = user
        self.owner = owner
        self.labbook_name = labbook_name

        # Create ActivityStore instance
        self.activity_store = ActivityStore(self.labbook)

        # A flag indicating if the activity record is OK to store
        self.can_store_activity_record = False

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
        self.labbook.git.add(filename)
        commit = self.labbook.git.commit("Auto-commit from activity monitoring")
        return commit.hexsha

    def commit_labbook(self) -> str:
        """Method to commit changes to the entire labbook

        Returns:
            str
        """
        self.labbook.git.add_all()
        commit = self.labbook.git.commit("Auto-commit from activity monitoring")
        return commit.hexsha

    def store_activity_record(self, linked_commit: str, activity_record: ActivityRecord) -> Optional[str]:
        """Method to commit changes to a file

        Args:
            linked_commit(str): Git commit this ActivityRecord is related to
            activity_record(ActivityNote): The populated ActivityNote object returned by the processing pipeline

        Returns:
            str
        """
        activity_record.linked_commit = linked_commit

        # Create a activity record
        record = self.activity_store.create_activity_record(activity_record)

        return record.commit

    def process(self, activity_type: ActivityType, data: List[ExecutionData],
                metadata: Dict[str, Any]) -> ActivityRecord:
        """Method to update the result ActivityRecord object based on code and result data

        Args:
            activity_type(ActivityType): A ActivityType object indicating the activity type
            data(list): A list of ExecutionData instances containing the data for this record
            metadata(str): A dictionary containing Dev Env specific or other developer defined data

        Returns:
            ActivityRecord
        """
        # Initialize empty record
        activity_record = ActivityRecord(activity_type=activity_type)

        # Get git status for tracking file changes
        status = self.labbook.git.status()

        # Run processors to populate the record
        for p in self.processors:
            activity_record = p.process(activity_record, data, status, metadata)

        return activity_record

    def get_container_ip(self) -> Optional[str]:
        """Method to get the monitored lab book container's IP address on the Docker bridge network

        Returns:
            str
        """
        client = get_docker_client()
        lb_key = infer_docker_image_name(self.labbook_name, self.owner, self.user)
        container = client.containers.get(lb_key)
        ip = container.attrs['NetworkSettings']['Networks']['bridge']['IPAddress']
        logger.info("container {} IP: {}".format(container.name, ip))

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

