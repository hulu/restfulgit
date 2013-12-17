# coding=utf-8
from __future__ import absolute_import, unicode_literals

import unittest
from hashlib import sha512
import os
import os.path
import io
from contextlib import contextmanager
from datetime import timedelta

from flask.ext.testing import TestCase as _FlaskTestCase


RESTFULGIT_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PARENT_DIR_OF_RESTFULGIT_REPO = os.path.abspath(os.path.join(RESTFULGIT_REPO, '..'))
os.environ[b'RESTFULGIT_CONFIG'] = os.path.join(RESTFULGIT_REPO, 'example_config.py')
import restfulgit


TEST_SUBDIR = os.path.join(RESTFULGIT_REPO, 'tests')
FIXTURES_DIR = os.path.join(TEST_SUBDIR, 'fixtures')
GIT_MIRROR_DESCRIPTION_FILEPATH = os.path.join(RESTFULGIT_REPO, 'description')
NORMAL_CLONE_DESCRIPTION_FILEPATH = os.path.join(RESTFULGIT_REPO, '.git', 'description')
FIRST_COMMIT = "07b9bf1540305153ceeb4519a50b588c35a35464"
TREE_OF_FIRST_COMMIT = "6ca22167185c31554aa6157306e68dfd612d6345"
BLOB_FROM_FIRST_COMMIT = "ae9d90706c632c26023ce599ac96cb152673da7c"
TAG_FOR_FIRST_COMMIT = "1dffc031c9beda43ff94c526cbc00a30d231c079"
FIFTH_COMMIT = "c04112733fe2db2cb2f179fca1a19365cf15fef5"
IMPROBABLE_SHA = "f" * 40


def delete_file_quietly(filepath):
    try:
        os.remove(filepath)
    except EnvironmentError as err:
        pass


class _RestfulGitTestCase(_FlaskTestCase):
    def create_app(self):
        restfulgit.app.config['RESTFULGIT_REPO_BASE_PATH'] = PARENT_DIR_OF_RESTFULGIT_REPO
        return restfulgit.app

    def assertJsonError(self, resp):
        json = resp.json
        self.assertIsInstance(json, dict)
        self.assertIsInstance(json.get('error'), unicode)

    def assertJson400(self, resp):
        self.assert400(resp)
        self.assertJsonError(resp)

    def assertJson404(self, resp):
        self.assert404(resp)
        self.assertJsonError(resp)

    @contextmanager
    def config_override(self, key, val):
        orig_val = self.app.config[key]
        self.app.config[key] = val
        try:
            yield
        finally:
            self.app.config[key] = orig_val

    def _get_fixture_text(self, filename):
        filepath = os.path.join(FIXTURES_DIR, filename)
        with open(filepath, 'r') as fixture_file:
            return fixture_file.read()

    def assertTextEqualsFixture(self, text, fixture):
        self.assertEqual(text, self._get_fixture_text(fixture))


class RepoKeyTestCase(_RestfulGitTestCase):
    def test_nonexistent_directory(self):
        resp = self.client.get('/repos/this-directory-does-not-exist/git/commits/')
        self.assertJson404(resp)

    def test_directory_is_not_git_repo(self):
        restfulgit.REPO_BASE = RESTFULGIT_REPO
        resp = self.client.get('/repos/test/git/commits/')
        self.assertJson404(resp)

    def test_dot_dot_disallowed(self):
        restfulgit.REPO_BASE = TEST_SUBDIR
        resp = self.client.get('/repos/../git/commits/')
        self.assertJson404(resp)

    def test_list_repos(self):
        resp = self.client.get('/repos/')
        self.assert200(resp)
        result = resp.json
        self.assertIsInstance(result, list)
        repo_list = [repo['name'] for repo in result]
        self.assertIn('restfulgit', repo_list)
        for repo in result:
            if repo['name'] == 'restfulgit':
                self.assertEqual(
                    repo,
                    {
                        "name": 'restfulgit',
                        "full_name": 'restfulgit',
                        "description": None,
                        "url": 'http://localhost/repos/restfulgit/',
                        "branches_url": "http://localhost/repos/restfulgit/branches{/branch}",
                        "tags_url": "http://localhost/repos/restfulgit/tags/",
                        "blobs_url": "http://localhost/repos/restfulgit/git/blobs{/sha}",
                        "git_tags_url": "http://localhost/repos/restfulgit/git/tags{/sha}",
                        "git_refs_url": "http://localhost/repos/restfulgit/git/refs{/sha}",
                        "trees_url": "http://localhost/repos/restfulgit/git/trees{/sha}",
                        # "compare_url": "http://localhost/repos/restfulgit/compare/{base}...{head}",
                        # "contributors_url": "http://localhost/repos/restfulgit/contributors",
                        # "contents_url": "http://localhost/repos/restfulgit/contents/{+path}",
                        "commits_url": "http://localhost/repos/restfulgit/commits{/sha}",
                        "git_commits_url": "http://localhost/repos/restfulgit/git/commits{/sha}",
                        # "size": N (in what units?)
                        # "updated_at": "some timestamp"
                    }
                )


class SHAConverterTestCase(_RestfulGitTestCase):
    def test_empty_sha_rejected(self):
        resp = self.client.get('/repos/restfulgit/git/trees/')
        self.assertJson404(resp)

    def test_too_long_sha_rejected(self):
        resp = self.client.get('/repos/restfulgit/git/trees/{}0/'.format(TREE_OF_FIRST_COMMIT))
        self.assertJson404(resp)

    def test_malformed_sha_rejected(self):
        resp = self.client.get('/repos/restfulgit/git/trees/0123456789abcdefghijklmnopqrstuvwxyzABCD/')
        self.assertJson404(resp)

    def test_full_sha_accepted(self):
        resp = self.client.get('/repos/restfulgit/git/trees/{}/'.format(TREE_OF_FIRST_COMMIT))
        self.assert200(resp)

    def test_partial_sha_accepted(self):
        resp = self.client.get('/repos/restfulgit/git/trees/{}/'.format(TREE_OF_FIRST_COMMIT[:35]))
        self.assert200(resp)


