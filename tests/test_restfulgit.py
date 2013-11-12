# coding=utf-8
from __future__ import absolute_import, unicode_literals

import unittest
from hashlib import sha512
from os import remove as _delete_file
import io
import os.path

from flask.ext.testing import TestCase as _FlaskTestCase

import restfulgit


RESTFULGIT_REPO = os.path.abspath(os.path.join(os.path.dirname(restfulgit.__file__), '..'))
TEST_SUBDIR = os.path.join(RESTFULGIT_REPO, 'test')
GIT_MIRROR_DESCRIPTION_FILEPATH = os.path.join(RESTFULGIT_REPO, 'description')
NORMAL_CLONE_DESCRIPTION_FILEPATH = os.path.join(RESTFULGIT_REPO, '.git', 'description')
PARENT_DIR_OF_RESTFULGIT_REPO = os.path.join(os.path.abspath(os.path.join(RESTFULGIT_REPO, '..')), '')
FIRST_COMMIT = "07b9bf1540305153ceeb4519a50b588c35a35464"
TREE_OF_FIRST_COMMIT = "6ca22167185c31554aa6157306e68dfd612d6345"
BLOB_FROM_FIRST_COMMIT = "ae9d90706c632c26023ce599ac96cb152673da7c"
TAG_FOR_FIRST_COMMIT = "1dffc031c9beda43ff94c526cbc00a30d231c079"
FIFTH_COMMIT = "c04112733fe2db2cb2f179fca1a19365cf15fef5"
IMPROBABLE_SHA = "f" * 40


def delete_file_quietly(filepath):
    try:
        _delete_file(filepath)
    except EnvironmentError as err:
        pass


class _RestfulGitTestCase(_FlaskTestCase):
    def create_app(self):
        restfulgit.REPO_BASE = PARENT_DIR_OF_RESTFULGIT_REPO
        return restfulgit.app


class RepoKeyTestCase(_RestfulGitTestCase):
    def test_nonexistent_directory(self):
        resp = self.client.get('/repos/this-directory-does-not-exist/git/commits/')
        self.assert404(resp)

    def test_directory_is_not_git_repo(self):
        restfulgit.REPO_BASE = RESTFULGIT_REPO
        resp = self.client.get('/repos/test/git/commits/')
        self.assert404(resp)

    def test_dot_dot_disallowed(self):
        restfulgit.REPO_BASE = TEST_SUBDIR
        resp = self.client.get('/repos/../git/commits/')
        self.assert404(resp)

    def test_list_repos(self):
        resp = self.client.get('/repos/')
        self.assert200(resp)
        result = resp.json
        self.assertIsInstance(result, dict)
        self.assertEqual(result.viewkeys(), {'repos'})
        repo_list = result['repos']
        self.assertIsInstance(repo_list, list)
        self.assertIn('restfulgit', repo_list)


