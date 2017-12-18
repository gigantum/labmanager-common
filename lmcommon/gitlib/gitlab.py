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
import requests
from typing import List, Optional, Tuple
import subprocess
import pexpect
import re

from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()


class GitLabRepositoryManager(object):
    """Class to manage administrative operations to a remote GitLab repository for a labbook"""
    def __init__(self, remote_host: str, admin_service: str, access_token: str,
                 username: str, owner: str, labbook_name: str) -> None:
        """Constructor"""
        self.remote_host = remote_host
        self.admin_service = admin_service
        self.access_token = access_token

        self.username = username
        self.owner = owner
        self.labbook_name = labbook_name

        # User's remote access token
        self._user_token: Optional[str] = None
        # ID of the repository in GitLab
        self._repository_id: Optional[int] = None

    @property
    def user_token(self) -> Optional[str]:
        """Method to get the user's API token from the auth microservice"""
        if not self._user_token:
            # Get the token
            response = requests.get(f"https://{self.admin_service}/key",
                                    headers={"Authorization": f"Bearer {self.access_token}"})
            if response.status_code == 200:
                self._user_token = response.json()['key']
            else:
                logger.error("Failed to get user access key from server")
                logger.error(response.json())
                raise ValueError("Failed to get user access key from server")

        return self._user_token

    def _get_user_id_from_username(self, username: str) -> int:
        """Method to get a user's id in GitLab based on their username

        Args:
            username(str):

        Returns:
            int
        """
        # Call API to get ID of the user
        response = requests.get(f"https://{self.remote_host}/api/v4/users?username={username}",
                                headers={"PRIVATE-TOKEN": self.user_token})
        if response.status_code != 200:
            logger.error("Failed to get id for user when adding collaborator")
            logger.error(response.json())
            raise ValueError("Failed to get id for user when adding collaborator")

        user_id = response.json()[0]['id']

        return user_id

    def repository_id(self) -> Optional[int]:
        """Method to get the repository's ID in GitLab"""
        if not self._repository_id:
            # Get the id
            response = requests.get(f"https://{self.remote_host}/api/v4/projects?search={self.labbook_name}",
                                    headers={"PRIVATE-TOKEN": self.user_token})
            if response.status_code == 200:
                data = response.json()
                if len(data) == 0:
                    logger.error(f"Failed to get repository id. {self.labbook_name} does not exist.")
                    raise ValueError(f"Failed to get repository id. {self.labbook_name} does not exist.")

                self._repository_id = data[0]['id']
            else:
                logger.error("Failed to get repository ID from server")
                logger.error(response.json())
                raise ValueError("Failed to get repository ID from server")

        return self._repository_id

    def exists(self) -> bool:
        """Method to check if the remote repository already exists

        Returns:
            bool
        """
        try:
            _ = self.repository_id()
            return True
        except ValueError:
            return False

    def create(self) -> None:
        """Method to create the remote repository

        Returns:

        """
        if self.exists():
            raise ValueError("Cannot create remote repository that already exists")

        data = {"name": self.labbook_name,
                "issues_enabled": False,
                "jobs_enabled": False,
                "wiki_enabled": False,
                "snippets_enabled": False,
                "shared_runners_enabled": False,
                "visibility": "private",
                "public_jobs": False,
                "request_access_enabled": False
                }

        # Call API to create project
        response = requests.post(f"https://{self.remote_host}/api/v4/projects",
                                 headers={"PRIVATE-TOKEN": self.user_token},
                                 json=data)

        if response.status_code != 201:
            logger.error("Failed to create remote repository")
            logger.error(response.json())
            raise ValueError("Failed to create remote repository")
        else:
            logger.info(f"Created remote repository for {self.username}/{self.owner}/{self.labbook_name}")

            # Save ID
            self._repository_id = response.json()['id']

    def get_collaborators(self) -> Optional[List[Tuple[int, str, bool]]]:
        """Method to get usernames and IDs of collaborators that have access to the repo

        The method returns a list of tuples where the entries in the tuple are (user id, username, is owner)

        Returns:
            list
        """
        if not self.exists():
            raise ValueError("Cannot get collaborators of a repository that does not exist")

        # Call API to get all collaborators
        response = requests.get(f"https://{self.remote_host}/api/v4/projects/{self.repository_id()}/members",
                                headers={"PRIVATE-TOKEN": self.user_token})

        if response.status_code != 200:
            logger.error("Failed to get remote repository collaborators")
            logger.error(response.json())
            raise ValueError("Failed to get remote repository collaborators")
        else:
            # Process response
            return [(x['id'], x['username'], x['access_level'] == 40) for x in response.json()]

    def add_collaborator(self, username: str) -> Optional[List[Tuple[int, str, bool]]]:
        """Method to add a collaborator to a remote repository by username

        Args:
            username(str): username to add

        Returns:
            list
        """
        if not self.exists():
            raise ValueError("Cannot add a collaborator to a repository that does not exist")

        # Call API to get ID of the user
        user_id = self._get_user_id_from_username(username)

        # Call API to add a collaborator
        data = {"user_id": user_id,
                "access_level": 30}
        response = requests.post(f"https://{self.remote_host}/api/v4/projects/{self.repository_id()}/members",
                                 headers={"PRIVATE-TOKEN": self.user_token},
                                 json=data)

        if response.status_code != 201:
            logger.error("Failed to add collaborator")
            logger.error(response.json())
            raise ValueError("Failed to add collaborator")
        else:
            # Re-query for collaborators and return
            logger.info(f"Added {username} as a collaborator to {self.labbook_name}")
            return self.get_collaborators()

    def delete_collaborator(self,  username: str) -> Optional[List[Tuple[int, str, bool]]]:
        """Method to remove a collaborator from a remote repository by user_id

        user id is used because it is assumed you've already listed the current collaborators

        Args:
            username(str): username to remove

        Returns:

        """
        if not self.exists():
            raise ValueError("Cannot remove a collaborator to a repository that does not exist")

        # Call API to get ID of the user
        user_id = self._get_user_id_from_username(username)

        # Call API to remove a collaborator
        response = requests.delete(f"https://{self.remote_host}/api/v4/projects/{self.repository_id()}/members/{user_id}",
                                   headers={"PRIVATE-TOKEN": self.user_token})

        if response.status_code != 204:
            logger.error("Failed to remove collaborator")
            logger.error(response.json())
            raise ValueError("Failed to remove collaborator")
        else:
            # Re-query for collaborators and return
            logger.info(f"Removed {username} as a collaborator to {self.labbook_name}")
            return self.get_collaborators()

    @staticmethod
    def _call_shell(command: str, input_list: Optional[List[str]]=None) -> Tuple[Optional[bytes], Optional[bytes]]:
        """Method to call shell commands, used to configure git client

        Args:
            command(str): command to send
            input_list(list): List of additional strings to send to the process

        Returns:
            tuple
        """
        # Start process
        p = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        # If additional commands provided, send to stdin
        if input_list:
            for i in input_list:
                p.stdin.write(i.encode('utf-8'))
                p.stdin.flush()

        # Get output
        try:
            out, err = p.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning(f"Subprocess timed-out while calling shell for git configuration")
            p.kill()
            out, err = p.communicate(timeout=5)

        return out, err

    def _check_if_git_credentials_configured(self, host: str, username: str) -> Optional[str]:
        """

        Args:
            host:
            username:

        Returns:

        """
        # Check if already configured
        child = pexpect.spawn("git credential fill")
        child.expect("")
        child.sendline("protocol=https")
        child.expect("")
        child.sendline(f"host={host}")
        child.expect("")
        child.sendline(f"username={username}")
        child.expect("")
        child.sendline("")
        i = child.expect(["Password for 'https://", "password=[\w\-\._]+"])
        if i == 0:
            # Not configured
            child.sendline("")
            return None
        elif i == 1:
            # Possibly configured, verify a valid string
            matches = re.finditer(r"password=[\w\-\._]+", child.after.decode("utf-8"))

            token = None
            try:
                for match in matches:
                    _, token = match.group().split("=")
                    break
            except ValueError:
                # if string is malformed it won't split properly and you don't have a token
                pass

            if not token:
                child.sendline("")
            child.close()

            return token

    def configure_git_credentials(self, host: str, username: str) -> None:
        """Method to configure the local git client's credentials

        Args:
            host(str): GitLab hostname
            username(str): Username to authenticate

        Returns:
            None
        """
        # Check if already configured
        token = self._check_if_git_credentials_configured(host, username)

        if token is None:
            # Need to init git creds, first select helper
            out, err = self._call_shell("git config --global credential.helper store")
            #out, err = self._call_shell("git config --global credential.helper 'cache --timeout=7200'")
            if err:
                raise ValueError("Failed to configure git credential helper")

            child = pexpect.spawn("git credential approve")
            child.expect("")
            child.sendline("protocol=https")
            child.expect("")
            child.sendline(f"host={host}")
            child.expect("")
            child.sendline(f"username={username}")
            child.expect("")
            child.sendline(f"password={self.user_token}")
            child.expect("")
            child.sendline("")
            child.expect("")
            child.sendline("")
            child.close()

            logger.info(f"Configured local git credentials for {host}")

    def clear_git_credentials(self, host: str) -> None:
        """Method to clear the local git client's credentials

        Args:
            host(str): GitLab hostname

        Returns:
            None
        """
        child = pexpect.spawn("git credential reject")
        child.expect("")
        child.sendline("protocol=https")
        child.expect("")
        child.sendline(f"host={host}")
        child.expect("")
        child.sendline("")
        child.expect("")
        child.sendline("")
        child.expect("")
        child.sendline("")

        logger.info(f"Removed local git credentials for {host}")