class CommitsTestCase(_RestfulGitTestCase):
    """Tests the "commits" endpoint."""
    def test_nonexistent_start_sha(self):
        resp = self.client.get('/repos/restfulgit/git/commits/?start_sha=1234567890abcdef')
        self.assertJson404(resp)

    def test_non_commit_start_sha(self):
        resp = self.client.get('/repos/restfulgit/git/commits/?start_sha={}'.format(TREE_OF_FIRST_COMMIT))
        self.assertJson400(resp)

    def test_malformed_start_sha(self):
        resp = self.client.get('/repos/restfulgit/git/commits/?start_sha=thisIsNotHexHash')
        self.assertJson400(resp)

    def test_start_sha_works_basic(self):
        resp = self.client.get('/repos/restfulgit/git/commits?start_sha={}'.format(FIRST_COMMIT), follow_redirects=True)
        self.assert200(resp)

    def test_nonexistent_ref_name(self):
        resp = self.client.get('/repos/restfulgit/git/commits/?ref_name=doesNotExist')
        self.assertJson404(resp)

    def test_ref_name_works(self):
        resp = self.client.get('/repos/restfulgit/git/commits?ref_name=master', follow_redirects=True)
        self.assert200(resp)
        # FIXME: should be more thorough

    def test_non_integer_limit_rejected(self):
        resp = self.client.get('/repos/restfulgit/git/commits/?limit=abc123')
        self.assertJson400(resp)

    def test_negative_limit_rejected(self):
        resp = self.client.get('/repos/restfulgit/git/commits/?limit=-1')
        self.assertJson400(resp)

    def test_limit_works_basic(self):
        resp = self.client.get('/repos/restfulgit/git/commits?limit=3', follow_redirects=True)
        self.assert200(resp)

    def test_limit_and_start_sha_work_full(self):
        resp = self.client.get('/repos/restfulgit/git/commits?limit=3&start_sha={}'.format(FIFTH_COMMIT), follow_redirects=True)
        self.assert200(resp)
        self.assertEqual(
            resp.json,
            [
                {
                    'author': {
                        'date': '2013-02-27T03:14:13Z',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'committer': {
                        'date': '2013-02-27T03:14:13Z',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'message': 'add file mode',
                    'parents': [{
                        'sha': '326d80cd68ec3413fe6eaca99c52c59ca428a0d0',
                        'url': 'http://localhost/repos/restfulgit/git/commits/326d80cd68ec3413fe6eaca99c52c59ca428a0d0/'
                    }],
                    'sha': 'c04112733fe2db2cb2f179fca1a19365cf15fef5',
                    'tree': {
                        'sha': '3fdeafb3d2f69a4f7d8bb499b81f836aa10b06eb',
                        'url': 'http://localhost/repos/restfulgit/git/trees/3fdeafb3d2f69a4f7d8bb499b81f836aa10b06eb/'
                    },
                    'url': 'http://localhost/repos/restfulgit/git/commits/c04112733fe2db2cb2f179fca1a19365cf15fef5/'
                },
                {
                    'author': {
                        'date': '2013-02-26T09:15:35Z',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'committer': {
                        'date': '2013-02-26T09:15:35Z',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'message': 'Now using a jsonify decorator which returns the correct content-type',
                    'parents': [{
                        'sha': '1f51b91ac383806df9d322ae67bbad3364f50811',
                        'url': 'http://localhost/repos/restfulgit/git/commits/1f51b91ac383806df9d322ae67bbad3364f50811/'
                    }],
                    'sha': '326d80cd68ec3413fe6eaca99c52c59ca428a0d0',
                    'tree': {
                        'sha': '3f4b1282d80af3f8a51000993968897330635e4f',
                        'url': 'http://localhost/repos/restfulgit/git/trees/3f4b1282d80af3f8a51000993968897330635e4f/'
                    },
                    'url': 'http://localhost/repos/restfulgit/git/commits/326d80cd68ec3413fe6eaca99c52c59ca428a0d0/'
                },
                {
                    'author': {
                        'date': '2013-02-25T12:35:29Z',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'committer': {
                        'date': '2013-02-25T12:35:29Z',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'message': 'Support submodule in tree-listings',
                    'parents': [{
                        'sha': 'ff6405b71273b5c2c50d5c33d5cf962af5390542',
                        'url': 'http://localhost/repos/restfulgit/git/commits/ff6405b71273b5c2c50d5c33d5cf962af5390542/'
                    }],
                    'sha': '1f51b91ac383806df9d322ae67bbad3364f50811',
                    'tree': {
                        'sha': '1404e1766a3269f5a73b3d2ec8c81b7ea3ad6e09',
                        'url': 'http://localhost/repos/restfulgit/git/trees/1404e1766a3269f5a73b3d2ec8c81b7ea3ad6e09/'
                    },
                    'url': 'http://localhost/repos/restfulgit/git/commits/1f51b91ac383806df9d322ae67bbad3364f50811/'
                }
            ]
        )

    #FIXME: test combos


class SimpleSHATestCase(_RestfulGitTestCase):
    def test_get_commit_with_non_commit_sha(self):
        resp = self.client.get('/repos/restfulgit/git/commits/{}/'.format(BLOB_FROM_FIRST_COMMIT))
        self.assertJson404(resp)

    def test_get_tree_with_non_tree_sha(self):
        resp = self.client.get('/repos/restfulgit/git/trees/{}/'.format(BLOB_FROM_FIRST_COMMIT))
        self.assertJson404(resp)

    def test_get_blob_with_non_blob_sha(self):
        resp = self.client.get('/repos/restfulgit/git/blobs/{}/'.format(FIRST_COMMIT))
        self.assertJson404(resp)

    def test_get_tag_with_non_tag_sha(self):
        resp = self.client.get('/repos/restfulgit/git/tags/{}/'.format(BLOB_FROM_FIRST_COMMIT))
        self.assertJson404(resp)

    def test_get_commit_with_nonexistent_sha(self):
        resp = self.client.get('/repos/restfulgit/git/commits/{}/'.format(IMPROBABLE_SHA))
        self.assertJson404(resp)

    def test_get_tree_with_nonexistent_sha(self):
        resp = self.client.get('/repos/restfulgit/git/trees/{}/'.format(IMPROBABLE_SHA))
        self.assertJson404(resp)

    def test_get_blob_with_nonexistent_sha(self):
        resp = self.client.get('/repos/restfulgit/git/blobs/{}/'.format(IMPROBABLE_SHA))
        self.assertJson404(resp)

    def test_get_tag_with_nonexistent_sha(self):
        resp = self.client.get('/repos/restfulgit/git/tags/{}/'.format(IMPROBABLE_SHA))
        self.assertJson404(resp)

    def test_get_git_commit_works(self):
        # From https://api.github.com/repos/hulu/restfulgit/git/commits/07b9bf1540305153ceeb4519a50b588c35a35464 with necessary adjustments
        resp = self.client.get('/repos/restfulgit/git/commits/{}/'.format(FIRST_COMMIT))
        self.assert200(resp)
        self.assertEqual(
            resp.json,
            {
                "sha": "07b9bf1540305153ceeb4519a50b588c35a35464",
                "url": "http://localhost/repos/restfulgit/git/commits/07b9bf1540305153ceeb4519a50b588c35a35464/",
                "author": {
                    "name": "Rajiv Makhijani",
                    "email": "rajiv@hulu.com",
                    "date": "2013-02-24T13:25:46Z"
                },
                "committer": {
                    "name": "Rajiv Makhijani",
                    "email": "rajiv@hulu.com",
                    "date": "2013-02-24T13:25:46Z"
                },
                "tree": {
                    "sha": "6ca22167185c31554aa6157306e68dfd612d6345",
                    "url": "http://localhost/repos/restfulgit/git/trees/6ca22167185c31554aa6157306e68dfd612d6345/"
                },
                "message": "Initial support for read-only REST api for Git plumbing",
                "parents": []
            }
        )

    def test_get_tree_works(self):
        # From https://api.github.com/repos/hulu/restfulgit/git/trees/6ca22167185c31554aa6157306e68dfd612d6345 with necessary adjustments
        resp = self.client.get('/repos/restfulgit/git/trees/{}/'.format(TREE_OF_FIRST_COMMIT))
        self.assert200(resp)
        self.assertEqual(
            resp.json,
            {
                "sha": "6ca22167185c31554aa6157306e68dfd612d6345",
                "url": "http://localhost/repos/restfulgit/git/trees/6ca22167185c31554aa6157306e68dfd612d6345/",
                "tree": [
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "ae9d90706c632c26023ce599ac96cb152673da7c",
                        "path": "api.py",
                        "size": 5543,
                        "url": "http://localhost/repos/restfulgit/git/blobs/ae9d90706c632c26023ce599ac96cb152673da7c/"
                    }
                ]
            }
        )

    def test_get_nested_tree_works(self):
        # From https://api.github.com/repos/hulu/restfulgit/git/trees/fc0fddc986c93f8444d754c7ec93c8b87f3d7c7e with necessary adjustments
        resp = self.client.get('/repos/restfulgit/git/trees/fc0fddc986c93f8444d754c7ec93c8b87f3d7c7e/')
        self.assert200(resp)
        self.assertEqual(
            resp.json,
            {
                "sha": "fc0fddc986c93f8444d754c7ec93c8b87f3d7c7e",
                "url": "http://localhost/repos/restfulgit/git/trees/fc0fddc986c93f8444d754c7ec93c8b87f3d7c7e/",
                "tree": [
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "b5d2ce6a7246f37aaa41e7ce3403b5acd6369914",
                        "path": ".coveragerc",
                        "size": 65,
                        "url": "http://localhost/repos/restfulgit/git/blobs/b5d2ce6a7246f37aaa41e7ce3403b5acd6369914/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "cae6643e19e7a8198a26a449f556db6d1909aec8",
                        "path": ".gitignore",
                        "size": 22,
                        "url": "http://localhost/repos/restfulgit/git/blobs/cae6643e19e7a8198a26a449f556db6d1909aec8/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "f93712aaf5fcc4c0d44dc472d86abad40fdb0ec3",
                        "path": ".pep8",
                        "size": 19,
                        "url": "http://localhost/repos/restfulgit/git/blobs/f93712aaf5fcc4c0d44dc472d86abad40fdb0ec3/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "14e6bf5b229127a5495d9c176f50e3ef1922f0f2",
                        "path": ".travis.yml",
                        "size": 985,
                        "url": "http://localhost/repos/restfulgit/git/blobs/14e6bf5b229127a5495d9c176f50e3ef1922f0f2/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "bb27aa0a502f73c19837b96d1bd514ba95e0d404",
                        "path": "LICENSE.md",
                        "size": 1056,
                        "url": "http://localhost/repos/restfulgit/git/blobs/bb27aa0a502f73c19837b96d1bd514ba95e0d404/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "342f0ffead9243f5a3514505b83b918e61247ae2",
                        "path": "README.md",
                        "size": 5655,
                        "url": "http://localhost/repos/restfulgit/git/blobs/342f0ffead9243f5a3514505b83b918e61247ae2/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "20ff5b895391daa7335cc55be7e3a4da601982da",
                        "path": "config.conf",
                        "size": 398,
                        "url": "http://localhost/repos/restfulgit/git/blobs/20ff5b895391daa7335cc55be7e3a4da601982da/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "3e4025298468787af1123191bdddfb72df19061a",
                        "path": "pylint.rc",
                        "size": 8529,
                        "url": "http://localhost/repos/restfulgit/git/blobs/3e4025298468787af1123191bdddfb72df19061a/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "77b71e4967983b090aef88ba358724ef4703b01b",
                        "path": "requirements.txt",
                        "size": 29,
                        "url": "http://localhost/repos/restfulgit/git/blobs/77b71e4967983b090aef88ba358724ef4703b01b/"
                    },
                    {
                        "mode": "040000",
                        "type": "tree",
                        "sha": "dd8a3571820936595e553c9ba9f776a5c77b1a53",
                        "path": "restfulgit",
                        "url": "http://localhost/repos/restfulgit/git/trees/dd8a3571820936595e553c9ba9f776a5c77b1a53/"
                    },
                    {
                        "mode": "040000",
                        "type": "tree",
                        "sha": "bdcb3627ba5b29da20f01d9c4571b0ebc6a8b2bd",
                        "path": "tests",
                        "url": "http://localhost/repos/restfulgit/git/trees/bdcb3627ba5b29da20f01d9c4571b0ebc6a8b2bd/"
                    }
                ]
            }
        )

    def test_get_recursive_tree_works(self):
        # From https://api.github.com/repos/hulu/restfulgit/git/trees/fc36ceb418b0b9e945ffd3706dd8544dd988500a?recursive=1 with necessary adjustments
        resp = self.client.get('/repos/restfulgit/git/trees/fc36ceb418b0b9e945ffd3706dd8544dd988500a/?recursive=1')
        self.assert200(resp)
        self.assertEqual(
            resp.json,
            {
                "sha": "fc36ceb418b0b9e945ffd3706dd8544dd988500a",
                "url": "http://localhost/repos/restfulgit/git/trees/fc36ceb418b0b9e945ffd3706dd8544dd988500a/",
                "tree": [
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "b5d2ce6a7246f37aaa41e7ce3403b5acd6369914",
                        "path": ".coveragerc",
                        "size": 65,
                        "url": "http://localhost/repos/restfulgit/git/blobs/b5d2ce6a7246f37aaa41e7ce3403b5acd6369914/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "cae6643e19e7a8198a26a449f556db6d1909aec8",
                        "path": ".gitignore",
                        "size": 22,
                        "url": "http://localhost/repos/restfulgit/git/blobs/cae6643e19e7a8198a26a449f556db6d1909aec8/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "f93712aaf5fcc4c0d44dc472d86abad40fdb0ec3",
                        "path": ".pep8",
                        "size": 19,
                        "url": "http://localhost/repos/restfulgit/git/blobs/f93712aaf5fcc4c0d44dc472d86abad40fdb0ec3/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "b3e1e0f2b569fef46e7413cadb6778504c19c87f",
                        "path": ".travis.yml",
                        "size": 1008,
                        "url": "http://localhost/repos/restfulgit/git/blobs/b3e1e0f2b569fef46e7413cadb6778504c19c87f/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "bb27aa0a502f73c19837b96d1bd514ba95e0d404",
                        "path": "LICENSE.md",
                        "size": 1056,
                        "url": "http://localhost/repos/restfulgit/git/blobs/bb27aa0a502f73c19837b96d1bd514ba95e0d404/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "ee655c4baa251fad0a67dd74b2c390b4a4f9ac53",
                        "path": "README.md",
                        "size": 7855,
                        "url": "http://localhost/repos/restfulgit/git/blobs/ee655c4baa251fad0a67dd74b2c390b4a4f9ac53/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "7186d8fab5c4bb492cbcfe1383b2270651e13c2e",
                        "path": "example_config.py",
                        "size": 489,
                        "url": "http://localhost/repos/restfulgit/git/blobs/7186d8fab5c4bb492cbcfe1383b2270651e13c2e/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "abb1a23bc0fad8f7fe1dc5996a8e4c7c4cb9903e",
                        "path": "pylint.rc",
                        "size": 8517,
                        "url": "http://localhost/repos/restfulgit/git/blobs/abb1a23bc0fad8f7fe1dc5996a8e4c7c4cb9903e/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "77b71e4967983b090aef88ba358724ef4703b01b",
                        "path": "requirements.txt",
                        "size": 29,
                        "url": "http://localhost/repos/restfulgit/git/blobs/77b71e4967983b090aef88ba358724ef4703b01b/"
                    },
                    {
                        "mode": "040000",
                        "type": "tree",
                        "sha": "c0dcf8f58a3c5bf42f07e880d5e442ef124c9370",
                        "path": "restfulgit",
                        "url": "http://localhost/repos/restfulgit/git/trees/c0dcf8f58a3c5bf42f07e880d5e442ef124c9370/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "7fe178c5687eae1e2c04d9d21b6a429c93a28e6a",
                        "path": "restfulgit/__init__.py",
                        "size": 15986,
                        "url": "http://localhost/repos/restfulgit/git/blobs/7fe178c5687eae1e2c04d9d21b6a429c93a28e6a/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "e067d7f361bd3b0f227ba1914c227ebf9539f59d",
                        "path": "restfulgit/__main__.py",
                        "size": 110,
                        "url": "http://localhost/repos/restfulgit/git/blobs/e067d7f361bd3b0f227ba1914c227ebf9539f59d/"
                    },
                    {
                        "mode": "040000",
                        "type": "tree",
                        "sha": "803c8592dd96cb0a6fc041ebb6af71fbf1f7551c",
                        "path": "tests",
                        "url": "http://localhost/repos/restfulgit/git/trees/803c8592dd96cb0a6fc041ebb6af71fbf1f7551c/"
                    },
                    {
                        "mode": "100644",
                        "type": "blob",
                        "sha": "2d500fea50b6c1a38d972c1a22b5cb5b5673167a",
                        "path": "tests/test_restfulgit.py",
                        "size": 26725,
                        "url": "http://localhost/repos/restfulgit/git/blobs/2d500fea50b6c1a38d972c1a22b5cb5b5673167a/"
                    }
                ]
            }
        )

    def test_get_blob_works(self):
        # From https://api.github.com/repos/hulu/restfulgit/git/blobs/ae9d90706c632c26023ce599ac96cb152673da7c with necessary adjustments
        resp = self.client.get('/repos/restfulgit/git/blobs/{}/'.format(BLOB_FROM_FIRST_COMMIT))
        self.assert200(resp)
        json = resp.json
        self.assertIsInstance(json, dict)
        self.assertIn("data", json)
        self.assertEqual(
            sha512(json["data"]).hexdigest(),
            '1c846bb4d44c08073c487316a7dc02d97d825aecf50546caf9bf10277c01d17e19860d5f86de877268dd969bd081c7595991c325e0ab492374b956e3a6c9967f'
        )
        del json["data"]
        self.assertEqual(
            json,
            {
                "url": "http://localhost/repos/restfulgit/git/blobs/ae9d90706c632c26023ce599ac96cb152673da7c/",
                "sha": "ae9d90706c632c26023ce599ac96cb152673da7c",
                "encoding": "utf-8",  # NOTE: RestfulGit extension
                "size": 5543
            }
        )

    def test_get_binary_blob_works(self):
        pass

    def test_get_tag_works(self):
        # From https://api.github.com/repos/hulu/restfulgit/git/tags/1dffc031c9beda43ff94c526cbc00a30d231c079 with necessary adjustments
        resp = self.client.get('/repos/restfulgit/git/tags/{}/'.format(TAG_FOR_FIRST_COMMIT))
        self.assert200(resp)
        self.assertEqual(
            resp.json,
            {
                "sha": "1dffc031c9beda43ff94c526cbc00a30d231c079",
                "url": "http://localhost/repos/restfulgit/git/tags/1dffc031c9beda43ff94c526cbc00a30d231c079/",
                "tagger": {
                    "name": "Chris Rebert",
                    "email": "chris.rebert@hulu.com",
                    "date": "2013-09-28T01:14:09Z"
                },
                "object": {
                    "sha": "07b9bf1540305153ceeb4519a50b588c35a35464",
                    "type": "commit",
                    "url": "http://localhost/repos/restfulgit/git/commits/07b9bf1540305153ceeb4519a50b588c35a35464/"
                },
                "tag": "initial",
                "message": "initial commit\n"
            }
        )

    def test_get_repos_tag_works(self):  # NOTE: RestfulGit extension
        resp = self.client.get('/repos/restfulgit/tags/initial/')
        self.assert200(resp)
        self.assertEqual(resp.json, {
            'commit': {
                'author': {
                    'date': '2013-02-24T13:25:46Z',
                    'email': 'rajiv@hulu.com',
                    'name': 'Rajiv Makhijani'
                },
                'commit': {
                    'author': {
                        'date': '2013-02-24T13:25:46Z',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'committer': {
                        'date': '2013-02-24T13:25:46Z',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'message': 'Initial support for read-only REST api for Git plumbing',
                    'parents': [],
                    'sha': '07b9bf1540305153ceeb4519a50b588c35a35464',
                    'tree': {
                        'sha': '6ca22167185c31554aa6157306e68dfd612d6345',
                        'url': 'http://localhost/repos/restfulgit/git/trees/6ca22167185c31554aa6157306e68dfd612d6345/'
                    },
                    'url': 'http://localhost/repos/restfulgit/git/commits/07b9bf1540305153ceeb4519a50b588c35a35464/'
                },
               'committer': {
                    'date': '2013-02-24T13:25:46Z',
                    'email': 'rajiv@hulu.com',
                    'name': 'Rajiv Makhijani'
                },
                'parents': [],
                'sha': '07b9bf1540305153ceeb4519a50b588c35a35464',
                'url': 'http://localhost/repos/restfulgit/commits/07b9bf1540305153ceeb4519a50b588c35a35464/'
            },
            'name': 'initial',
            'tag': {
                'message': 'initial commit\n',
                'object': {
                    'sha': '07b9bf1540305153ceeb4519a50b588c35a35464',
                    'type': 'commit',
                    'url': 'http://localhost/repos/restfulgit/git/commits/07b9bf1540305153ceeb4519a50b588c35a35464/'
                },
            'sha': '1dffc031c9beda43ff94c526cbc00a30d231c079',
            'tag': 'initial',
            'tagger': {
                'date': '2013-09-28T01:14:09Z',
                'email': 'chris.rebert@hulu.com',
                'name': 'Chris Rebert'
            },
            'url': 'http://localhost/repos/restfulgit/git/tags/1dffc031c9beda43ff94c526cbc00a30d231c079/'
        },
        'url': 'http://localhost/repos/restfulgit/tags/initial/'
    })

    def test_get_repos_tag_with_nonexistent_tag(self):  # NOTE: RestfulGit extension
        resp = self.client.get('/repos/restfulgit/tags/this-tag-does-not-exist/')
        self.assertJson404(resp)

    def test_get_repo_tags_works(self):
        # From https://api.github.com/repos/hulu/restfulgit/tags with necessary adjustments
        reference_tag = {
            "name": "initial",
            "commit": {
                "sha": "07b9bf1540305153ceeb4519a50b588c35a35464",
                "url": "http://localhost/repos/restfulgit/commits/07b9bf1540305153ceeb4519a50b588c35a35464/"
            }
        }
        resp = self.client.get('/repos/restfulgit/tags/')
        self.assert200(resp)
        json = resp.json
        self.assertIsInstance(json, list)
        for tag in json:
            self.assertIsInstance(tag, dict)
            self.assertIn('name', tag)
        initial_tags = [tag for tag in json if tag['name'] == 'initial']
        self.assertEqual(len(initial_tags), 1)
        initial_tag = initial_tags[0]
        self.assertEqual(reference_tag, initial_tag)

    def test_get_repo_tags_with_nonexistent_repo(self):
        resp = self.client.get('/repos/this-repo-does-not-exist/tags/')
        self.assertJson404(resp)

    def test_get_repo_branches_works(self):
        # From https://api.github.com/repos/hulu/restfulgit/branches with necessary adjustments
        reference_branch = {
            "name": "ambiguous",
            "commit": {
                "sha": "1f51b91ac383806df9d322ae67bbad3364f50811",
                "url": "http://localhost/repos/restfulgit/commits/1f51b91ac383806df9d322ae67bbad3364f50811/"
            }
        }
        resp = self.client.get('/repos/restfulgit/branches/')
        self.assert200(resp)
        json = resp.json
        self.assertIsInstance(json, list)
        for branch in json:
            self.assertIsInstance(branch, dict)
            self.assertIn('name', branch)
        ambiguous_branches = [branch for branch in json if branch['name'] == 'ambiguous']
        self.assertEqual(len(ambiguous_branches), 1)
        ambiguous_branch = ambiguous_branches[0]
        self.assertEqual(reference_branch, ambiguous_branch)

    def test_get_repo_branches_with_nonexistent_repo(self):
        resp = self.client.get('/repos/this-repo-does-not-exist/branches/')
        self.assertJson404(resp)

    def test_get_repo_branch_works(self):
        # From https://api.github.com/repos/hulu/restfulgit/branches/ambiguous with necessary adjustments
        reference = {
            "name": "ambiguous",
            "commit": {
                "sha": "1f51b91ac383806df9d322ae67bbad3364f50811",
                "commit": {
                    "author": {
                        "name": "Rajiv Makhijani",
                        "email": "rajiv@hulu.com",
                        "date": "2013-02-25T12:35:29Z"
                    },
                    "committer": {
                        "name": "Rajiv Makhijani",
                        "email": "rajiv@hulu.com",
                        "date": "2013-02-25T12:35:29Z"
                    },
                    "message": "Support submodule in tree-listings",
                    "tree": {
                        "sha": "1404e1766a3269f5a73b3d2ec8c81b7ea3ad6e09",
                        "url": "http://localhost/repos/restfulgit/git/trees/1404e1766a3269f5a73b3d2ec8c81b7ea3ad6e09/"
                    },
                    "url": "http://localhost/repos/restfulgit/git/commits/1f51b91ac383806df9d322ae67bbad3364f50811/",
                    "sha": "1f51b91ac383806df9d322ae67bbad3364f50811",  # NOTE: RestfulGit extension
                    "parents": [  # NOTE: RestfulGit extension
                        {
                            "sha": "ff6405b71273b5c2c50d5c33d5cf962af5390542",
                            "url": "http://localhost/repos/restfulgit/commits/ff6405b71273b5c2c50d5c33d5cf962af5390542/",
                        }
                    ]
                },
                "url": "http://localhost/repos/restfulgit/commits/1f51b91ac383806df9d322ae67bbad3364f50811/",
                "author": {
                    "name": "Rajiv Makhijani",
                    "email": "rajiv@hulu.com",
                    "date": "2013-02-25T12:35:29Z"
                },
                "committer": {
                    "name": "Rajiv Makhijani",
                    "email": "rajiv@hulu.com",
                    "date": "2013-02-25T12:35:29Z"
                },
                "parents": [
                    {
                        "sha": "ff6405b71273b5c2c50d5c33d5cf962af5390542",
                        "url": "http://localhost/repos/restfulgit/commits/ff6405b71273b5c2c50d5c33d5cf962af5390542/",
                    }
                ]
            },
            "_links": {
                "self": "http://localhost/repos/restfulgit/branches/ambiguous/",
            },
            'url': 'http://localhost/repos/restfulgit/branches/ambiguous/'
        }
        resp = self.client.get('/repos/restfulgit/branches/ambiguous/')
        self.assert200(resp)
        json = resp.json
        self.assertEqual(reference, json)

    def test_get_repo_branch_with_nonexistent_branch(self):
        resp = self.client.get('/repos/restfulgit/branches/this-branch-does-not-exist/')
        self.assertJson404(resp)

    def test_get_repo_commit_works(self):
        # From https://api.github.com/repos/hulu/restfulgit/commits/d408fc2428bc6444cabd7f7b46edbe70b6992b16 with necessary adjustments
        reference = {
            "sha": "d408fc2428bc6444cabd7f7b46edbe70b6992b16",
            "commit": {
                "author": {
                    "name": "Rajiv Makhijani",
                    "email": "rajiv@hulu.com",
                    "date": "2013-04-21T11:20:14Z"
                },
                "committer": {
                    "name": "Rajiv Makhijani",
                    "email": "rajiv@hulu.com",
                    "date": "2013-04-21T11:20:14Z"
                },
                "message": "Added requirements.txt + more README",
                "tree": {
                    "sha": "e49e456564f8d852f430c1d0028a9d6560e3f3e9",
                    "url": "http://localhost/repos/restfulgit/git/trees/e49e456564f8d852f430c1d0028a9d6560e3f3e9/"
                },
                "url": "http://localhost/repos/restfulgit/git/commits/d408fc2428bc6444cabd7f7b46edbe70b6992b16/",
                "sha": "d408fc2428bc6444cabd7f7b46edbe70b6992b16",  # NOTE: RestfulGit extension
                "parents": [  # NOTE: RestfulGit extension
                    {
                        "sha": "c92de24597eff312bbdd5a70059665a2e3000590",
                        "url": "http://localhost/repos/restfulgit/commits/c92de24597eff312bbdd5a70059665a2e3000590/",
                    }
                ],
            },
            "url": "http://localhost/repos/restfulgit/commits/d408fc2428bc6444cabd7f7b46edbe70b6992b16/",
            "author": {
                "name": "Rajiv Makhijani",
                "email": "rajiv@hulu.com",
                "date": "2013-04-21T11:20:14Z"
            },
            "committer": {
                "name": "Rajiv Makhijani",
                "email": "rajiv@hulu.com",
                "date": "2013-04-21T11:20:14Z"
            },
            "parents": [
                {
                    "sha": "c92de24597eff312bbdd5a70059665a2e3000590",
                    "url": "http://localhost/repos/restfulgit/commits/c92de24597eff312bbdd5a70059665a2e3000590/",
                }
            ],
            "stats": {
                "total": 10,
                "additions": 10,
                "deletions": 0
            },
            "files": [
                {
                    "sha": "c65dc8c22cc3dc5d37a1c39e5a9f336f1dd6fe34",
                    "filename": "README.md",
                    "status": "modified",
                    "additions": 5,
                    "deletions": 0,
                    "changes": 5,
                    "raw_url": "http://localhost/repos/restfulgit/raw/d408fc2428bc6444cabd7f7b46edbe70b6992b16/README.md",
                    "contents_url": "http://localhost/repos/restfulgit/contents/README.md?ref=d408fc2428bc6444cabd7f7b46edbe70b6992b16",
                    "patch": "@@ -4,6 +4,11 @@ REST API for Git data\n Provides a read-only restful interface for accessing data from Git repositories (local to the server).\n Modeled off the GitHub Git DB API for compatibility (see http://developer.github.com/v3/git/).\n \n+Requires: flask, pygit2 (>= 0.18.1), libgit2 (>= 0.18).\n+Must modify: REPO_BASE (root path for repositories, note only repositories immediately under this path are currently supported).\n+\n+api.py is a valid WSGI application.\n+\n --\n \n All of these routes return JSON unless otherwise specified."
                },
                {
                    "sha": "da23f6c1cf961369faa90c8c4f4c242a09205ce6",
                    "filename": "requirements.txt",
                    "status": "added",
                    "additions": 5,
                    "deletions": 0,
                    "changes": 5,
                    "raw_url": "http://localhost/repos/restfulgit/raw/d408fc2428bc6444cabd7f7b46edbe70b6992b16/requirements.txt",
                    "contents_url": "http://localhost/repos/restfulgit/contents/requirements.txt?ref=d408fc2428bc6444cabd7f7b46edbe70b6992b16",
                    "patch": "@@ -0,0 +1,5 @@\n+Flask==0.9\n+Jinja2==2.6\n+Werkzeug==0.8.3\n+pygit2==0.18.1\n+wsgiref==0.1.2"
                }
            ]
        }
        resp = self.client.get('/repos/restfulgit/commits/d408fc2428bc6444cabd7f7b46edbe70b6992b16/')
        self.assert200(resp)
        self.assertEqual(reference, resp.json)

    def test_get_repo_commit_with_nonexistent_sha(self):
        resp = self.client.get('/repos/restfulgit/commits/{}/'.format(IMPROBABLE_SHA))
        self.assertJson404(resp)

    def test_get_diff_works(self):
        resp = self.client.get('/repos/restfulgit/commit/d408fc2428bc6444cabd7f7b46edbe70b6992b16.diff')
        self.assert200(resp)
        self.assertEqual(resp.headers.get_all('Content-Type'), [b'text/x-diff; charset=utf-8'])
        self.assertTextEqualsFixture(resp.get_data(), 'd408fc2428bc6444cabd7f7b46edbe70b6992b16.diff')

    def test_get_diff_with_parentless_commit(self):  # NOTE: RestfulGit extension; GitHub gives a 404 in this case
        resp = self.client.get('/repos/restfulgit/commit/07b9bf1540305153ceeb4519a50b588c35a35464.diff')
        self.assert200(resp)
        self.assertEqual(resp.headers.get_all('Content-Type'), [b'text/x-diff; charset=utf-8'])
        self.assertTextEqualsFixture(resp.get_data(), '07b9bf1540305153ceeb4519a50b588c35a35464.diff')

    def test_get_diff_with_nonexistent_sha(self):
        resp = self.client.get('/repos/restfulgit/commit/{}.diff'.format(IMPROBABLE_SHA))
        self.assertJson404(resp)


class RefsTestCase(_RestfulGitTestCase):
    def test_get_refs_works(self):
        # From https://api.github.com/repos/hulu/restfulgit/git/refs with necessary adjustments
        reference_initial_tag_ref = {
            "ref": "refs/tags/initial",
            "url": "http://localhost/repos/restfulgit/git/refs/tags/initial",
            "object": {
                "sha": "1dffc031c9beda43ff94c526cbc00a30d231c079",
                "type": "tag",
                "url": "http://localhost/repos/restfulgit/git/tags/1dffc031c9beda43ff94c526cbc00a30d231c079/"
            }
        }
        reference_ambiguous_branch_ref = {
            "ref": "refs/heads/ambiguous",
            "url": "http://localhost/repos/restfulgit/git/refs/heads/ambiguous",
            "object": {
                "sha": "1f51b91ac383806df9d322ae67bbad3364f50811",
                "type": "commit",
                "url": "http://localhost/repos/restfulgit/git/commits/1f51b91ac383806df9d322ae67bbad3364f50811/"
            }
        }
        resp = self.client.get('/repos/restfulgit/git/refs/')
        self.assert200(resp)
        ref_list = resp.json
        self.assertIsInstance(ref_list, list)
        self.assertIn(reference_initial_tag_ref, ref_list)
        self.assertIn(reference_ambiguous_branch_ref, ref_list)

    def test_invalid_ref_path(self):
        resp = self.client.get('/repos/restfulgit/git/refs/this_ref/path_does/not_exist')
        self.assert200(resp)
        self.assertEqual([], resp.json)

    def test_valid_specific_ref_path(self):
        # Frpm https://api.github.com/repos/hulu/restfulgit/git/refs/tags/initial with necessary adjustments
        resp = self.client.get('/repos/restfulgit/git/refs/tags/initial')
        self.assert200(resp)
        self.assertEqual(
            resp.json,
            {
                "url": "http://localhost/repos/restfulgit/git/refs/tags/initial",
                "object": {
                    "url": "http://localhost/repos/restfulgit/git/tags/1dffc031c9beda43ff94c526cbc00a30d231c079/",
                    "sha": "1dffc031c9beda43ff94c526cbc00a30d231c079",
                    "type": "tag"
                },
                "ref": "refs/tags/initial"
            }
        )


class RawFileTestCase(_RestfulGitTestCase):
    def test_nonexistent_branch(self):
        resp = self.client.get('/repos/restfulgit/raw/this-branch-does-not-exist/LICENSE.md')
        self.assertJson404(resp)

    def test_nonexistent_file_path(self):
        resp = self.client.get('/repos/restfulgit/raw/master/this_path/does_not/exist.txt')
        self.assertJson404(resp)

    def test_mime_type_logic(self):
        # FIXME: implement
        pass

    def test_branches_trump_tags(self):
        # branch "ambiguous" = commit 1f51b91
        #     api.py's SHA-512 = e948e8d0b0d0703d972279382a002c90040ff19d636e96927262d63e1f1429526539ea781744d2f3a65a5938b59e0c5f57adadc26f797480efcfc6f7dcff3d81
        # tag "ambiguous" = commit ff6405b
        #     api.py's SHA-512 = a50e02753d282c0e35630bbbc16a525ea4e0b2e2af668135b603c8e1467c7269bcbe9075886baf3f08ce195a7eab1e0b8179080af08a2c0f3eda3b9518650fa1
        resp = self.client.get("/repos/restfulgit/raw/ambiguous/api.py")
        self.assert200(resp)
        self.assertEqual(
            'e948e8d0b0d0703d972279382a002c90040ff19d636e96927262d63e1f1429526539ea781744d2f3a65a5938b59e0c5f57adadc26f797480efcfc6f7dcff3d81',
            sha512(resp.data).hexdigest()
        )

    def test_sha_works(self):
        resp = self.client.get('/repos/restfulgit/raw/326d80cd68ec3413fe6eaca99c52c59ca428a0d0/api.py')
        self.assert200(resp)
        self.assertEqual(
            '0229e0a11f6a3c8c9b84c50ecbd54d476edf5c0767137e37526d1961210530aa6bd93f67a70bd4ea1998d65cdbe74c7fd8b90482ef5cbdf244cc697e3135e497',
            sha512(resp.data).hexdigest()
        )

    def test_tag_works(self):
        resp = self.client.get('/repos/restfulgit/raw/initial/api.py')
        self.assert200(resp)
        self.assertEqual(
            '1c846bb4d44c08073c487316a7dc02d97d825aecf50546caf9bf10277c01d17e19860d5f86de877268dd969bd081c7595991c325e0ab492374b956e3a6c9967f',
            sha512(resp.data).hexdigest()
        )

    def test_branch_works(self):
        resp = self.client.get('/repos/restfulgit/raw/master/LICENSE.md')
        self.assert200(resp)
        self.assertEqual(
            '7201955547d83fb4e740adf52d95c3044591ec8b60e4a136f5486a05d1dfaac2bd44d4546830cf0f32d05b40ce5928d0b3f71e0b2628488ea0db1427a6dd2988',
            sha512(resp.data).hexdigest()
        )


class RepositoryInfoCase(_RestfulGitTestCase):
    def test_no_description_file(self):
        delete_file_quietly(NORMAL_CLONE_DESCRIPTION_FILEPATH)
        delete_file_quietly(GIT_MIRROR_DESCRIPTION_FILEPATH)
        resp = self.client.get('/repos/restfulgit/')
        self.assert200(resp)
        self.assertEqual(
            resp.json,
            {
                'blobs_url': 'http://localhost/repos/restfulgit/git/blobs{/sha}',
                'branches_url': 'http://localhost/repos/restfulgit/branches{/branch}',
                'commits_url': 'http://localhost/repos/restfulgit/commits{/sha}',
                'description': None,
                'full_name': 'restfulgit',
                'git_commits_url': 'http://localhost/repos/restfulgit/git/commits{/sha}',
                'git_refs_url': 'http://localhost/repos/restfulgit/git/refs{/sha}',
                'git_tags_url': 'http://localhost/repos/restfulgit/git/tags{/sha}',
                'name': 'restfulgit',
                'tags_url': 'http://localhost/repos/restfulgit/tags/',
                'trees_url': 'http://localhost/repos/restfulgit/git/trees{/sha}',
                'url': 'http://localhost/repos/restfulgit/',
            }
        )

    def test_default_description_file(self):
        with io.open(NORMAL_CLONE_DESCRIPTION_FILEPATH, mode='wt', encoding='utf-8') as description_file:
            description_file.write("Unnamed repository; edit this file 'description' to name the repository.\n")
        try:
            resp = self.client.get('/repos/restfulgit/')
            self.assert200(resp)
            self.assertEqual(
                resp.json,
                {
                    'blobs_url': 'http://localhost/repos/restfulgit/git/blobs{/sha}',
                    'branches_url': 'http://localhost/repos/restfulgit/branches{/branch}',
                    'commits_url': 'http://localhost/repos/restfulgit/commits{/sha}',
                    'description': None,
                    'full_name': 'restfulgit',
                    'git_commits_url': 'http://localhost/repos/restfulgit/git/commits{/sha}',
                    'git_refs_url': 'http://localhost/repos/restfulgit/git/refs{/sha}',
                    'git_tags_url': 'http://localhost/repos/restfulgit/git/tags{/sha}',
                    'name': 'restfulgit',
                    'tags_url': 'http://localhost/repos/restfulgit/tags/',
                    'trees_url': 'http://localhost/repos/restfulgit/git/trees{/sha}',
                    'url': 'http://localhost/repos/restfulgit/',
                }
            )
        finally:
            delete_file_quietly(NORMAL_CLONE_DESCRIPTION_FILEPATH)

    def test_dot_dot_disallowed(self):
        restfulgit.REPO_BASE = TEST_SUBDIR
        resp = self.client.get('/repos/../')
        self.assertJson404(resp)

    def test_nonexistent_repo(self):
        restfulgit.REPO_BASE = RESTFULGIT_REPO
        resp = self.client.get('/repos/test/')
        self.assertJson404(resp)

    def test_works_normal_clone(self):
        description = "REST API for Git data\n"
        with io.open(NORMAL_CLONE_DESCRIPTION_FILEPATH, mode='wt', encoding='utf-8') as description_file:
            description_file.write(description)
        try:
            resp = self.client.get('/repos/restfulgit/')
            self.assertEqual(
                resp.json,
                {
                    'blobs_url': 'http://localhost/repos/restfulgit/git/blobs{/sha}',
                    'branches_url': 'http://localhost/repos/restfulgit/branches{/branch}',
                    'commits_url': 'http://localhost/repos/restfulgit/commits{/sha}',
                    'description': description,
                    'full_name': 'restfulgit',
                    'git_commits_url': 'http://localhost/repos/restfulgit/git/commits{/sha}',
                    'git_refs_url': 'http://localhost/repos/restfulgit/git/refs{/sha}',
                    'git_tags_url': 'http://localhost/repos/restfulgit/git/tags{/sha}',
                    'name': 'restfulgit',
                    'tags_url': 'http://localhost/repos/restfulgit/tags/',
                    'trees_url': 'http://localhost/repos/restfulgit/git/trees{/sha}',
                    'url': 'http://localhost/repos/restfulgit/',
                }
            )
        finally:
            delete_file_quietly(NORMAL_CLONE_DESCRIPTION_FILEPATH)

    def test_works_git_mirror(self):
        description = "REST API for Git data\n"
        with io.open(GIT_MIRROR_DESCRIPTION_FILEPATH, mode='wt', encoding='utf-8') as description_file:
            description_file.write(description)
        try:
            resp = self.client.get('/repos/restfulgit/')
            self.assertEqual(
                resp.json,
                {
                    'blobs_url': 'http://localhost/repos/restfulgit/git/blobs{/sha}',
                    'branches_url': 'http://localhost/repos/restfulgit/branches{/branch}',
                    'commits_url': 'http://localhost/repos/restfulgit/commits{/sha}',
                    'description': description,
                    'full_name': 'restfulgit',
                    'git_commits_url': 'http://localhost/repos/restfulgit/git/commits{/sha}',
                    'git_refs_url': 'http://localhost/repos/restfulgit/git/refs{/sha}',
                    'git_tags_url': 'http://localhost/repos/restfulgit/git/tags{/sha}',
                    'name': 'restfulgit',
                    'tags_url': 'http://localhost/repos/restfulgit/tags/',
                    'trees_url': 'http://localhost/repos/restfulgit/git/trees{/sha}',
                    'url': 'http://localhost/repos/restfulgit/',
                }
            )
        finally:
            delete_file_quietly(GIT_MIRROR_DESCRIPTION_FILEPATH)


class CorsTestCase(_RestfulGitTestCase):
    @property
    @contextmanager
    def cors_enabled(self):
        with self.config_override('RESTFULGIT_ENABLE_CORS', True):
            yield

    @property
    def arbitrary_response(self):
        resp = self.client.get('/repos/restfulgit/raw/master/LICENSE.md')
        self.assert200(resp)
        return resp

    def assert_header_equal(self, header, value):
        resp = self.arbitrary_response
        headers = resp.headers
        self.assertIn(header, headers)
        self.assertEqual(headers[header], value)

    def assert_cors_enabled_for(self, resp):
        self.assertIn('Access-Control-Allow-Methods', resp.headers)
        self.assertIn('Access-Control-Allow-Origin', resp.headers)
        self.assertIn('Access-Control-Allow-Credentials', resp.headers)

    def assert_cors_disabled_for(self, resp):
        for header in resp.headers.keys():
            self.assertFalse(header.lower().startswith('access-control'), msg="CORS-related header present")

    def test_disabled_really_disables(self):
        with self.config_override('RESTFULGIT_ENABLE_CORS', False):
            self.assert_cors_disabled_for(self.arbitrary_response)

    def test_enabled_really_enables(self):
        with self.config_override('RESTFULGIT_ENABLE_CORS', True):
            self.assert_cors_enabled_for(self.arbitrary_response)

    def test_disabled_disables_preflight(self):
        with self.config_override('RESTFULGIT_ENABLE_CORS', False):
            resp = self.client.options('/repos/restfulgit/raw/master/LICENSE.md')
            self.assert200(resp)
            self.assert_cors_disabled_for(resp)

    def test_enabled_enables_preflight(self):
        with self.config_override('RESTFULGIT_ENABLE_CORS', True):
            resp = self.client.options('/repos/restfulgit/raw/master/LICENSE.md')
            self.assert200(resp)
            self.assert_cors_enabled_for(resp)

    def test_specific_allowed_origin_honored(self):
        origin = 'https://foo.bar.baz:90'
        with self.cors_enabled:
            with self.config_override('RESTFULGIT_CORS_ALLOWED_ORIGIN', origin):
                self.assert_header_equal('Access-Control-Allow-Origin', origin)

    def test_star_allowed_origin_honored(self):
        with self.cors_enabled:
            with self.config_override('RESTFULGIT_CORS_ALLOWED_ORIGIN', '*'):
                self.assert_header_equal('Access-Control-Allow-Origin', '*')

    def test_max_age_honored(self):
        max_age = timedelta(minutes=427)
        with self.cors_enabled:
            with self.config_override('RESTFULGIT_CORS_MAX_AGE', max_age):
                self.assert_header_equal('Access-Control-Max-Age', unicode(int(max_age.total_seconds())))

    def test_enabled_allow_credentials_honored(self):
        with self.cors_enabled:
            with self.config_override('RESTFULGIT_CORS_ALLOW_CREDENTIALS', True):
                self.assert_header_equal('Access-Control-Allow-Credentials', 'true')

    def test_disabled_allow_credentials_honored(self):
        with self.cors_enabled:
            with self.config_override('RESTFULGIT_CORS_ALLOW_CREDENTIALS', False):
                self.assert_header_equal('Access-Control-Allow-Credentials', 'false')

    def test_allowed_headers_honored(self):
        with self.cors_enabled:
            with self.config_override('RESTFULGIT_CORS_ALLOWED_HEADERS', ['X-Foo', 'X-Bar']):
                self.assert_header_equal('Access-Control-Allow-Headers', "X-Foo, X-Bar")

    def test_allowed_methods(self):
        with self.cors_enabled:
            self.assert_header_equal('Access-Control-Allow-Methods', 'HEAD, OPTIONS, GET')


if __name__ == '__main__':
    unittest.main()