class SHAConverterTestCase(_RestfulGitTestCase):
    def test_empty_sha_rejected(self):
        resp = self.client.get('/repos/restfulgit/git/trees/')
        self.assert404(resp)

    def test_too_long_sha_rejected(self):
        resp = self.client.get('/repos/restfulgit/git/trees/{}0/'.format(TREE_OF_FIRST_COMMIT))
        self.assert404(resp)

    def test_malformed_sha_rejected(self):
        resp = self.client.get('/repos/restfulgit/git/trees/0123456789abcdefghijklmnopqrstuvwxyzABCD/')
        self.assert404(resp)

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
        self.assert404(resp)

    def test_non_commit_start_sha(self):
        resp = self.client.get('/repos/restfulgit/git/commits/?start_sha={}'.format(TREE_OF_FIRST_COMMIT))
        self.assert400(resp)

    def test_malformed_start_sha(self):
        resp = self.client.get('/repos/restfulgit/git/commits/?start_sha=thisIsNotHexHash')
        self.assert400(resp)

    def test_start_sha_works_basic(self):
        resp = self.client.get('/repos/restfulgit/git/commits?start_sha={}'.format(FIRST_COMMIT), follow_redirects=True)
        self.assert200(resp)

    def test_nonexistent_ref_name(self):
        resp = self.client.get('/repos/restfulgit/git/commits/?ref_name=doesNotExist')
        self.assert404(resp)

    def test_ref_name_works(self):
        resp = self.client.get('/repos/restfulgit/git/commits?ref_name=master', follow_redirects=True)
        self.assert200(resp)
        # FIXME: should be more thorough

    def test_non_integer_limit_rejected(self):
        resp = self.client.get('/repos/restfulgit/git/commits/?limit=abc123')
        self.assert400(resp)

    def test_negative_limit_rejected(self):
        resp = self.client.get('/repos/restfulgit/git/commits/?limit=-1')
        self.assert400(resp)

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
                        'date': '2013-02-26T19:14:13-08:00',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'committer': {
                        'date': '2013-02-26T19:14:13-08:00',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'message': 'add file mode\n',
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
                        'date': '2013-02-26T01:15:35-08:00',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'committer': {
                        'date': '2013-02-26T01:15:35-08:00',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'message': 'Now using a jsonify decorator which returns the correct content-type\n',
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
                        'date': '2013-02-25T04:35:29-08:00',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'committer': {
                        'date': '2013-02-25T04:35:29-08:00',
                        'email': 'rajiv@hulu.com',
                        'name': 'Rajiv Makhijani'
                    },
                    'message': 'Support submodule in tree-listings\n',
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
        self.assert404(resp)

    def test_get_tree_with_non_tree_sha(self):
        resp = self.client.get('/repos/restfulgit/git/trees/{}/'.format(BLOB_FROM_FIRST_COMMIT))
        self.assert404(resp)

    def test_get_blob_with_non_blob_sha(self):
        resp = self.client.get('/repos/restfulgit/git/blobs/{}/'.format(FIRST_COMMIT))
        self.assert404(resp)

    def test_get_tag_with_non_tag_sha(self):
        resp = self.client.get('/repos/restfulgit/git/tags/{}/'.format(BLOB_FROM_FIRST_COMMIT))
        self.assert404(resp)

    def test_get_commit_with_nonexistent_sha(self):
        resp = self.client.get('/repos/restfulgit/git/commits/{}/'.format(IMPROBABLE_SHA))
        self.assert404(resp)

    def test_get_tree_with_nonexistent_sha(self):
        resp = self.client.get('/repos/restfulgit/git/trees/{}/'.format(IMPROBABLE_SHA))
        self.assert404(resp)

    def test_get_blob_with_nonexistent_sha(self):
        resp = self.client.get('/repos/restfulgit/git/blobs/{}/'.format(IMPROBABLE_SHA))
        self.assert404(resp)

    def test_get_tag_with_nonexistent_sha(self):
        resp = self.client.get('/repos/restfulgit/git/tags/{}/'.format(IMPROBABLE_SHA))
        self.assert404(resp)

    def test_get_commit_works(self):
        resp = self.client.get('/repos/restfulgit/git/commits/{}/'.format(FIRST_COMMIT))
        self.assert200(resp)
        self.assertEqual(
            resp.json,
            {
                "committer": {
                    "date": "2013-02-24T05:25:46-08:00",
                    "name": "Rajiv Makhijani",
                    "email": "rajiv@hulu.com"
                },
                "author": {
                    "date": "2013-02-24T05:25:46-08:00",
                    "name": "Rajiv Makhijani",
                    "email": "rajiv@hulu.com"
                },
                "url": "http://localhost/repos/restfulgit/git/commits/07b9bf1540305153ceeb4519a50b588c35a35464/",
                "tree": {
                    "url": "http://localhost/repos/restfulgit/git/trees/6ca22167185c31554aa6157306e68dfd612d6345/",
                    "sha": "6ca22167185c31554aa6157306e68dfd612d6345"
                },
                "sha": "07b9bf1540305153ceeb4519a50b588c35a35464",
                "parents": [],
                "message": "Initial support for read-only REST api for Git plumbing\n"
            }
        )

    def test_get_tree_works(self):
        resp = self.client.get('/repos/restfulgit/git/trees/{}/'.format(TREE_OF_FIRST_COMMIT))
        self.assert200(resp)
        self.assertEqual(
            resp.json,
            {
                "url": "http://localhost/repos/restfulgit/git/trees/6ca22167185c31554aa6157306e68dfd612d6345/",
                "sha": "6ca22167185c31554aa6157306e68dfd612d6345",
                "tree": [
                    {
                        "url": "http://localhost/repos/restfulgit/git/blobs/ae9d90706c632c26023ce599ac96cb152673da7c/",
                        "sha": "ae9d90706c632c26023ce599ac96cb152673da7c",
                        "mode": "0100644",
                        "path": "api.py",
                        "type": "blob",
                        "size": 5543
                    }
                ]
            }
        )

    def test_get_blob_works(self):
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
                "encoding": "utf-8",
                "size": 5543
            }
        )

    def test_get_tag_works(self):
        resp = self.client.get('/repos/restfulgit/git/tags/{}/'.format(TAG_FOR_FIRST_COMMIT))
        self.assert200(resp)
        self.assertEqual(
            resp.json,
            {
                "url": "http://localhost/repos/restfulgit/git/tags/1dffc031c9beda43ff94c526cbc00a30d231c079/",
                "object": {
                    "url": "http://localhost/repos/restfulgit/git/commits/07b9bf1540305153ceeb4519a50b588c35a35464/",
                    "sha": "07b9bf1540305153ceeb4519a50b588c35a35464",
                    "type": "commit"
                },
                "sha": "1dffc031c9beda43ff94c526cbc00a30d231c079",
                "tag": "initial",
                "tagger": {
                    "date": "2013-09-27T18:14:09-07:00",
                    "name": "Chris Rebert",
                    "email": "chris.rebert@hulu.com"
                },
                "message": "initial commit\n"
            }
        )


