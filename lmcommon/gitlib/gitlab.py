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
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any
import subprocess
import pexpect
import re
import os
from urllib.parse import quote_plus

from lmcommon.logging import LMLogger

logger = LMLogger.get_logger()


def check_and_add_user(admin_service: str, access_token: str, username: str) -> None:
    """Method to check if a user exists in GitLab and if not, create it

    Args:
        admin_service(str): URL of the GitLab Auth service
        access_token(str): The logged in user's access token
        username(str): The logged in user's username

    Returns:
        None
    """
    # Check for user
    response = requests.get(f"https://{admin_service}/user",
                            headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    if response.status_code == 200:
        # User exists, do nothing
        pass
    elif response.status_code == 404:
        assert response.json()['exists'] is False, "User not found in repository, but an error occurred"

        # user does not exist, add!
        response = requests.post(f"https://{admin_service}/user",
                                 headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        if response.status_code != 201:
            logger.error("Failed to create new user in GitLab")
            logger.error(response.json())
            raise ValueError("Failed to create new user in GitLab")

        logger.info(f"Created new user `{username}` in remote git server")
    else:
        raise ValueError("Failed to check for user in repository")


class GitLabException(Exception):
    pass


class Visibility(Enum):
    """ Represents access to remote GitLab project"""
    # Available only to owner and collaborators
    PRIVATE = "private"

    # Available to anyone via link (even non-users)
    PUBLIC = "public"

    # Available to any user registered in GitLab
    INTERNAL = "internal"


class GitLabManager(object):
    """Class to manage administrative operations to a remote GitLab server"""
    def __init__(self, remote_host: str, admin_service: str, access_token: str) -> None:
        # GitLab Server URL
        self.remote_host = remote_host
        # Admin Service URL
        self.admin_service = admin_service

        # Current user's bearer token
        self.access_token = access_token
        # Current user's GitLab impersonation token
        self._gitlab_token: Optional[str] = None

    @staticmethod
    def get_repository_id(namespace: str, labbook_name: str) -> str:
        """Method to transform a namespace and labbook name to a project ID

        Args:
            namespace(str): Namespace in gitlab, currently the "owner"
            labbook_name(str): LabBook name (i.e. project name in gitlab)

        Returns:
            str
        """
        return quote_plus(f"{namespace}/{labbook_name}")

    @property
    def user_token(self) -> Optional[str]:
        """Method to get the user's API token from the auth microservice"""
        if not self._gitlab_token:
            # Get the token
            response = requests.get(f"https://{self.admin_service}/key",
                                    headers={"Authorization": f"Bearer {self.access_token}"}, timeout=10)
            if response.status_code == 200:
                self._gitlab_token = response.json()['key']
            elif response.status_code == 404:
                # User not found so create it!
                response = requests.post(f"https://{self.admin_service}/user",
                                         headers={"Authorization": f"Bearer {self.access_token}"}, timeout=10)
                if response.status_code != 201:
                    logger.error("Failed to create new user in GitLab")
                    logger.error(response.json())
                    raise ValueError("Failed to create new user in GitLab")

                logger.info(f"Created new user in remote git server")

                # New get the key so the current request that triggered this still succeeds
                response = requests.get(f"https://{self.admin_service}/key",
                                        headers={"Authorization": f"Bearer {self.access_token}"}, timeout=10)
                if response.status_code == 200:
                    self._gitlab_token = response.json()['key']
                else:
                    logger.error("Failed to get user access key from server after creation. "
                                 "Status Code: {response.status_code}")
                    logger.error(response.json())
                    raise ValueError("Failed to get user access key from server after creation")
            else:
                logger.error(f"Failed to get user access key from server. Status Code: {response.status_code}")
                logger.error(response.json())
                raise ValueError("Failed to get user access key from server")

        return self._gitlab_token

    def _get_user_id_from_username(self, username: str) -> int:
        """Method to get a user's id in GitLab based on their username

        Args:
            username(str):

        Returns:
            int
        """
        # Call API to get ID of the user
        response = requests.get(f"https://{self.remote_host}/api/v4/users?username={username}",
                                headers={"PRIVATE-TOKEN": self.user_token}, timeout=10)
        if response.status_code != 200:
            logger.error(f"Failed to query for user ID from username. Status Code: {response.status_code}")
            logger.error(response.json())
            raise ValueError("Failed to query for user ID from username.")

        user_id = None
        for user in response.json():
            if user['username'] == username:
                user_id = user['id']
                break

        if user_id is None:
            raise ValueError(f"User ID not found when querying by username: {username}")

        return user_id

    def list_labbooks(self, order_by: str = 'name', sort_str: str = 'desc',
                      page: int = 0, per_page: int = 20) -> List[Dict[str, Any]]:
        """Method to list all remote labbooks for a user

        Args:
            order_by(str): String specifying how projects should be sorted
            sort_str(str): string indicating order of results, desc or asc, for descending or ascending respectively
            page(int): Page to query
            per_page(int): Number of items to return per page

        Supported sorting modes:
            - az: naturally sort
            - created_on: sort by creation date, newest first
            - modified_on: sort by modification date, newest first

        Returns:
            bool
        """
        # Prep request
        if order_by == 'name':
            order_by = 'name'
        elif order_by == 'created_on':
            order_by = 'created_at'
        elif order_by == 'modified_on':
            order_by = 'last_activity_at'
        else:
            raise ValueError(f"Unsupported order_by: {order_by}. Use `name`, `created_on`, `modified_on`")

        if sort_str not in ['desc', 'asc']:
            raise ValueError(f"Unsupported sort_str: {sort_str}. Use `desc`, `asc`")

        query_url = f"https://{self.remote_host}/api/v4/projects?page={page}&" + \
                    f"per_page={per_page}&order_by={order_by}&sort={sort_str}&membership=true"

        # Call API to check for project
        response = requests.get(query_url,
                                headers={"PRIVATE-TOKEN": self.user_token}, timeout=30)

        if response.status_code == 200:
            # TODO: Add description after async task to populate description in GitLab is implemented
            labbooks = [{"id": p.get("id"),
                         "namespace": p.get("namespace").get("name"),
                         "labbook_name": p.get("name"),
                         "description": "",
                         "created_on": p.get("created_at"),
                         "modified_on": p.get("last_activity_at"),
                         "visibility": p.get("visibility")} for p in response.json()]

            return labbooks

        else:
            msg = f"Failed to list Projects. Status Code: {response.status_code}"
            logger.error(msg)
            logger.error(response.json())
            raise ValueError(msg)

    def labbook_exists(self, namespace: str, labbook_name: str) -> bool:
        """Method to check if the remote repository already exists

        Args:
            namespace(str): Namespace in gitlab, currently the "owner"
            labbook_name(str): LabBook name (i.e. project name in gitlab)

        Returns:
            bool
        """
        # Call API to check for project
        repo_id = self.get_repository_id(namespace, labbook_name)
        response = requests.get(f"https://{self.remote_host}/api/v4/projects/{repo_id}",
                                headers={"PRIVATE-TOKEN": self.user_token}, timeout=10)

        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            return False
        else:
            msg = f"Failed to check if {namespace}/{labbook_name} exists. Status Code: {response.status_code}"
            logger.error(msg)
            logger.error(response.json())
            raise ValueError(msg)

    def set_visibility(self, namespace: str, labbook_name: str, visibility: str) -> None:
        """ Change public/private visibility for a given project

        Args:
            namespace: Owner or organization
            labbook_name: Name of labbook
            visibility: One of "public" or "private"

        Returns:
            None (Exception on failure)

        """
        repo_id = self.get_repository_id(namespace, labbook_name)
        update_data = {'visibility': visibility}
        response = requests.put(f"https://{self.remote_host}/api/v4/projects/{repo_id}",
                                data=update_data, headers={"PRIVATE-TOKEN": self.user_token},
                                timeout=10)
        if response.status_code != 200:
            msg = f"Could not set visibility for remote project {namespace}/{labbook_name} " \
                  f"to {visibility}: Status code {response.status_code}"
            raise ValueError(msg)

        details = self.repo_details(namespace, labbook_name)
        if details.get('visibility') != visibility:
            raise ValueError(f"Visibility could not be set for {namespace}/{labbook_name} to {visibility}")

    def repo_details(self, namespace: str, labbook_name: str) -> Dict[str, Any]:
        """ Get all properties of a given Gitlab Repository, see API documentation
            at https://docs.gitlab.com/ee/api/projects.html#get-single-project.

            TODO - Find or create a GitLab Python API project to replace (much) of this.

            Args:
                namespace: Owner or organization
                labbook_name: Name of labbook

            Returns:
                Dict of labbook properties, for keys see above link.
            """
        repo_id = self.get_repository_id(namespace, labbook_name)
        response = requests.get(f"https://{self.remote_host}/api/v4/projects/{repo_id}",
                                headers={"PRIVATE-TOKEN": self.user_token}, timeout=10)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise ValueError(f"Remote GitLab repo {namespace}/{labbook_name} not found")
        else:
            msg = f"Failed to check if {namespace}/{labbook_name} exists. Status Code: {response.status_code}"
            logger.error(msg)
            logger.error(response.json())
            raise ValueError(msg)

    def fork_labbook(self, username: str, namespace: str, labbook_name: str):
        if self.labbook_exists(namespace, labbook_name):
            raise ValueError(f"Remote repository {namespace}/{labbook_name}")

        repo_id = self.get_repository_id(namespace, labbook_name)
        data = {"id": repo_id,
                "namespace": username}
        response = requests.post(f"https://{self.remote_host}/api/v4/projects/{repo_id}/fork",
                                 headers={"PRIVATE-TOKEN": self.user_token},
                                 json=data,
                                 timeout=10)

        if response.status_code != 201:
            msg = f"Failed to fork {namespace}/{labbook_name} for user {username} ({response.status_code})"
            logger.error(msg)
            raise GitLabException(f'Failed to fork: {msg}')

    def create_labbook(self, namespace: str, labbook_name: str, visibility: str) -> None:
        """Method to create the remote repository

        Args:
            namespace(str): Namespace in gitlab, currently the "owner"
            labbook_name(str): LabBook name (i.e. project name in gitlab)
            visibility(str): public, private (default), or internal.

        Returns:

        """
        if self.labbook_exists(namespace, labbook_name):
            raise ValueError("Cannot create remote repository that already exists")

        # Raises ValueError if given visibility is not valid
        Visibility(visibility)

        data = {"name": labbook_name,
                "issues_enabled": False,
                "jobs_enabled": False,
                "wiki_enabled": False,
                "snippets_enabled": False,
                "shared_runners_enabled": False,
                # See: https://docs.gitlab.com/ee/api/projects.html#project-merge-method
                # We want all deconfliction done on client-side.
                "merge_method": "ff",
                "visibility": visibility,
                "public_jobs": False,
                "request_access_enabled": False
                }

        # Call API to create project
        response = requests.post(f"https://{self.remote_host}/api/v4/projects",
                                 headers={"PRIVATE-TOKEN": self.user_token},
                                 json=data, timeout=10)

        if response.status_code != 201:
            logger.error("Failed to create remote repository")
            logger.error(response.json())
            raise ValueError("Failed to create remote repository")
        else:
            logger.info(f"Created remote repository {namespace}/{labbook_name}")

        # Add project to quota service
        try:
            response = requests.post(f"https://{self.admin_service}/webhook/{namespace}/{labbook_name}",
                                     headers={"Authorization": f"Bearer {self.access_token}"}, timeout=30)
            if response.status_code != 201:
                logger.error(f"Failed to configure quota webhook: {response.status_code}")
                logger.error(response.json)
            else:
                logger.info(f"Configured webhook for {namespace}/{labbook_name}")

        except Exception as err:
            # Don't let quota service errors stop you from continuing
            logger.error(f"Failed to configure quota webhook: {err}")

    def remove_labbook(self, namespace: str, labbook_name: str) -> None:
        """Method to remove the remote repository

        Args:
            namespace(str): Namespace in gitlab, currently the "owner"
            labbook_name(str): LabBook name (i.e. project name in gitlab)

        Returns:
            None
        """
        if not self.labbook_exists(namespace, labbook_name):
            raise ValueError("Cannot remove remote repository that does not exist")

        # Remove project from quota service
        try:
            response = requests.delete(f"https://{self.admin_service}/webhook/{namespace}/{labbook_name}",
                                       headers={"Authorization": f"Bearer {self.access_token}"}, timeout=20)
            if response.status_code != 204:
                logger.error(f"Failed to remove quota webhook: {response.status_code}")
                logger.error(response.json)
            else:
                logger.info(f"Removed webhook for {namespace}/{labbook_name}")

        except Exception as err:
            # Don't let quota service errors stop you from continuing
            logger.error(f"Failed to remove quota webhook: {err}")

        # Call API to remove project
        repo_id = self.get_repository_id(namespace, labbook_name)
        response = requests.delete(f"https://{self.remote_host}/api/v4/projects/{repo_id}",
                                   headers={"PRIVATE-TOKEN": self.user_token}, timeout=10)

        if response.status_code != 202:
            logger.error(f"Failed to remove remote repository. Status Code: {response.status_code}")
            logger.error(response.json())
            raise ValueError("Failed to create remote repository")
        else:
            logger.info(f"Deleted remote repository {namespace}/{labbook_name}")

    def get_collaborators(self, namespace: str, labbook_name: str) -> Optional[List[Tuple[int, str, bool]]]:
        """Method to get usernames and IDs of collaborators that have access to the repo

        The method returns a list of tuples where the entries in the tuple are (user id, username, is owner)

        Args:
            namespace(str): Namespace in gitlab, currently the "owner"
            labbook_name(str): LabBook name (i.e. project name in gitlab)

        Returns:
            list
        """
        if not self.labbook_exists(namespace, labbook_name):
            raise ValueError("Cannot get collaborators of a repository that does not exist")

        # Call API to get all collaborators
        repo_id = self.get_repository_id(namespace, labbook_name)
        response = requests.get(f"https://{self.remote_host}/api/v4/projects/{repo_id}/members",
                                headers={"PRIVATE-TOKEN": self.user_token}, timeout=10)

        if response.status_code != 200:
            logger.error("Failed to get remote repository collaborators")
            logger.error(response.json())
            raise ValueError("Failed to get remote repository collaborators")
        else:
            # Process response
            return [(x['id'], x['username'], x['access_level'] == 40) for x in response.json()]

    def add_collaborator(self,
                         namespace: str,
                         labbook_name: str,
                         username: str) -> Optional[List[Tuple[int, str, bool]]]:
        """Method to add a collaborator to a remote repository by username

        Args:
            namespace(str): Namespace in gitlab, currently the "owner"
            labbook_name(str): LabBook name (i.e. project name in gitlab)
            username(str): username to add

        Returns:
            list
        """
        if not self.labbook_exists(namespace, labbook_name):
            raise ValueError("Cannot add a collaborator to a repository that does not exist")

        # Call API to get ID of the user
        user_id = self._get_user_id_from_username(username)

        # Call API to add a collaborator
        data = {"user_id": user_id,
                "access_level": 30}
        repo_id = self.get_repository_id(namespace, labbook_name)
        response = requests.post(f"https://{self.remote_host}/api/v4/projects/{repo_id}/members",
                                 headers={"PRIVATE-TOKEN": self.user_token},
                                 json=data, timeout=10)

        if response.status_code != 201:
            logger.error("Failed to add collaborator")
            logger.error(response.json())
            raise ValueError("Failed to add collaborator")
        else:
            # Re-query for collaborators and return
            logger.info(f"Added {username} as a collaborator to {labbook_name}")
            return self.get_collaborators(namespace, labbook_name)

    def delete_collaborator(self,
                            namespace: str,
                            labbook_name: str,
                            username: str) -> Optional[List[Tuple[int, str, bool]]]:
        """Method to remove a collaborator from a remote repository by user_id

        user id is used because it is assumed you've already listed the current collaborators

        Args:
            namespace(str): Namespace in gitlab, currently the "owner"
            labbook_name(str): LabBook name (i.e. project name in gitlab)
            username(str): username to remove

        Returns:

        """
        if not self.labbook_exists(namespace, labbook_name):
            raise ValueError("Cannot remove a collaborator to a repository that does not exist")

        # Lookup username
        user_id = self._get_user_id_from_username(username)

        # Call API to remove a collaborator
        repo_id = self.get_repository_id(namespace, labbook_name)
        response = requests.delete(f"https://{self.remote_host}/api/v4/projects/{repo_id}/members/{user_id}",
                                   headers={"PRIVATE-TOKEN": self.user_token}, timeout=10)

        if response.status_code != 204:
            logger.error("Failed to remove collaborator")
            logger.error(response.json())
            raise ValueError("Failed to remove collaborator")
        else:
            # Re-query for collaborators and return
            logger.info(f"Removed user id `{user_id}` as a collaborator to {labbook_name}")
            return self.get_collaborators(namespace, labbook_name)

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
        # Get the current working dir
        cwd = os.getcwd()
        try:
            # Switch to the user's home dir (needed to make git config and credential saving work)
            os.chdir(os.path.expanduser("~"))
            child = pexpect.spawn("git credential fill")
            child.expect("")
            child.sendline("protocol=https")
            child.expect("")
            child.sendline(f"host={host}")
            child.expect("")
            child.sendline(f"username={username}")
            child.expect("")
            child.sendline("")
            i = child.expect(["Password for 'https://", "password=[\w\-\._]+", pexpect.EOF])
        finally:
            # Switch back to where you were
            os.chdir(os.path.expanduser(cwd))
        if i == 0:
            # Not configured
            child.sendline("")
            return None
        elif i == 1:
            # Possibly configured, verify a valid string TODO - Why does pycharm complain about redundant chars?
            matches = re.finditer(r"password=[a-zA-Z0-9\-_\!@\#\$%\^&\*]+", child.after.decode("utf-8"))

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
        elif i == 2:
            # Possibly configured, verify a valid string
            matches = re.finditer(r"password=[a-zA-Z0-9\-_\!@\#\$%\^&\*]+", child.before.decode("utf-8"))

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

        else:
            return None

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
            cwd = os.getcwd()
            try:
                os.chdir(os.path.expanduser("~"))
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
                child.expect(["", pexpect.EOF])
                child.sendline("")
                child.expect(["", pexpect.EOF])
                child.close()
            finally:
                os.chdir(os.path.expanduser(cwd))

            logger.info(f"Configured local git credentials for {host}")

    def clear_git_credentials(self, host: str) -> None:
        """Method to clear the local git client's credentials

        Args:
            host(str): GitLab hostname

        Returns:
            None
        """
        cwd = os.getcwd()
        try:
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
            child.close()
        finally:
            os.chdir(os.path.expanduser(cwd))

        logger.info(f"Removed local git credentials for {host}")
