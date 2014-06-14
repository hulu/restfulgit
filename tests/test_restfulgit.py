# coding=utf-8
from __future__ import absolute_import, unicode_literals

import unittest
from hashlib import sha512
import os
import os.path
import io
from contextlib import contextmanager
from datetime import timedelta
from tempfile import mkdtemp, mkstemp
from shutil import rmtree
from subprocess import check_call
from json import load as load_json_file

from flask.ext.testing import TestCase as _FlaskTestCase

from restfulgit.app_factory import create_app


RESTFULGIT_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PARENT_DIR_OF_RESTFULGIT_REPO = os.path.abspath(os.path.join(RESTFULGIT_REPO, '..'))
CONFIG_FILE = os.path.join(RESTFULGIT_REPO, 'example_config.py')


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
        app = create_app()
        app.config.from_pyfile(CONFIG_FILE)
        app.config['RESTFULGIT_REPO_BASE_PATH'] = PARENT_DIR_OF_RESTFULGIT_REPO
        return app

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

    def assertContentTypeIsDiff(self, resp):
        self.assertEqual(resp.headers.get_all('Content-Type'), [b'text/x-diff; charset=utf-8'])

    @contextmanager
    def config_override(self, key, val):
        orig_val = self.app.config[key]
        self.app.config[key] = val
        try:
            yield
        finally:
            self.app.config[key] = orig_val

    def get_fixture_path(self, filename):
        return os.path.join(FIXTURES_DIR, filename)

    def _get_fixture_bytes(self, filename):
        filepath = self.get_fixture_path(filename)
        with open(filepath, 'r') as fixture_file:
            return fixture_file.read()

    def assertBytesEqualFixture(self, text, fixture):
        self.assertEqual(text, self._get_fixture_bytes(fixture))

    @contextmanager
    def temporary_file(self, suffix=''):
        file_descriptor, filepath = mkstemp(suffix=suffix)
        file_obj = os.fdopen(file_descriptor, 'wb')
        try:
            yield file_obj, filepath
        finally:
            if not file_obj.closed:
                file_obj.close()
            delete_file_quietly(filepath)

    @contextmanager
    def temporary_directory(self, suffix=''):
        temp_dir = mkdtemp(suffix=suffix)
        try:
            yield temp_dir
        finally:
            rmtree(temp_dir)

    def make_nested_dir(self, extant_parent, new_child):
        new_dir = os.path.join(extant_parent, new_child)
        os.mkdir(new_dir)
        return new_dir


