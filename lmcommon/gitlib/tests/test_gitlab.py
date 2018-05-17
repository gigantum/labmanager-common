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
import pytest
import responses

from lmcommon.gitlib.gitlab import GitLabManager


@pytest.fixture()
def gitlab_mngr_fixture():
    """A pytest fixture that returns a GitLabRepositoryManager instance"""
    yield GitLabManager("repo.gigantum.io", "usersrv.gigantum.io", "fakeaccesstoken")


@pytest.fixture()
def property_mocks_fixture():
    """A pytest fixture that returns a GitLabRepositoryManager instance"""
    responses.add(responses.GET, 'https://usersrv.gigantum.io/key',
                  json={'key': 'afaketoken'}, status=200)
    responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/testuser%2Ftest-labbook',
                  json=[{
                          "id": 26,
                          "description": "",
                        }],
                  status=200)
    yield


class TestGitLabManager(object):
    @responses.activate
    def test_user_token(self, gitlab_mngr_fixture):
        """test the user_token property"""
        # Setup responses mock for this test
        responses.add(responses.GET, 'https://usersrv.gigantum.io/key',
                      json={'key': 'afaketoken'}, status=200)

        assert gitlab_mngr_fixture._gitlab_token is None

        # Get token
        token = gitlab_mngr_fixture.user_token
        assert token == 'afaketoken'
        assert gitlab_mngr_fixture._gitlab_token == 'afaketoken'

        # Assert token is returned and set on second call and does not make a request
        responses.add(responses.GET, 'https://usersrv.gigantum.io/key', status=400)
        assert token == gitlab_mngr_fixture.user_token

    @responses.activate
    def test_user_token_error(self, gitlab_mngr_fixture):
        """test the user_token property"""
        # Setup responses mock for this test
        responses.add(responses.GET, 'https://usersrv.gigantum.io/key',
                      json={'message': 'it failed'}, status=400)

        # Make sure error is raised when getting the key fails and returns !=200
        with pytest.raises(ValueError):
            _ = gitlab_mngr_fixture.user_token

    def test_repository_id(self):
        """test the repository_id property"""
        assert GitLabManager.get_repository_id("tester", "test-lb-1") == "tester%2Ftest-lb-1"

    @responses.activate
    def test_exists_true(self, property_mocks_fixture, gitlab_mngr_fixture):
        """test the exists method for a repo that should exist"""
        assert gitlab_mngr_fixture.labbook_exists("testuser", "test-labbook") is True

    @responses.activate
    def test_exists_false(self, gitlab_mngr_fixture):
        """test the exists method for a repo that should not exist"""
        responses.add(responses.GET, 'https://usersrv.gigantum.io/key',
                      json={'key': 'afaketoken'}, status=200)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/testuser%2Fderp',
                      json=[{
                                "message": "404 Project Not Found"
                            }],
                      status=404)

        assert gitlab_mngr_fixture.labbook_exists("testuser", "derp") is False

    @responses.activate
    def test_create(self, gitlab_mngr_fixture, property_mocks_fixture):
        """test the create method"""
        # Setup responses mock for this test
        responses.add(responses.POST, 'https://repo.gigantum.io/api/v4/projects',
                      json={
                              "id": 27,
                              "description": "",
                            },
                      status=201)
        responses.add(responses.POST, 'https://usersrv.gigantum.io/webhook/testuser/new-labbook',
                      json={
                              "success": True
                            },
                      status=201)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/testuser%2Fnew-labbook',
                      json=[{
                                "message": "404 Project Not Found"
                            }],
                      status=404)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/testuser%2Fnew-labbook',
                      json=[{
                              "id": 27,
                              "description": "",
                            }],
                      status=200)

        gitlab_mngr_fixture.create_labbook("testuser", "new-labbook")

        assert gitlab_mngr_fixture.labbook_exists("testuser", "new-labbook") is True

    @responses.activate
    def test_create_errors(self, gitlab_mngr_fixture, property_mocks_fixture):
        """test the create method"""

        # Should fail because the repo "already exists"
        with pytest.raises(ValueError):
            gitlab_mngr_fixture.create_labbook("testuser", "test-labbook")

        # Should fail because the call to gitlab failed
        responses.add(responses.POST, 'https://repo.gigantum.io/api/v4/projects',
                      json={
                              "id": 27,
                              "description": "",
                            },
                      status=400)
        with pytest.raises(ValueError):
            gitlab_mngr_fixture.create_labbook("testuser", "test-labbook")

    @responses.activate
    def test_get_collaborators(self, gitlab_mngr_fixture, property_mocks_fixture):
        """Test the get_collaborators method"""
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/testuser%2Ftest-labbook/members',
                      json=[
                                {
                                    "id": 29,
                                    "name": "Jane Doe",
                                    "username": "janed",
                                    "access_level": 40,
                                    "expires_at": None
                                },
                                {
                                    "id": 30,
                                    "name": "John Doeski",
                                    "username": "jd",
                                    "access_level": 30,
                                    "expires_at": None
                                }
                            ],
                      status=200)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/testuser%2Ftest-labbook/members',
                      status=400)

        collaborators = gitlab_mngr_fixture.get_collaborators("testuser", "test-labbook")

        assert len(collaborators) == 2
        assert collaborators[0] == (29, 'janed', True)
        assert collaborators[1] == (30, 'jd', False)

        # Verify it fails on error to gitlab (should get second mock on second call)
        with pytest.raises(ValueError):
            gitlab_mngr_fixture.get_collaborators("testuser", "test-labbook")

    @responses.activate
    def test_add_collaborator(self, gitlab_mngr_fixture, property_mocks_fixture):
        """Test the add_collaborator method"""
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/users?username=person100',
                      json=[
                                {
                                    "id": 100,
                                    "name": "New Person",
                                    "username": "person100",
                                    "state": "active",
                                }
                            ],
                      status=200)
        responses.add(responses.POST, 'https://repo.gigantum.io/api/v4/projects/testuser%2Ftest-labbook/members',
                      json={
                                "id": 100,
                                "name": "New Person",
                                "username": "person100",
                                "state": "active",
                            },
                      status=201)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/testuser%2Ftest-labbook/members',
                      json=[
                                {
                                    "id": 29,
                                    "name": "Jane Doe",
                                    "username": "janed",
                                    "access_level": 40,
                                    "expires_at": None
                                },
                                {
                                    "id": 100,
                                    "name": "New Person",
                                    "username": "person100",
                                    "access_level": 30,
                                    "expires_at": None
                                }
                            ],
                      status=200)

        collaborators = gitlab_mngr_fixture.add_collaborator("testuser", "test-labbook", "person100")

        assert len(collaborators) == 2
        assert collaborators[0] == (29, 'janed', True)
        assert collaborators[1] == (100, 'person100', False)

    @responses.activate
    def test_add_collaborator_errors(self, gitlab_mngr_fixture, property_mocks_fixture):
        """Test the add_collaborator method exception handling"""
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/users?username=person100',
                      json=[
                                {
                                    "id": 100,
                                    "name": "New Person",
                                    "username": "person100",
                                    "state": "active",
                                }
                            ],
                      status=400)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/users?username=person100',
                      json=[
                                {
                                    "id": 100,
                                    "name": "New Person",
                                    "username": "person100",
                                    "state": "active",
                                }
                            ],
                      status=200)
        responses.add(responses.POST, 'https://repo.gigantum.io/api/v4/projects/testuser%2Ftest-labbook/members',
                      json={
                                "id": 100,
                                "name": "New Person",
                                "username": "person100",
                                "state": "active",
                            },
                      status=400)

        with pytest.raises(ValueError):
            _ = gitlab_mngr_fixture.add_collaborator("testuser", "test-labbook", "person100")

        with pytest.raises(ValueError):
            _ = gitlab_mngr_fixture.add_collaborator("testuser", "test-labbook", "person100")

    @responses.activate
    def test_delete_collaborator(self, gitlab_mngr_fixture, property_mocks_fixture):
        """Test the delete_collaborator method"""
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/users?username=person100',
                      json=[
                                {
                                    "id": 100,
                                    "name": "New Person",
                                    "username": "person100",
                                    "state": "active",
                                }
                            ],
                      status=200)
        responses.add(responses.DELETE, 'https://repo.gigantum.io/api/v4/projects/testuser%2Ftest-labbook/members/100',
                      status=204)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/testuser%2Ftest-labbook/members',
                      json=[
                                {
                                    "id": 29,
                                    "name": "Jane Doe",
                                    "username": "janed",
                                    "access_level": 40,
                                    "expires_at": None
                                }
                            ],
                      status=200)

        collaborators = gitlab_mngr_fixture.delete_collaborator("testuser", "test-labbook", 'person100')

        assert len(collaborators) == 1
        assert collaborators[0] == (29, 'janed', True)

    @responses.activate
    def test_delete_collaborator_error(self, gitlab_mngr_fixture, property_mocks_fixture):
        """Test the delete_collaborator method exception handling"""
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/users?username=person100',
                      json=[
                                {
                                    "id": 100,
                                    "name": "New Person",
                                    "username": "person100",
                                    "state": "active",
                                }
                            ],
                      status=200)
        responses.add(responses.DELETE, 'https://repo.gigantum.io/api/v4/projects/testuser%2Ftest-labbook/members/100',
                      status=204)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/testuser%2Ftest-labbook/members',
                      json=[
                                {
                                    "id": 29,
                                    "name": "Jane Doe",
                                    "username": "janed",
                                    "access_level": 40,
                                    "expires_at": None
                                }
                            ],
                      status=400)

        with pytest.raises(ValueError):
            gitlab_mngr_fixture.delete_collaborator("testuser", "test-labbook", 'person100')

    @responses.activate
    def test_error_on_missing_repo(self, gitlab_mngr_fixture):
        """Test the exception handling on a repo when it doesn't exist"""
        responses.add(responses.GET, 'https://usersrv.gigantum.io/key',
                      json={'key': 'afaketoken'}, status=200)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/testuser%2Ftest-labbook',
                      json=[{
                                "message": "404 Project Not Found"
                            }],
                      status=404)

        with pytest.raises(ValueError):
            gitlab_mngr_fixture.get_collaborators("testuser", "test-labbook")
        with pytest.raises(ValueError):
            gitlab_mngr_fixture.add_collaborator("testuser", "test-labbook", "test")
        with pytest.raises(ValueError):
            gitlab_mngr_fixture.delete_collaborator("testuser", "test-labbook", 100)

    @responses.activate
    def test_configure_git_credentials(self, gitlab_mngr_fixture):
        """test the configure_git_credentials method"""
        host = "test.gigantum.io"
        username = "testuser"

        # Setup responses mock for this test
        responses.add(responses.GET, 'https://usersrv.gigantum.io/key',
                      json={'key': 'afaketoken'}, status=200)

        # Check that creds are empty
        token = gitlab_mngr_fixture._check_if_git_credentials_configured(host, username)
        assert token is None

        # Set creds
        gitlab_mngr_fixture.configure_git_credentials(host, username)

        # Check that creds are configured
        token = gitlab_mngr_fixture._check_if_git_credentials_configured(host, username)
        assert token == "afaketoken"

        # Set creds
        gitlab_mngr_fixture.clear_git_credentials(host)

        # Check that creds are configured
        token = gitlab_mngr_fixture._check_if_git_credentials_configured(host, username)
        assert token is None

    @responses.activate
    def test_delete(self, gitlab_mngr_fixture, property_mocks_fixture):
        """test the create method"""
        # Setup responses mock for this test
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/testuser%2Fnew-labbook',
                      json=[{
                              "id": 27,
                              "description": "",
                            }],
                      status=200)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/testuser%2Fnew-labbook',
                      json=[{
                              "id": 27,
                              "description": "",
                            }],
                      status=200)
        responses.add(responses.DELETE, 'https://repo.gigantum.io/api/v4/projects/testuser%2Fnew-labbook',
                      json={
                                "message": "202 Accepted"
                            },
                      status=202)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/testuser%2Fnew-labbook',
                      json=[{
                                "message": "404 Project Not Found"
                            }],
                      status=404)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/testuser%2Fnew-labbook',
                      json=[{
                                "message": "404 Project Not Found"
                            }],
                      status=404)
        responses.add(responses.DELETE, 'https://usersrv.gigantum.io/webhook/testuser/new-labbook',
                      json={},
                      status=204)

        assert gitlab_mngr_fixture.labbook_exists("testuser", "new-labbook") is True

        gitlab_mngr_fixture.remove_labbook("testuser", "new-labbook")

        assert gitlab_mngr_fixture.labbook_exists("testuser", "new-labbook") is False

        with pytest.raises(ValueError):
            gitlab_mngr_fixture.remove_labbook("testuser", "new-labbook")

    @responses.activate
    def test_list_labbooks_az(self, gitlab_mngr_fixture):
        """test list labbooks"""
        responses.add(responses.GET, 'https://usersrv.gigantum.io/key',
                      json={'key': 'afaketoken'}, status=200)
        dummy_data = [
                        {
                            "id": 118,
                            "name": "test11",
                            "name_with_namespace": "testuser / test11",
                            "path_with_namespace": "testuser/test11",
                            "created_at": "2018-04-19T19:06:11.009Z",
                            "last_activity_at": "2018-04-19T22:08:05.974Z",
                            "visibility": "private",
                            "owner": {
                                "id": 14,
                                "name": "testuser",
                                "username": "testuser",
                                "state": "active",
                            },
                            "creator_id": 14,
                            "namespace": {
                                "id": 14,
                                "name": "testuser",
                                "path": "testuser",
                                "kind": "user",
                                "full_path": "testuser"
                            },
                            "import_status": "none",
                            "permissions": {
                                "project_access": {
                                    "access_level": 30,
                                    "notification_level": 3
                                },
                            }
                        },
                        {
                            "id": 138,
                            "name": "test2",
                            "name_with_namespace": "testuser / test2",
                            "path_with_namespace": "testuser/test2",
                            "created_at": "2018-04-19T19:36:11.009Z",
                            "last_activity_at": "2018-04-19T20:58:05.974Z",
                            "visibility": "private",
                            "owner": {
                                "id": 14,
                                "name": "testuser",
                                "username": "testuser",
                                "state": "active",
                            },
                            "creator_id": 14,
                            "namespace": {
                                "id": 14,
                                "name": "testuser",
                                "path": "testuser",
                                "kind": "user",
                                "full_path": "testuser"
                            },
                            "import_status": "none",
                            "permissions": {
                                "project_access": {
                                    "access_level": 30,
                                    "notification_level": 3
                                },
                            }
                        }]

        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/',
                      json=dummy_data, status=200)

        labbooks = gitlab_mngr_fixture.list_labbooks()

        assert len(labbooks) == 2
        assert labbooks[0]['id'] == 138
        assert labbooks[0]['namespace'] == "testuser"
        assert labbooks[0]['labbook_name'] == "test2"
        assert labbooks[0]['description'] == ""
        assert labbooks[0]['created_on'] == "2018-04-19T19:36:11.009Z"
        assert labbooks[0]['modified_on'] == "2018-04-19T20:58:05.974Z"
        assert labbooks[1]['id'] == 118
        assert labbooks[1]['namespace'] == "testuser"
        assert labbooks[1]['labbook_name'] == "test11"
        assert labbooks[1]['description'] == ""
        assert labbooks[1]['created_on'] == "2018-04-19T19:06:11.009Z"
        assert labbooks[1]['modified_on'] == "2018-04-19T22:08:05.974Z"

        labbooks = gitlab_mngr_fixture.list_labbooks(reverse=True)

        assert len(labbooks) == 2
        assert labbooks[0]['id'] == 118
        assert labbooks[0]['namespace'] == "testuser"
        assert labbooks[0]['labbook_name'] == "test11"
        assert labbooks[0]['description'] == ""
        assert labbooks[0]['created_on'] == "2018-04-19T19:06:11.009Z"
        assert labbooks[0]['modified_on'] == "2018-04-19T22:08:05.974Z"
        assert labbooks[1]['id'] == 138
        assert labbooks[1]['namespace'] == "testuser"
        assert labbooks[1]['labbook_name'] == "test2"
        assert labbooks[1]['description'] == ""
        assert labbooks[1]['created_on'] == "2018-04-19T19:36:11.009Z"
        assert labbooks[1]['modified_on'] == "2018-04-19T20:58:05.974Z"

    @responses.activate
    def test_list_labbooks_create_modify(self, gitlab_mngr_fixture):
        """test list labbooks"""
        responses.add(responses.GET, 'https://usersrv.gigantum.io/key',
                      json={'key': 'afaketoken'}, status=200)
        dummy_data = [
                        {
                            "id": 118,
                            "name": "test11",
                            "name_with_namespace": "testuser / test11",
                            "path_with_namespace": "testuser/test11",
                            "created_at": "2018-04-19T19:06:11.009Z",
                            "last_activity_at": "2018-04-20T22:08:05.974Z",
                            "visibility": "private",
                            "owner": {
                                "id": 14,
                                "name": "testuser",
                                "username": "testuser",
                                "state": "active",
                            },
                            "creator_id": 14,
                            "namespace": {
                                "id": 14,
                                "name": "testuser",
                                "path": "testuser",
                                "kind": "user",
                                "full_path": "testuser"
                            },
                            "import_status": "none",
                            "permissions": {
                                "project_access": {
                                    "access_level": 30,
                                    "notification_level": 3
                                },
                            }
                        },
                        {
                            "id": 138,
                            "name": "test2",
                            "name_with_namespace": "testuser / test2",
                            "path_with_namespace": "testuser/test2",
                            "created_at": "2018-04-19T19:36:11.009Z",
                            "last_activity_at": "2018-04-19T20:58:05.974Z",
                            "visibility": "private",
                            "owner": {
                                "id": 14,
                                "name": "testuser",
                                "username": "testuser",
                                "state": "active",
                            },
                            "creator_id": 14,
                            "namespace": {
                                "id": 14,
                                "name": "testuser",
                                "path": "testuser",
                                "kind": "user",
                                "full_path": "testuser"
                            },
                            "import_status": "none",
                            "permissions": {
                                "project_access": {
                                    "access_level": 30,
                                    "notification_level": 3
                                },
                            }
                        }]

        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/',
                      json=dummy_data, status=200)

        labbooks = gitlab_mngr_fixture.list_labbooks(sort_mode="created_on")

        assert len(labbooks) == 2
        assert labbooks[0]['id'] == 138
        assert labbooks[0]['namespace'] == "testuser"
        assert labbooks[0]['labbook_name'] == "test2"
        assert labbooks[0]['description'] == ""
        assert labbooks[0]['created_on'] == "2018-04-19T19:36:11.009Z"
        assert labbooks[0]['modified_on'] == "2018-04-19T20:58:05.974Z"
        assert labbooks[1]['id'] == 118
        assert labbooks[1]['namespace'] == "testuser"
        assert labbooks[1]['labbook_name'] == "test11"
        assert labbooks[1]['description'] == ""
        assert labbooks[1]['created_on'] == "2018-04-19T19:06:11.009Z"
        assert labbooks[1]['modified_on'] == "2018-04-20T22:08:05.974Z"

        labbooks = gitlab_mngr_fixture.list_labbooks(sort_mode="modified_on")

        assert len(labbooks) == 2
        assert labbooks[0]['id'] == 118
        assert labbooks[0]['namespace'] == "testuser"
        assert labbooks[0]['labbook_name'] == "test11"
        assert labbooks[0]['description'] == ""
        assert labbooks[0]['created_on'] == "2018-04-19T19:06:11.009Z"
        assert labbooks[0]['modified_on'] == "2018-04-20T22:08:05.974Z"
        assert labbooks[1]['id'] == 138
        assert labbooks[1]['namespace'] == "testuser"
        assert labbooks[1]['labbook_name'] == "test2"
        assert labbooks[1]['description'] == ""
        assert labbooks[1]['created_on'] == "2018-04-19T19:36:11.009Z"
        assert labbooks[1]['modified_on'] == "2018-04-19T20:58:05.974Z"