class RefsTestCase(_RestfulGitTestCase):
    def test_get_ref_list_works(self):
        resp = self.client.get('/repos/restfulgit/git/refs/')
        self.assert200(resp)
        ref_list = resp.json
        self.assertIsInstance(ref_list, list)
        for ref in ref_list:
            self.assertIsInstance(ref, dict)
            self.assertEqual(ref.viewkeys(), {'object', 'ref', 'url'})

            self.assertIsInstance(ref['ref'], unicode)
            self.assertIsInstance(ref['url'], unicode)

            obj = ref['object']
            self.assertIsInstance(obj, dict)
            self.assertEqual(obj.viewkeys(), {'type', 'sha', 'url'})
            for val in obj.itervalues():
                self.assertIsInstance(val, unicode)
            self.assertIn(obj['type'], {'commit', 'tag'})

    def test_invalid_ref_path(self):
        resp = self.client.get('/repos/restfulgit/git/refs/this_ref/path_does/not_exist')
        self.assert200(resp)
        self.assertEqual([], resp.json)

    def test_valid_ref_path(self):
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
        resp = self.client.get('/repos/restfulgit/blob/this-branch-does-not-exist/LICENSE.md')
        self.assert404(resp)

    def test_nonexistent_file_path(self):
        resp = self.client.get('/repos/restfulgit/blob/master/this_path/does_not/exist.txt')
        self.assert404(resp)

    def test_mime_type_logic(self):
        # FIXME: implement
        pass

    def test_branches_trump_tags(self):
        # branch "ambiguous" = commit 1f51b91
        #     api.py's SHA-512 = e948e8d0b0d0703d972279382a002c90040ff19d636e96927262d63e1f1429526539ea781744d2f3a65a5938b59e0c5f57adadc26f797480efcfc6f7dcff3d81
        # tag "ambiguous" = commit ff6405b
        #     api.py's SHA-512 = a50e02753d282c0e35630bbbc16a525ea4e0b2e2af668135b603c8e1467c7269bcbe9075886baf3f08ce195a7eab1e0b8179080af08a2c0f3eda3b9518650fa1
        resp = self.client.get("/repos/restfulgit/blob/ambiguous/api.py")
        self.assert200(resp)
        self.assertEqual(
            'e948e8d0b0d0703d972279382a002c90040ff19d636e96927262d63e1f1429526539ea781744d2f3a65a5938b59e0c5f57adadc26f797480efcfc6f7dcff3d81',
            sha512(resp.data).hexdigest()
        )

    def test_sha_works(self):
        resp = self.client.get('/repos/restfulgit/blob/326d80cd68ec3413fe6eaca99c52c59ca428a0d0/api.py')
        self.assert200(resp)
        self.assertEqual(
            '0229e0a11f6a3c8c9b84c50ecbd54d476edf5c0767137e37526d1961210530aa6bd93f67a70bd4ea1998d65cdbe74c7fd8b90482ef5cbdf244cc697e3135e497',
            sha512(resp.data).hexdigest()
        )

    def test_tag_works(self):
        resp = self.client.get('/repos/restfulgit/blob/initial/api.py')
        self.assert200(resp)
        self.assertEqual(
            '1c846bb4d44c08073c487316a7dc02d97d825aecf50546caf9bf10277c01d17e19860d5f86de877268dd969bd081c7595991c325e0ab492374b956e3a6c9967f',
            sha512(resp.data).hexdigest()
        )

    def test_branch_works(self):
        resp = self.client.get('/repos/restfulgit/blob/master/LICENSE.md')
        self.assert200(resp)
        self.assertEqual(
            '7201955547d83fb4e740adf52d95c3044591ec8b60e4a136f5486a05d1dfaac2bd44d4546830cf0f32d05b40ce5928d0b3f71e0b2628488ea0db1427a6dd2988',
            sha512(resp.data).hexdigest()
        )


