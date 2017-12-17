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

from lmcommon.gitlib.gitlab import GitLabRepositoryManager


@pytest.fixture()
def gitlab_mngr_fixture():
    """A pytest fixture that returns a GitLabRepositoryManager instance"""
    yield GitLabRepositoryManager("repo.gigantum.io", "usersrv.gigantum.io", "fakeaccesstoken",
                                  "testuser", "testuser", "test-labbook")


@pytest.fixture()
def property_mocks_fixture():
    """A pytest fixture that returns a GitLabRepositoryManager instance"""
    responses.add(responses.GET, 'https://usersrv.gigantum.io/key',
                  json={'key': 'afaketoken'}, status=200)
    responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects?search=test-labbook',
                  json=[{
                          "id": 26,
                          "description": "",
                        }],
                  status=200, match_querystring=True)
    yield


class TestGitLabRepositoryManager(object):
    @responses.activate
    def test_user_token(self, gitlab_mngr_fixture):
        """test the user_token property"""
        # Setup responses mock for this test
        responses.add(responses.GET, 'https://usersrv.gigantum.io/key',
                      json={'key': 'afaketoken'}, status=200)

        assert gitlab_mngr_fixture._user_token is None

        # Get token
        token = gitlab_mngr_fixture.user_token
        assert token == 'afaketoken'
        assert gitlab_mngr_fixture._user_token == 'afaketoken'

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

    @responses.activate
    def test_repository_id_does_not_exist(self, gitlab_mngr_fixture):
        """test the repository_id property when the repo doesn't exist"""
        # Setup responses mock for this test
        responses.add(responses.GET, 'https://usersrv.gigantum.io/key',
                      json={'key': 'afaketoken'}, status=200)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects?search=test-labbook',
                      json=[], status=200)

        # Make sure error is raised when no ids come back from the server
        with pytest.raises(ValueError):
            _ = gitlab_mngr_fixture.repository_id()

    @responses.activate
    def test_repository_id_error(self, gitlab_mngr_fixture):
        """test the repository_id property error"""
        # Setup responses mock for this test
        responses.add(responses.GET, 'https://usersrv.gigantum.io/key',
                      json={'key': 'afaketoken'}, status=200)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects?search=test-labbook',
                      json={'message': 'it failed'}, status=400)

        # Make sure error is raised when getting the key fails and returns !=200
        with pytest.raises(ValueError):
            _ = gitlab_mngr_fixture.repository_id()

    @responses.activate
    def test_repository_id(self, gitlab_mngr_fixture):
        """test the repository_id property"""
        # Setup responses mock for this test
        responses.add(responses.GET, 'https://usersrv.gigantum.io/key',
                      json={'key': 'afaketoken'}, status=200)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects?search=test-labbook',
                      json=[{
                              "id": 26,
                              "description": "",
                            }],
                      status=200)

        assert gitlab_mngr_fixture._repository_id is None

        # Get token
        repo_id = gitlab_mngr_fixture.repository_id()
        assert repo_id == 26
        assert gitlab_mngr_fixture._repository_id == 26

        # Assert token is returned and set on second call and does not make a request
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects?search=test-labbook', status=400)
        assert repo_id == gitlab_mngr_fixture.repository_id()

    @responses.activate
    def test_exists_true(self, property_mocks_fixture):
        """test the exists method for a repo that should exist"""

        glrm1 = GitLabRepositoryManager("repo.gigantum.io", "usersrv.gigantum.io", "fakeaccesstoken",
                                        "testuser", "testuser", "test-labbook")
        assert glrm1.exists() is True

    @responses.activate
    def test_exists_false(self):
        """test the exists method for a repo that should not exist"""
        responses.add(responses.GET, 'https://usersrv.gigantum.io/key',
                      json={'key': 'afaketoken'}, status=200)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects?search=test-labbook-not-mocked',
                      json=[], status=200)

        glrm2 = GitLabRepositoryManager("repo.gigantum.io", "usersrv.gigantum.io", "fakeaccesstoken",
                                        "testuser", "testuser", "test-labbook-not-mocked")
        assert glrm2.exists() is False

    @responses.activate
    def test_create(self, property_mocks_fixture):
        """test the create method"""
        # Setup responses mock for this test
        responses.add(responses.POST, 'https://repo.gigantum.io/api/v4/projects',
                      json={
                              "id": 27,
                              "description": "",
                            },
                      status=201)

        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects?search=new-labbook',
                      json=[],
                      status=200, match_querystring=True)

        glrm = GitLabRepositoryManager("repo.gigantum.io", "usersrv.gigantum.io", "fakeaccesstoken",
                                       "testuser", "testuser", "new-labbook")

        glrm.create()

        assert glrm.repository_id() == 27

    @responses.activate
    def test_create_errors(self, property_mocks_fixture):
        """test the create method"""
        glrm = GitLabRepositoryManager("repo.gigantum.io", "usersrv.gigantum.io", "fakeaccesstoken",
                                       "testuser", "testuser", "test-labbook")

        # Should fail because the repo "already exists"
        with pytest.raises(ValueError):
            glrm.create()

        # Should fail because the call to gitlab failed
        responses.add(responses.POST, 'https://repo.gigantum.io/api/v4/projects',
                      json={
                              "id": 27,
                              "description": "",
                            },
                      status=400)
        with pytest.raises(ValueError):
            glrm.create()

    @responses.activate
    def test_get_collaborators(self, gitlab_mngr_fixture, property_mocks_fixture):
        """Test the get_collaborators method"""
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/26/members',
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
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/26/members',
                      status=400)

        collaborators = gitlab_mngr_fixture.get_collaborators()

        assert len(collaborators) == 2
        assert collaborators[0] == (29, 'janed', True)
        assert collaborators[1] == (30, 'jd', False)

        # Verify it fails on error to gitlab (should get second mock on second call)
        with pytest.raises(ValueError):
            gitlab_mngr_fixture.get_collaborators()

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
        responses.add(responses.POST, 'https://repo.gigantum.io/api/v4/projects/26/members',
                      json={
                                "id": 100,
                                "name": "New Person",
                                "username": "person100",
                                "state": "active",
                            },
                      status=201)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/26/members',
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

        collaborators = gitlab_mngr_fixture.add_collaborator("person100")

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
        responses.add(responses.POST, 'https://repo.gigantum.io/api/v4/projects/26/members',
                      json={
                                "id": 100,
                                "name": "New Person",
                                "username": "person100",
                                "state": "active",
                            },
                      status=400)

        with pytest.raises(ValueError):
            _ = gitlab_mngr_fixture.add_collaborator("person100")

        with pytest.raises(ValueError):
            _ = gitlab_mngr_fixture.add_collaborator("person100")

    @responses.activate
    def test_delete_collaborator(self, gitlab_mngr_fixture, property_mocks_fixture):
        """Test the delete_collaborator method"""
        responses.add(responses.DELETE, 'https://repo.gigantum.io/api/v4/projects/26/members/100', status=204)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/26/members',
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

        collaborators = gitlab_mngr_fixture.delete_collaborator(100)

        assert len(collaborators) == 1
        assert collaborators[0] == (29, 'janed', True)

    @responses.activate
    def test_delete_collaborator_error(self, gitlab_mngr_fixture, property_mocks_fixture):
        """Test the delete_collaborator method exception handling"""
        responses.add(responses.DELETE, 'https://repo.gigantum.io/api/v4/projects/26/members/100', status=204)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects/26/members',
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
            gitlab_mngr_fixture.delete_collaborator(100)

    @responses.activate
    def test_error_on_missing_repo(self, gitlab_mngr_fixture):
        """Test the exception handling on a repo when it doesn't exist"""
        responses.add(responses.GET, 'https://usersrv.gigantum.io/key',
                      json={'key': 'afaketoken'}, status=200)
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects?search=test-labbook',
                      json=[],
                      status=200, match_querystring=True)

        with pytest.raises(ValueError):
            gitlab_mngr_fixture.get_collaborators()
        with pytest.raises(ValueError):
            gitlab_mngr_fixture.add_collaborator("test")
        with pytest.raises(ValueError):
            gitlab_mngr_fixture.delete_collaborator(100)
