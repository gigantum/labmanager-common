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
                  json=[], status=200)
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
            _ = gitlab_mngr_fixture.repository_id

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
            _ = gitlab_mngr_fixture.repository_id

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
        repo_id = gitlab_mngr_fixture.repository_id
        assert repo_id == 26
        assert gitlab_mngr_fixture._repository_id == 26

        # Assert token is returned and set on second call and does not make a request
        responses.add(responses.GET, 'https://repo.gigantum.io/api/v4/projects?search=test-labbook', status=400)
        assert repo_id == gitlab_mngr_fixture.repository_id