class DescriptionTestCase(_RestfulGitTestCase):
    def test_no_description_file(self):
        delete_file_quietly(NORMAL_CLONE_DESCRIPTION_FILEPATH)
        delete_file_quietly(GIT_MIRROR_DESCRIPTION_FILEPATH)
        resp = self.client.get('/repos/restfulgit/description/')
        self.assert200(resp)
        self.assertEqual(resp.data, "")

    def test_dot_dot_disallowed(self):
        restfulgit.REPO_BASE = TEST_SUBDIR
        resp = self.client.get('/repos/../description/')
        self.assert404(resp)

    def test_nonexistent_repo(self):
        restfulgit.REPO_BASE = RESTFULGIT_REPO
        resp = self.client.get('/repos/test/description/')
        self.assert404(resp)

    def test_works_normal_clone(self):
        description = "REST API for Git data\n"
        with io.open(NORMAL_CLONE_DESCRIPTION_FILEPATH, mode='wt', encoding='utf-8') as description_file:
            description_file.write(description)
        try:
            resp = self.client.get('/repos/restfulgit/description/')
            self.assertEqual(resp.data, description)
        finally:
            delete_file_quietly(NORMAL_CLONE_DESCRIPTION_FILEPATH)

    def test_works_git_mirror(self):
        description = "REST API for Git data\n"
        with io.open(GIT_MIRROR_DESCRIPTION_FILEPATH, mode='wt', encoding='utf-8') as description_file:
            description_file.write(description)
        try:
            resp = self.client.get('/repos/restfulgit/description/')
            self.assertEqual(resp.data, description)
        finally:
            delete_file_quietly(GIT_MIRROR_DESCRIPTION_FILEPATH)


if __name__ == '__main__':
    unittest.main()