class RepoKeyTestCase(_RestfulGitTestCase):
    def test_nonexistent_directory(self):
        resp = self.client.get('/repos/this-directory-does-not-exist/git/commits/')
        self.assertJson404(resp)

    def test_directory_is_not_git_repo(self):
        self.app.config['RESTFULGIT_REPO_BASE_PATH'] = RESTFULGIT_REPO
        resp = self.client.get('/repos/test/git/commits/')
        self.assertJson404(resp)

    def test_dot_dot_disallowed(self):
        self.app.config['RESTFULGIT_REPO_BASE_PATH'] = TEST_SUBDIR
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
        self.assertIn("content", json)
        self.assertEqual(
            sha512(json["content"]).hexdigest(),
            '1c846bb4d44c08073c487316a7dc02d97d825aecf50546caf9bf10277c01d17e19860d5f86de877268dd969bd081c7595991c325e0ab492374b956e3a6c9967f'
        )
        del json["content"]
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
        # From https://api.github.com/repos/hulu/restfulgit/git/blobs/79fbf74e9d9f752c901c956e958845a308c44283 with necessary adjustments
        resp = self.client.get('/repos/restfulgit/git/blobs/79fbf74e9d9f752c901c956e958845a308c44283/')
        self.assert200(resp)
        json = resp.json
        self.assertIsInstance(json, dict)
        self.assertIn('content', json)
        content = json['content']
        del json['content']
        self.assertBytesEqualFixture(content.decode('base64'), 'example.png')
        self.assertEqual(
            json,
            {
                "sha": "79fbf74e9d9f752c901c956e958845a308c44283",
                "size": 1185,
                "url": "http://localhost/repos/restfulgit/git/blobs/79fbf74e9d9f752c901c956e958845a308c44283/",
                "encoding": "base64"
            }
        )

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
            },
            "url": "http://localhost/repos/restfulgit/tags/initial/",  # NOTE: RestfulGit extension
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

    def test_get_merged_branches_inclusion(self):
        resp = self.client.get('/repos/restfulgit/branches/master/merged/')
        self.assert200(resp)
        json = resp.json
        self.assertIsInstance(json, list)
        for item in json:
            self.assertIsInstance(item, dict)
            self.assertIn('name', item)
        branch_names = {item['name'] for item in json}
        self.assertIn('ambiguous', branch_names)

    def test_get_merged_branches_format(self):
        resp = self.client.get('/repos/restfulgit/branches/master/merged/')
        self.assert200(resp)
        json = resp.json
        self.assertIsInstance(json, list)
        for item in json:
            self.assertIsInstance(item, dict)
            self.assertIn('name', item)
        name_to_branch = {item['name']: item for item in json}
        reference = {
            "name": "ambiguous",
            "commit": {
                "sha": "1f51b91ac383806df9d322ae67bbad3364f50811",
                "url": "http://localhost/repos/restfulgit/commits/1f51b91ac383806df9d322ae67bbad3364f50811/",
            }
        }
        self.assertEqual(reference, name_to_branch.get('ambiguous'))

    def test_get_merged_branches_exclusion(self):
        resp = self.client.get('/repos/restfulgit/branches/ambiguous/merged/')
        self.assert200(resp)
        branches = {branch['name'] for branch in resp.json}
        self.assertNotIn('master', branches)

    def test_get_merged_branches_with_nonexistent_branch(self):
        resp = self.client.get('/repos/restfulgit/branches/this-branch-does-not-exist/merged/')
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
        self.assertContentTypeIsDiff(resp)
        self.assertBytesEqualFixture(resp.get_data(), 'd408fc2428bc6444cabd7f7b46edbe70b6992b16.diff')

    def test_get_diff_with_parentless_commit(self):  # NOTE: RestfulGit extension; GitHub gives a 404 in this case
        resp = self.client.get('/repos/restfulgit/commit/07b9bf1540305153ceeb4519a50b588c35a35464.diff')
        self.assert200(resp)
        self.assertContentTypeIsDiff(resp)
        self.assertBytesEqualFixture(resp.get_data(), '07b9bf1540305153ceeb4519a50b588c35a35464.diff')

    def test_get_diff_with_nonexistent_sha(self):
        resp = self.client.get('/repos/restfulgit/commit/{}.diff'.format(IMPROBABLE_SHA))
        self.assertJson404(resp)

    def test_get_diff_involving_binary_file(self):
        # From https://github.com/hulu/restfulgit/commit/88edac1a3a55c04646ccc963fdada0e194ed5926.diff
        resp = self.client.get('/repos/restfulgit/commit/88edac1a3a55c04646ccc963fdada0e194ed5926.diff')
        self.assert200(resp)
        self.assertContentTypeIsDiff(resp)
        self.assertBytesEqualFixture(resp.get_data(), '88edac1a3a55c04646ccc963fdada0e194ed5926.diff')

    def test_get_diff_with_merge_commit(self):
        pass


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

    def test_tags_trump_branches(self):
        # branch "ambiguous" = commit 1f51b91
        #     api.py's SHA-512 = e948e8d0b0d0703d972279382a002c90040ff19d636e96927262d63e1f1429526539ea781744d2f3a65a5938b59e0c5f57adadc26f797480efcfc6f7dcff3d81
        # tag "ambiguous" = commit ff6405b
        #     api.py's SHA-512 = a50e02753d282c0e35630bbbc16a525ea4e0b2e2af668135b603c8e1467c7269bcbe9075886baf3f08ce195a7eab1e0b8179080af08a2c0f3eda3b9518650fa1
        resp = self.client.get("/repos/restfulgit/raw/ambiguous/api.py")
        self.assert200(resp)
        self.assertEqual(
            'a50e02753d282c0e35630bbbc16a525ea4e0b2e2af668135b603c8e1467c7269bcbe9075886baf3f08ce195a7eab1e0b8179080af08a2c0f3eda3b9518650fa1',
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
        self.app.config['RESTFULGIT_REPO_BASE_PATH'] = TEST_SUBDIR
        resp = self.client.get('/repos/../')
        self.assertJson404(resp)

    def test_nonexistent_repo(self):
        self.app.config['RESTFULGIT_REPO_BASE_PATH'] = RESTFULGIT_REPO
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


class ArchiveDownloadTestCase(_RestfulGitTestCase):
    def run_command_quietly(self, args):
        with open(os.devnull, 'wb') as blackhole:
            check_call(args, stdout=blackhole)

    def _only_subdirectory_in(self, directory):
        names = os.listdir(directory)
        self.assertEqual(len(names), 1)
        subdir = os.path.join(directory, names[0])
        self.assertTrue(os.path.isdir(subdir))
        return subdir

    def assertFilesEqual(self, filepath_one, filepath_two, including_permissions=False):
        if including_permissions:
            self.assertEqualPermissions(filepath_one, filepath_two)
        with open(filepath_one, 'rb') as file_one, open(filepath_two, 'rb') as file_two:
            self.assertEqual(file_one.read(), file_two.read())

    def assertEqualPermissions(self, path_one, path_two):
        stat_one = os.stat(path_one)
        stat_two = os.stat(path_two)
        self.assertEqual(stat_one.st_mode, stat_two.st_mode)
        self.assertEqual(stat_one.st_uid, stat_two.st_uid)
        self.assertEqual(stat_one.st_gid, stat_two.st_gid)

    def assertDirectoriesEqual(self, dir_one, dir_two, including_permissions=False):
        for dirpath_one, dirnames_one, filenames_one in os.walk(dir_one):
            dirnames_one = frozenset(dirnames_one)
            filenames_one = frozenset(filenames_one)

            dirpath_two = dirpath_one.replace(dir_one, dir_two, 1)
            self.assertTrue(os.path.isdir(dirpath_two))
            children_two = os.listdir(dirpath_two)
            dirnames_two = frozenset(name for name in children_two if os.path.isdir(os.path.join(dirpath_two, name)))
            filenames_two = frozenset(name for name in children_two if os.path.isfile(os.path.join(dirpath_two, name)))

            if including_permissions:
                self.assertEqualPermissions(dirpath_one, dirpath_two)
            self.assertEqual(dirnames_one, dirnames_two)
            self.assertEqual(filenames_one, filenames_two)

            for filename in filenames_one:
                filepath_one = os.path.join(dirpath_one, filename)
                filepath_two = os.path.join(dirpath_two, filename)
                self.assertFilesEqual(filepath_one, filepath_two, including_permissions=including_permissions)

    def assertIsAttachment(self, resp):
        self.assertTrue(resp.headers.get('Content-Disposition', '').startswith('attachment;'))

    def test_zipball_contents(self):
        commit = '7da1a61e2f566cf3094c2fea4b18b111d2638a8f'  # 1st commit in the repo that has multiple levels of subdirectories
        with self.temporary_directory(suffix='.restfulgit') as temp_dir:
            actual_dir = self.make_nested_dir(temp_dir, 'actual')
            reference_dir = self.make_nested_dir(temp_dir, 'reference')

            self.run_command_quietly(['unzip', self.get_fixture_path('{}.zip'.format(commit)), '-d', reference_dir])

            with self.temporary_file(suffix='restfulgit_actual_zipball.zip') as pair:
                actual_zip_file, actual_zip_filepath = pair
                with actual_zip_file:
                    resp = self.client.get('/repos/restfulgit/zipball/{}/'.format(commit))
                    self.assert200(resp)

                    actual_zip_file.write(resp.data)

                self.run_command_quietly(['unzip', actual_zip_filepath, '-d', actual_dir])

            reference_wrapper_dir = self._only_subdirectory_in(reference_dir)
            actual_wrapper_dir = self._only_subdirectory_in(actual_dir)
            self.assertDirectoriesEqual(reference_wrapper_dir, actual_wrapper_dir)

    def test_zipball_headers(self):
        resp = self.client.get('/repos/restfulgit/zipball/7da1a61e2f566cf3094c2fea4b18b111d2638a8f/')
        self.assertIsAttachment(resp)
        self.assertTrue(resp.headers.get('Content-Disposition', '').endswith('filename=restfulgit-7da1a61e2f566cf3094c2fea4b18b111d2638a8f.zip'))
        self.assertEqual(resp.headers.get('Content-Type'), 'application/zip')
        self.assertIn('max-age=0', resp.headers.get('Cache-Control', ''))

    def test_zipball_on_nonexistent_repo(self):
        resp = self.client.get('/repos/this-repo-does-not-exist/zipball/master/')
        self.assertJson404(resp)

    def test_zipball_on_nonexistent_ref(self):
        resp = self.client.get('/repos/restfulgit/zipball/{}/'.format(IMPROBABLE_SHA))
        self.assertJson404(resp)

    def test_tarball_contents(self):
        commit = '7da1a61e2f566cf3094c2fea4b18b111d2638a8f'  # 1st commit in the repo that has multiple levels of subdirectories
        with self.temporary_directory(suffix='.restfulgit') as temp_dir:
            actual_dir = self.make_nested_dir(temp_dir, 'actual')
            reference_dir = self.make_nested_dir(temp_dir, 'reference')

            self.run_command_quietly(['tar', 'xf', self.get_fixture_path('{}.tar.gz'.format(commit)), '-C', reference_dir])

            with self.temporary_file(suffix='restfulgit_actual_tarball.tar.gz') as pair:
                actual_tar_file, actual_tar_filepath = pair
                with actual_tar_file:
                    resp = self.client.get('/repos/restfulgit/tarball/{}/'.format(commit))
                    self.assert200(resp)

                    actual_tar_file.write(resp.data)

                self.run_command_quietly(['tar', 'xf', actual_tar_filepath, '-C', actual_dir])

            reference_wrapper_dir = self._only_subdirectory_in(reference_dir)
            actual_wrapper_dir = self._only_subdirectory_in(actual_dir)
            self.assertDirectoriesEqual(reference_wrapper_dir, actual_wrapper_dir, including_permissions=True)

    def test_tarball_headers(self):
        resp = self.client.get('/repos/restfulgit/tarball/7da1a61e2f566cf3094c2fea4b18b111d2638a8f/')
        self.assertIsAttachment(resp)
        self.assertTrue(resp.headers.get('Content-Disposition', '').endswith('filename=restfulgit-7da1a61e2f566cf3094c2fea4b18b111d2638a8f.tar.gz'))
        self.assertIn(resp.headers.get('Content-Type'), {'application/x-gzip', 'application/x-tar'})
        self.assertIn('max-age=0', resp.headers.get('Cache-Control', ''))

    def test_tarball_on_nonexistent_repo(self):
        resp = self.client.get('/repos/this-repo-does-not-exist/tarball/master/')
        self.assertJson404(resp)

    def test_tarball_on_nonexistent_ref(self):
        resp = self.client.get('/repos/restfulgit/tarball/{}/'.format(IMPROBABLE_SHA))
        self.assertJson404(resp)


class BlameTestCase(_RestfulGitTestCase):
    def test_nonexistent_repo(self):
        resp = self.client.get('/repos/this-repo-does-not-exist/blame/master/README')
        self.assertJson404(resp)

    def test_nonexistent_ref(self):
        resp = self.client.get('/repos/restfulgit/blame/this-branch-does-not-exist/README')
        self.assertJson404(resp)

    def test_nonexistent_file(self):
        resp = self.client.get('/repos/restfulgit/blame/master/this-file-does-not-exist')
        self.assertJson404(resp)

    def test_directory_with_trailing_slash(self):
        resp = self.client.get('/repos/restfulgit/blame/da55cbf2f13c2ec019bf02f080bc47cc4f83318c/restfulgit/')
        self.assertJson400(resp)

    def test_directory_without_trailing_slash(self):
        resp = self.client.get('/repos/restfulgit/blame/da55cbf2f13c2ec019bf02f080bc47cc4f83318c/restfulgit')
        self.assertJson400(resp)

    def test_first_line_out_of_bounds(self):
        # relevant file is 1027 lines long
        resp = self.client.get('/repos/restfulgit/blame/da55cbf2f13c2ec019bf02f080bc47cc4f83318c/restfulgit/__init__.py?firstLine=1028')
        self.assertJson400(resp)

    def test_last_line_out_of_bounds(self):
        # relevant file is 1027 lines long
        resp = self.client.get('/repos/restfulgit/blame/da55cbf2f13c2ec019bf02f080bc47cc4f83318c/restfulgit/__init__.py?lastLine=1028')
        self.assertJson400(resp)

    def test_malformed_line_range(self):
        resp = self.client.get('/repos/restfulgit/blame/da55cbf2f13c2ec019bf02f080bc47cc4f83318c/restfulgit/__init__.py?firstLine=2&lastLine=1')
        self.assertJson400(resp)

    def test_zero_first_line(self):
        resp = self.client.get('/repos/restfulgit/blame/da55cbf2f13c2ec019bf02f080bc47cc4f83318c/restfulgit/__init__.py?firstLine=0')
        self.assertJson400(resp)

    def test_zero_last_line(self):
        resp = self.client.get('/repos/restfulgit/blame/da55cbf2f13c2ec019bf02f080bc47cc4f83318c/restfulgit/__init__.py?lastLine=0')
        self.assertJson400(resp)

    def test_non_integer_first_line(self):
        resp = self.client.get('/repos/restfulgit/blame/da55cbf2f13c2ec019bf02f080bc47cc4f83318c/restfulgit/__init__.py?firstLine=abc')
        self.assertJson400(resp)

    def test_non_integer_last_line(self):
        resp = self.client.get('/repos/restfulgit/blame/da55cbf2f13c2ec019bf02f080bc47cc4f83318c/restfulgit/__init__.py?lastLine=abc')
        self.assertJson400(resp)

    def test_basic_works(self):
        resp = self.client.get('/repos/restfulgit/blame/da55cbf2f13c2ec019bf02f080bc47cc4f83318c/restfulgit/__init__.py')
        self.assert200(resp)

        with io.open(self.get_fixture_path('da55cbf2f13c2ec019bf02f080bc47cc4f83318c-__init__.py-blame.json'), mode='rt', encoding='utf-8') as reference_file:
            reference = load_json_file(reference_file)

        self.assertEqual(reference, resp.json)

    def test_first_line_only(self):
        # relevant file is 1027 lines long
        resp = self.client.get('/repos/restfulgit/blame/da55cbf2f13c2ec019bf02f080bc47cc4f83318c/restfulgit/__init__.py?firstLine=1025')
        self.assert200(resp)
        self.assertEqual(resp.json, {
            "commits": {
                "090750eec2fe5f120ad1010fc2204d06fc3ca91e": {
                    "committer": {
                        "date": "2013-05-20T19:12:03Z",
                        "name": "Rajiv Makhijani",
                        "email": "rajiv@hulu.com"
                    },
                    "author": {
                        "date": "2013-05-20T19:12:03Z",
                        "name": "Rajiv Makhijani",
                        "email": "rajiv@hulu.com"
                    },
                    "url": "http://localhost/repos/restfulgit/git/commits/090750eec2fe5f120ad1010fc2204d06fc3ca91e/",
                    "tree": {
                        "url": "http://localhost/repos/restfulgit/git/trees/288a19807d25403221c3f5260f4c172ec820b621/",
                        "sha": "288a19807d25403221c3f5260f4c172ec820b621"
                    },
                    "sha": "090750eec2fe5f120ad1010fc2204d06fc3ca91e",
                    "parents": [{
                        "url": "http://localhost/repos/restfulgit/git/commits/cff4955ef40cfce35efe282e196c840619c518f2/",
                        "sha": "cff4955ef40cfce35efe282e196c840619c518f2"
                    }],
                    "message": "PEP-8 minor cleanup"
                },
                "ebaa594a5b689d1cb552e15753bcd109f60b0a10": {
                    "committer": {
                        "date": "2013-10-06T23:44:52Z",
                        "name": "Chris Rebert", "email": "chris.rebert@hulu.com"
                    },
                    "author": {
                        "date": "2013-10-05T04:15:22Z",
                        "name": "Chris Rebert",
                        "email": "chris.rebert@hulu.com"
                    },
                    "url": "http://localhost/repos/restfulgit/git/commits/ebaa594a5b689d1cb552e15753bcd109f60b0a10/",
                    "tree": {
                        "url": "http://localhost/repos/restfulgit/git/trees/16507999f5b925211a48e3c97b242577b14bfc71/",
                        "sha": "16507999f5b925211a48e3c97b242577b14bfc71"
                    },
                    "sha": "ebaa594a5b689d1cb552e15753bcd109f60b0a10",
                    "parents": [{
                        "url": "http://localhost/repos/restfulgit/git/commits/caccc35a6f5d8e9b9a7e23d4a2ad60f4b4155739/",
                        "sha": "caccc35a6f5d8e9b9a7e23d4a2ad60f4b4155739"
                    }],
                    "message": "use a blueprint to enhance embedability/reuseability/modularity; fixes #25\n\nURL converter registration inspired by http://blog.adrianschreyer.eu/post/adding-custom-url-map-converters-to-flask-blueprint-objects"
                }
            },
            "lines": [
                {
                    "commit": "ebaa594a5b689d1cb552e15753bcd109f60b0a10",
                    "line": "app.register_blueprint(restfulgit)",
                    "origPath": "gitapi.py",
                    "lineNum": 1025
                },
                {
                    "commit": "ebaa594a5b689d1cb552e15753bcd109f60b0a10",
                    "line": "",
                    "origPath": "gitapi.py",
                    "lineNum": 1026
                },
                {
                    "commit": "090750eec2fe5f120ad1010fc2204d06fc3ca91e",
                    "line": "application = app",
                    "origPath": "api.py",
                    "lineNum": 1027
                }
            ]
        })

    def test_last_line_only(self):
        resp = self.client.get('/repos/restfulgit/blame/da55cbf2f13c2ec019bf02f080bc47cc4f83318c/restfulgit/__init__.py?lastLine=2')
        self.assert200(resp)
        self.assertEqual(resp.json, {
            'commits': {
                '34f85950f3fcc662338593bbd43ad3bebc8cbf22': {
                    'author': {
                        'date': '2013-09-24T04:42:40Z',
                        'email': 'github@rebertia.com',
                        'name': 'Chris Rebert'
                    },
                    'committer': {
                        'date': '2013-09-24T04:42:40Z',
                        'email': 'github@rebertia.com',
                        'name': 'Chris Rebert'
                    },
                    'message': 'add PEP-263 encoding declaration',
                    'parents': [{
                        'sha': 'fadadc122ac7357816d6d57515c36ed8dddfadb5',
                        'url': 'http://localhost/repos/restfulgit/git/commits/fadadc122ac7357816d6d57515c36ed8dddfadb5/'
                    }],
                    'sha': '34f85950f3fcc662338593bbd43ad3bebc8cbf22',
                    'tree': {
                        'sha': '029c2787239825668f3619eb02bf5a336720f5e9',
                        'url': 'http://localhost/repos/restfulgit/git/trees/029c2787239825668f3619eb02bf5a336720f5e9/'
                    },
                    'url': 'http://localhost/repos/restfulgit/git/commits/34f85950f3fcc662338593bbd43ad3bebc8cbf22/'
                },
                'ffefa5a12812d65ba4f55adeaa5bbd8131ea0c69': {
                    'author': {
                        'date': '2013-09-26T07:46:16Z',
                        'email': 'chris.rebert@hulu.com',
                        'name': 'Chris Rebert'
                    },
                    'committer': {
                        'date': '2013-09-26T07:46:16Z',
                        'email': 'chris.rebert@hulu.com',
                        'name': 'Chris Rebert'},
                    'message': 'improve config loading error reporting & squelch last W0702',
                    'parents': [{
                        'sha': '1f6787c238ef12413dca5305b8254c26c299718f',
                        'url': 'http://localhost/repos/restfulgit/git/commits/1f6787c238ef12413dca5305b8254c26c299718f/'
                    }],
                    'sha': 'ffefa5a12812d65ba4f55adeaa5bbd8131ea0c69',
                    'tree': {
                        'sha': '60859aa5e7ef3ba15006bd33f6ace219a3049ea5',
                        'url': 'http://localhost/repos/restfulgit/git/trees/60859aa5e7ef3ba15006bd33f6ace219a3049ea5/'
                    },
                    'url': 'http://localhost/repos/restfulgit/git/commits/ffefa5a12812d65ba4f55adeaa5bbd8131ea0c69/'
                }
            },
            'lines': [
                {
                    'commit': '34f85950f3fcc662338593bbd43ad3bebc8cbf22',
                    'line': '# coding=utf-8',
                    'lineNum': 1,
                    'origPath': 'gitapi.py'},
                {
                    'commit': 'ffefa5a12812d65ba4f55adeaa5bbd8131ea0c69',
                    'line': 'from __future__ import print_function',
                    'lineNum': 2,
                    'origPath': 'gitapi.py'
                }
            ]
        })

    def test_first_line_just_within_bounds(self):
        # relevant file is 1027 lines long
        resp = self.client.get('/repos/restfulgit/blame/da55cbf2f13c2ec019bf02f080bc47cc4f83318c/restfulgit/__init__.py?firstLine=1027')
        self.assert200(resp)
        self.assertEqual(resp.json, {
            'commits': {
                '090750eec2fe5f120ad1010fc2204d06fc3ca91e': {
                    'author': {
                        'date': '2013-05-20T19:12:03Z',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'committer': {
                        'date': '2013-05-20T19:12:03Z',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'message': 'PEP-8 minor cleanup',
                    'parents': [{
                        'sha': 'cff4955ef40cfce35efe282e196c840619c518f2',
                        'url': 'http://localhost/repos/restfulgit/git/commits/cff4955ef40cfce35efe282e196c840619c518f2/'
                    }],
                    'sha': '090750eec2fe5f120ad1010fc2204d06fc3ca91e',
                    'tree': {
                        'sha': '288a19807d25403221c3f5260f4c172ec820b621',
                        'url': 'http://localhost/repos/restfulgit/git/trees/288a19807d25403221c3f5260f4c172ec820b621/'
                    },
                    'url': 'http://localhost/repos/restfulgit/git/commits/090750eec2fe5f120ad1010fc2204d06fc3ca91e/'
                }
            },
            'lines': [{
                'commit': '090750eec2fe5f120ad1010fc2204d06fc3ca91e',
                'line': 'application = app',
                'lineNum': 1027,
                'origPath': 'api.py'
            }]
        })

    def test_last_line_just_within_bounds(self):
        # relevant file is 1027 lines long
        resp = self.client.get('/repos/restfulgit/blame/da55cbf2f13c2ec019bf02f080bc47cc4f83318c/restfulgit/__init__.py?lastLine=1027&firstLine=1026')
        self.assert200(resp)
        self.assertEqual(resp.json, {
            'commits': {
                '090750eec2fe5f120ad1010fc2204d06fc3ca91e': {
                    'author': {
                        'date': '2013-05-20T19:12:03Z',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'committer': {
                        'date': '2013-05-20T19:12:03Z',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'message': 'PEP-8 minor cleanup',
                    'parents': [{
                        'sha': 'cff4955ef40cfce35efe282e196c840619c518f2',
                        'url': 'http://localhost/repos/restfulgit/git/commits/cff4955ef40cfce35efe282e196c840619c518f2/'
                    }],
                    'sha': '090750eec2fe5f120ad1010fc2204d06fc3ca91e',
                    'tree': {
                        'sha': '288a19807d25403221c3f5260f4c172ec820b621',
                        'url': 'http://localhost/repos/restfulgit/git/trees/288a19807d25403221c3f5260f4c172ec820b621/'
                    },
                    'url': 'http://localhost/repos/restfulgit/git/commits/090750eec2fe5f120ad1010fc2204d06fc3ca91e/'
                },
                'ebaa594a5b689d1cb552e15753bcd109f60b0a10': {
                    'author': {
                        'date': '2013-10-05T04:15:22Z',
                        'email': 'chris.rebert@hulu.com',
                        'name': 'Chris Rebert'
                    },
                    'committer': {
                        'date': '2013-10-06T23:44:52Z',
                        'email': 'chris.rebert@hulu.com',
                        'name': 'Chris Rebert'
                    },
                    'message': 'use a blueprint to enhance embedability/reuseability/modularity; fixes #25\n\nURL converter registration inspired by http://blog.adrianschreyer.eu/post/adding-custom-url-map-converters-to-flask-blueprint-objects',
                    'parents': [{
                        'sha': 'caccc35a6f5d8e9b9a7e23d4a2ad60f4b4155739',
                        'url': 'http://localhost/repos/restfulgit/git/commits/caccc35a6f5d8e9b9a7e23d4a2ad60f4b4155739/'
                    }],
                    'sha': 'ebaa594a5b689d1cb552e15753bcd109f60b0a10',
                    'tree': {
                        'sha': '16507999f5b925211a48e3c97b242577b14bfc71',
                        'url': 'http://localhost/repos/restfulgit/git/trees/16507999f5b925211a48e3c97b242577b14bfc71/'
                    },
                    'url': 'http://localhost/repos/restfulgit/git/commits/ebaa594a5b689d1cb552e15753bcd109f60b0a10/'
                }
            },
            'lines': [
                {
                    'commit': 'ebaa594a5b689d1cb552e15753bcd109f60b0a10',
                    'line': '',
                    'lineNum': 1026,
                    'origPath': 'gitapi.py'
                },
                {
                    'commit': '090750eec2fe5f120ad1010fc2204d06fc3ca91e',
                    'line': 'application = app',
                    'lineNum': 1027,
                    'origPath': 'api.py'
                },
            ]
        })

    def test_first_and_last_line_works(self):
        resp = self.client.get('/repos/restfulgit/blame/da55cbf2f13c2ec019bf02f080bc47cc4f83318c/restfulgit/__init__.py?firstLine=4&lastLine=6')
        self.assert200(resp)
        self.assertEqual(resp.json, {
            'commits': {
                '13e9ff41ba4704d6ca91988f9216adeeee8c79b5': {
                    'author': {
                        'date': '2013-12-23T04:16:14Z',
                        'email': 'chris.rebert@hulu.com',
                        'name': 'Chris Rebert'
                    },
                    'committer': {
                        'date': '2013-12-30T20:01:35Z',
                        'email': 'chris.rebert@hulu.com',
                        'name': 'Chris Rebert'
                    },
                    'message': 'implement tarball & zipball downloads; fixes #62\n\nReference zipball from https://github.com/hulu/restfulgit/zipball/7da1a61e2f566cf3094c2fea4b18b111d2638a8f\nReference tarball from https://github.com/hulu/restfulgit/tarball/7da1a61e2f566cf3094c2fea4b18b111d2638a8f',
                    'parents': [{
                        'sha': '129458e24667a9c32db4cb1a0549e3554bff0965',
                        'url': 'http://localhost/repos/restfulgit/git/commits/129458e24667a9c32db4cb1a0549e3554bff0965/'
                    }],
                    'sha': '13e9ff41ba4704d6ca91988f9216adeeee8c79b5',
                    'tree': {
                        'sha': 'a611bc827047055a6b8e9cbf7ee2827767b27328',
                        'url': 'http://localhost/repos/restfulgit/git/trees/a611bc827047055a6b8e9cbf7ee2827767b27328/'
                    },
                    'url': 'http://localhost/repos/restfulgit/git/commits/13e9ff41ba4704d6ca91988f9216adeeee8c79b5/'
                },
                'a8e4af2d7f30492bfef34ccb1c2c167df54512ba': {
                    'author': {
                        'date': '2013-12-10T03:32:32Z',
                        'email': 'chris.rebert@hulu.com',
                        'name': 'Chris Rebert'
                    },
                    'committer': {
                        'date': '2013-12-10T03:59:40Z',
                        'email': 'chris.rebert@hulu.com',
                        'name': 'Chris Rebert'
                    },
                    'message': 'use JSON error pages; fixes #39',
                    'parents': [{
                        'sha': '493431d90a21109290e4a8ab8978e523ec957531',
                        'url': 'http://localhost/repos/restfulgit/git/commits/493431d90a21109290e4a8ab8978e523ec957531/'
                    }],
                    'sha': 'a8e4af2d7f30492bfef34ccb1c2c167df54512ba',
                    'tree': {
                        'sha': 'b08d1b792ecba9ebb06bc8f2dad5d0877a9a42ec',
                        'url': 'http://localhost/repos/restfulgit/git/trees/b08d1b792ecba9ebb06bc8f2dad5d0877a9a42ec/'
                    },
                    'url': 'http://localhost/repos/restfulgit/git/commits/a8e4af2d7f30492bfef34ccb1c2c167df54512ba/'
                },
                'ba3f032dbd2ead6a6610f3bf3b66f05cb628f579': {
                    'author': {
                        'date': '2013-09-12T04:26:31Z',
                        'email': 'chris.rebert@hulu.com',
                        'name': 'Chris Rebert'
                    },
                    'committer': {
                        'date': '2013-09-12T06:16:37Z',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                   'message': 'use a custom Werkzeug converter for commit SHAs; fixes #1',
                   'parents': [{
                        'sha': '98b873f9d87b110a48628b8493de2cb0383eb391',
                        'url': 'http://localhost/repos/restfulgit/git/commits/98b873f9d87b110a48628b8493de2cb0383eb391/'
                    }],
                    'sha': 'ba3f032dbd2ead6a6610f3bf3b66f05cb628f579',
                    'tree': {
                        'sha': 'a6fb2a953ab675c8da0f3776faa160101ac301f9',
                        'url': 'http://localhost/repos/restfulgit/git/trees/a6fb2a953ab675c8da0f3776faa160101ac301f9/'
                    },
                    'url': 'http://localhost/repos/restfulgit/git/commits/ba3f032dbd2ead6a6610f3bf3b66f05cb628f579/'
                }
            },
            'lines': [
                {
                    'commit': '13e9ff41ba4704d6ca91988f9216adeeee8c79b5',
                    'line': 'from flask import Flask, url_for, request, Response, current_app, Blueprint, safe_join, send_from_directory, make_response, send_file',
                    'lineNum': 4,
                    'origPath': 'restfulgit/__init__.py'},
                {
                    'commit': 'a8e4af2d7f30492bfef34ccb1c2c167df54512ba',
                    'line': 'from werkzeug.exceptions import NotFound, BadRequest, HTTPException, default_exceptions',
                    'lineNum': 5,
                    'origPath': 'restfulgit/__init__.py'
                },
                {
                    'commit': 'ba3f032dbd2ead6a6610f3bf3b66f05cb628f579',
                    'line': 'from werkzeug.routing import BaseConverter',
                    'lineNum': 6,
                    'origPath': 'gitapi.py'
                }
            ]
        })

    def test_single_line_works(self):
        resp = self.client.get('/repos/restfulgit/blame/da55cbf2f13c2ec019bf02f080bc47cc4f83318c/restfulgit/__init__.py?firstLine=1027&lastLine=1027')
        self.assert200(resp)
        self.assertEqual(resp.json, {
            'commits': {
                '090750eec2fe5f120ad1010fc2204d06fc3ca91e': {
                    'author': {
                        'date': '2013-05-20T19:12:03Z',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'committer': {
                        'date': '2013-05-20T19:12:03Z',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'message': 'PEP-8 minor cleanup',
                    'parents': [{
                        'sha': 'cff4955ef40cfce35efe282e196c840619c518f2',
                        'url': 'http://localhost/repos/restfulgit/git/commits/cff4955ef40cfce35efe282e196c840619c518f2/'
                    }],
                    'sha': '090750eec2fe5f120ad1010fc2204d06fc3ca91e',
                    'tree': {
                        'sha': '288a19807d25403221c3f5260f4c172ec820b621',
                        'url': 'http://localhost/repos/restfulgit/git/trees/288a19807d25403221c3f5260f4c172ec820b621/'
                    },
                    'url': 'http://localhost/repos/restfulgit/git/commits/090750eec2fe5f120ad1010fc2204d06fc3ca91e/'
                }
            },
            'lines': [{
                'commit': '090750eec2fe5f120ad1010fc2204d06fc3ca91e',
                'line': 'application = app',
                'lineNum': 1027,
                'origPath': 'api.py'
            }]
        })

    def test_oldest_with_nonexistent_ref(self):
        resp = self.client.get('/repos/restfulgit/blame/da55cbf2f13c2ec019bf02f080bc47cc4f83318c/restfulgit/__init__.py?oldest={}'.format(IMPROBABLE_SHA))
        self.assertJson404(resp)

    def test_oldest_works(self):
        resp = self.client.get('/repos/restfulgit/blame/da55cbf2f13c2ec019bf02f080bc47cc4f83318c/restfulgit/__init__.py?oldest=129458e24667a9c32db4cb1a0549e3554bff0965')
        self.assert200(resp)
        json = resp.json
        relevant_commits = {'129458e24667a9c32db4cb1a0549e3554bff0965', '13e9ff41ba4704d6ca91988f9216adeeee8c79b5'}
        self.assertEqual(relevant_commits, set(json['commits'].viewkeys()))
        self.assertEqual(relevant_commits, {line['commit'] for line in json['lines']})


class RepoContentsTestCase(_RestfulGitTestCase):
    def test_nonexistent_repo(self):
        resp = self.client.get('/repos/this-repo-does-not-exist/contents/README.md')
        self.assertJson404(resp)

    def test_nonexistent_ref(self):
        resp = self.client.get('/repos/restfulgit/contents/README.md?ref=this-branch-does-not-exist')
        self.assertJson404(resp)

    def test_ref_is_optional(self):
        resp = self.client.get('/repos/restfulgit/contents/README.md')
        self.assert200(resp)

    def test_extant_file(self):
        resp = self.client.get('/repos/restfulgit/contents/tests/fixtures/d408fc2428bc6444cabd7f7b46edbe70b6992b16.diff?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f')
        self.assert200(resp)
        json = resp.json
        content = json.pop('content')
        self.assertEqual(sha512(content).hexdigest(), '1966b04df26b4b9168d9c294d12ff23794fc36ba7bd7e96997541f5f31814f0d2f640dd6f0c0fe719a74815439154890df467ec5b9c4322d785902b18917fecc')
        # From https://api.github.com/repos/hulu/restfulgit/contents/tests/fixtures/d408fc2428bc6444cabd7f7b46edbe70b6992b16.diff?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f with necessary adjustments
        self.assertEqual(json, {
            "name": "d408fc2428bc6444cabd7f7b46edbe70b6992b16.diff",
            "path": "tests/fixtures/d408fc2428bc6444cabd7f7b46edbe70b6992b16.diff",
            "sha": "40c739b1166f47c791e87f747f0061739b49af0e",
            "size": 853,
            "url": "http://localhost/repos/restfulgit/contents/tests/fixtures/d408fc2428bc6444cabd7f7b46edbe70b6992b16.diff?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f",
            "git_url": "http://localhost/repos/restfulgit/git/blobs/40c739b1166f47c791e87f747f0061739b49af0e/",
            "type": "file",
            "encoding": "utf-8",
            "_links": {
                "self": "http://localhost/repos/restfulgit/contents/tests/fixtures/d408fc2428bc6444cabd7f7b46edbe70b6992b16.diff?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f",
                "git": "http://localhost/repos/restfulgit/git/blobs/40c739b1166f47c791e87f747f0061739b49af0e/",
            }
        })

    def test_nonexistent_file(self):
        resp = self.client.get('/repos/restfulgit/contents/this-file-does-not-exist')
        self.assertJson404(resp)

    def test_extant_directory_without_trailing_slash(self):
        # From https://api.github.com/repos/hulu/restfulgit/contents/restfulgit?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f with necessary adjustments
        resp = self.client.get('/repos/restfulgit/contents/restfulgit?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f')
        self.assert200(resp)
        self.assertEqual(resp.json, [
            {
                "name": "__init__.py",
                "path": "restfulgit/__init__.py",
                "sha": "db36c03e5649e6e6d23fd431deff3a52ec1faaba",
                "size": 24099,
                "url": "http://localhost/repos/restfulgit/contents/restfulgit/__init__.py?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f",
                "git_url": "http://localhost/repos/restfulgit/git/blobs/db36c03e5649e6e6d23fd431deff3a52ec1faaba/",
                "type": "file",
                "_links": {
                    "self": "http://localhost/repos/restfulgit/contents/restfulgit/__init__.py?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f",
                    "git": "http://localhost/repos/restfulgit/git/blobs/db36c03e5649e6e6d23fd431deff3a52ec1faaba/",
                }
            },
            {
                "name": "__main__.py",
                "path": "restfulgit/__main__.py",
                "sha": "e067d7f361bd3b0f227ba1914c227ebf9539f59d",
                "size": 110,
                "url": "http://localhost/repos/restfulgit/contents/restfulgit/__main__.py?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f",
                "git_url": "http://localhost/repos/restfulgit/git/blobs/e067d7f361bd3b0f227ba1914c227ebf9539f59d/",
                "type": "file",
                "_links": {
                    "self": "http://localhost/repos/restfulgit/contents/restfulgit/__main__.py?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f",
                    "git": "http://localhost/repos/restfulgit/git/blobs/e067d7f361bd3b0f227ba1914c227ebf9539f59d/",
                }
            }
        ])

    def test_extant_directory_with_trailing_slash(self):
        # From https://api.github.com/repos/hulu/restfulgit/contents/restfulgit?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f with necessary adjustments
        resp = self.client.get('/repos/restfulgit/contents/restfulgit/?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f')
        self.assert200(resp)
        self.assertEqual(resp.json, [
            {
                "name": "__init__.py",
                "path": "restfulgit/__init__.py",
                "sha": "db36c03e5649e6e6d23fd431deff3a52ec1faaba",
                "size": 24099,
                "url": "http://localhost/repos/restfulgit/contents/restfulgit/__init__.py?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f",
                "git_url": "http://localhost/repos/restfulgit/git/blobs/db36c03e5649e6e6d23fd431deff3a52ec1faaba/",
                "type": "file",
                "_links": {
                    "self": "http://localhost/repos/restfulgit/contents/restfulgit/__init__.py?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f",
                    "git": "http://localhost/repos/restfulgit/git/blobs/db36c03e5649e6e6d23fd431deff3a52ec1faaba/",
                }
            },
            {
                "name": "__main__.py",
                "path": "restfulgit/__main__.py",
                "sha": "e067d7f361bd3b0f227ba1914c227ebf9539f59d",
                "size": 110,
                "url": "http://localhost/repos/restfulgit/contents/restfulgit/__main__.py?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f",
                "git_url": "http://localhost/repos/restfulgit/git/blobs/e067d7f361bd3b0f227ba1914c227ebf9539f59d/",
                "type": "file",
                "_links": {
                    "self": "http://localhost/repos/restfulgit/contents/restfulgit/__main__.py?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f",
                    "git": "http://localhost/repos/restfulgit/git/blobs/e067d7f361bd3b0f227ba1914c227ebf9539f59d/",
                }
            }
        ])

    def test_root_directory(self):
        resp = self.client.get('/repos/restfulgit/contents/?ref=initial')
        self.assert200(resp)
        self.assertEqual(resp.json, [{
            'name': 'api.py',
            'url': 'http://localhost/repos/restfulgit/contents/api.py?ref=initial',
            'sha': 'ae9d90706c632c26023ce599ac96cb152673da7c',
            '_links': {
                'self': 'http://localhost/repos/restfulgit/contents/api.py?ref=initial',
                'git': 'http://localhost/repos/restfulgit/git/blobs/ae9d90706c632c26023ce599ac96cb152673da7c/'
            },
            'git_url': 'http://localhost/repos/restfulgit/git/blobs/ae9d90706c632c26023ce599ac96cb152673da7c/',
            'path': 'api.py',
            'type': 'file',
            'size': 5543
        }])

    def test_directory_with_subdirectories(self):
        # From https://api.github.com/repos/hulu/restfulgit/contents/tests?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f with necessary adjustments
        resp = self.client.get('/repos/restfulgit/contents/tests?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f')
        self.assert200(resp)
        self.assertEqual(resp.json, [
            {
                "name": "fixtures",
                "path": "tests/fixtures",
                "sha": "7a62b2e0c7e25dc66d110380844c477abf13b91f",
                "size": 0,
                "url": "http://localhost/repos/restfulgit/contents/tests/fixtures?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f",
                "git_url": "http://localhost/repos/restfulgit/git/trees/7a62b2e0c7e25dc66d110380844c477abf13b91f/",
                "type": "dir",
                "_links": {
                    "self": "http://localhost/repos/restfulgit/contents/tests/fixtures?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f",
                    "git": "http://localhost/repos/restfulgit/git/trees/7a62b2e0c7e25dc66d110380844c477abf13b91f/",
                }
            },
            {
                "name": "test_restfulgit.py",
                "path": "tests/test_restfulgit.py",
                "sha": "3da8fd332d44b67ecd9910f5392c73cb62a76a4d",
                "size": 47069,
                "url": "http://localhost/repos/restfulgit/contents/tests/test_restfulgit.py?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f",
                "git_url": "http://localhost/repos/restfulgit/git/blobs/3da8fd332d44b67ecd9910f5392c73cb62a76a4d/",
                "type": "file",
                "_links": {
                    "self": "http://localhost/repos/restfulgit/contents/tests/test_restfulgit.py?ref=7da1a61e2f566cf3094c2fea4b18b111d2638a8f",
                    "git": "http://localhost/repos/restfulgit/git/blobs/3da8fd332d44b67ecd9910f5392c73cb62a76a4d/",
                }
            }
        ])

    def test_nonexistent_directory(self):
        resp = self.client.get('/repos/restfulgit/contents/this-directory-does-not-exist/')
        self.assertJson404(resp)

    def test_symlink(self):
        # FIXME: implement
        pass

    def test_submodule(self):
        # FIXME: implement
        pass


class CompareTestCase(_RestfulGitTestCase):
    def test_works(self):
        resp = self.client.get('/repos/restfulgit/compare/{}...{}.diff'.format('initial', FIFTH_COMMIT))
        self.assert200(resp)
        self.assertContentTypeIsDiff(resp)
        self.assertBytesEqualFixture(resp.get_data(), 'initial_c04112733fe2db2cb2f179fca1a19365cf15fef5.diff')

    def test_empty_diff(self):
        resp = self.client.get('/repos/restfulgit/compare/initial...initial.diff')
        self.assert200(resp)
        self.assertContentTypeIsDiff(resp)
        self.assertEqual(resp.get_data(), b'')  # From https://github.com/hulu/restfulgit/compare/initial...initial.diff

    def test_nonexistent_refspec_404(self):
        resp = self.client.get('/repos/restfulgit/compare/initial...this-branch-does-not-exist.diff')
        self.assertJson404(resp)

    def test_empty_left_refspec_rejected(self):
        resp = self.client.get('/repos/restfulgit/compare/...initial.diff')
        self.assertJson404(resp)

    def test_right_empty_refspec_rejected(self):
        resp = self.client.get('/repos/restfulgit/compare/initial....diff')
        self.assertJson404(resp)

    def test_branch_names_with_dots(self):
        pass

    def test_non_integer_context_rejected(self):  # NOTE: `context` is a RestfulGit extension
        resp = self.client.get('/repos/restfulgit/compare/{}...{}.diff?context=abcdef'.format('initial', FIFTH_COMMIT))
        self.assert400(resp)

    def test_negative_context_rejected(self):  # NOTE: `context` is a RestfulGit extension
        resp = self.client.get('/repos/restfulgit/compare/{}...{}.diff?context=-1'.format('initial', FIFTH_COMMIT))
        self.assert400(resp)

    def test_context_is_honored(self):  # NOTE: `context` is a RestfulGit extension
        resp = self.client.get('/repos/restfulgit/compare/{}...{}.diff?context=1'.format('initial', FIFTH_COMMIT))
        self.assert200(resp)
        self.assertContentTypeIsDiff(resp)
        self.assertBytesEqualFixture(resp.get_data(), 'initial_c04112733fe2db2cb2f179fca1a19365cf15fef5_context_1.diff')


class ContributorsTestCase(_RestfulGitTestCase):
    def test_nonexistent_repo(self):
        resp = self.client.get('/repos/this-repo-does-not-exist/contributors/')
        self.assert404(resp)

    def test_results_well_formed(self):
        resp = self.client.get('/repos/restfulgit/contributors/')
        self.assert200(resp)
        contributors = resp.json
        for contributor in contributors:
            self.assertIsInstance(contributor, dict)
            self.assertIsInstance(contributor.get('name'), unicode)
            self.assertIsInstance(contributor.get('email'), unicode)
            count = contributor.get('contributions')
            self.assertIsInstance(count, int)
            self.assertGreater(count, 0)
        counts = [contributor['contributions'] for contributor in contributors]
        sorted_counts = sorted(counts, reverse=True)
        self.assertEqual(sorted_counts, counts)


if __name__ == '__main__':
    unittest.main()
