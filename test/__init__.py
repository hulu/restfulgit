# coding=utf-8
from __future__ import unicode_literals

from hashlib import sha512
import io
import os.path

from flask.ext.testing import TestCase as _FlaskTestCase

import gitapi


RESTFULGIT_REPO = os.path.dirname(gitapi.__file__)
DESCRIPTION_FILEPATH = os.path.join(RESTFULGIT_REPO, '.git', 'description')
PARENT_DIR_OF_RESTFULGIT_REPO = os.path.join(os.path.abspath(os.path.join(RESTFULGIT_REPO, '..')), '')
FIRST_COMMIT = "07b9bf1540305153ceeb4519a50b588c35a35464"
TREE_OF_FIRST_COMMIT = "6ca22167185c31554aa6157306e68dfd612d6345"
BLOB_FROM_FIRST_COMMIT = "ae9d90706c632c26023ce599ac96cb152673da7c"


class _GitApiTestCase(_FlaskTestCase):
    def create_app(self):
        gitapi.REPO_BASE = PARENT_DIR_OF_RESTFULGIT_REPO
        return gitapi.app


class RepoKeyTestCase(_GitApiTestCase):
    def test_nonexistent_directory(self):
        resp = self.client.get('/repos/this-directory-does-not-exist/git/commits')
        self.assert404(resp)

    def test_directory_is_not_git_repo(self):
        gitapi.app.REPO_BASE = RESTFULGIT_REPO
        resp = self.client.get('/repos/test/git/commits')
        self.assert404(resp)

    def test_dot_dot_disallowed(self):
        # FIXME: implement
        # resp = self.client.get('/repos/../git/commits')
        # self.assert403(resp)
        pass


class SHAConverterTestCase(_GitApiTestCase):
    def test_empty_sha_rejected(self):
        resp = self.client.get('/repos/restfulgit/git/trees/')
        self.assert404(resp)

    def test_too_long_sha_rejected(self):
        resp = self.client.get('/repos/restfulgit/git/trees/{}0'.format(TREE_OF_FIRST_COMMIT))
        self.assert404(resp)

    def test_malformed_sha_rejected(self):
        resp = self.client.get('/repos/restfulgit/git/trees/0123456789abcdefghijklmnopqrstuvwxyzABCD')
        self.assert404(resp)

    def test_full_sha_accepted(self):
        resp = self.client.get('/repos/restfulgit/git/trees/{}'.format(TREE_OF_FIRST_COMMIT))
        self.assert200(resp)

    def test_partial_sha_accepted(self):
        resp = self.client.get('/repos/restfulgit/git/trees/{}'.format(TREE_OF_FIRST_COMMIT[:35]))
        self.assert200(resp)


class CommitsTestCase(_GitApiTestCase):
    """Tests the "commits" endpoint."""
    def test_nonexistent_start_sha(self):
        resp = self.client.get('/repos/restfulgit/git/commits?start_sha=1234567890abcdef')
        self.assert404(resp)

    def test_non_commit_start_sha(self):
        resp = self.client.get('/repos/restfulgit/git/commits?start_sha={}'.format(TREE_OF_FIRST_COMMIT))
        self.assert400(resp)

    def test_malformed_start_sha(self):
        resp = self.client.get('/repos/restfulgit/git/commits?start_sha=thisIsNotHexHash')
        self.assert400(resp)

    def test_start_sha_works(self):
        resp = self.client.get('/repos/restfulgit/git/commits?start_sha={}'.format(FIRST_COMMIT))
        self.assert200(resp)
        # FIXME: should be more thorough

    def test_nonexistent_ref_name(self):
        resp = self.client.get('/repos/restfulgit/git/commits?ref_name=doesNotExist')
        self.assert404(resp)

    def test_ref_name_works(self):
        resp = self.client.get('/repos/restfulgit/git/commits?ref_name=master')
        self.assert200(resp)
        # FIXME: should be more thorough

    def test_non_integer_limit_rejected(self):
        resp = self.client.get('/repos/restfulgit/git/commits?limit=abc123')
        self.assert400(resp)

    def test_negative_limit_rejected(self):
        resp = self.client.get('/repos/restfulgit/git/commits?limit=-1')
        self.assert400(resp)

    def test_limit_works(self):
        resp = self.client.get('/repos/restfulgit/git/commits?limit=3')
        self.assert200(resp)
        # FIXME: should be more thorough

    #FIXME: test combos


class SimpleSHATestCase(_GitApiTestCase):
    def test_get_commit_with_non_commit_sha(self):
        resp = self.client.get('/repos/restfulgit/git/commits/{}'.format(BLOB_FROM_FIRST_COMMIT))
        self.assert404(resp)

    def test_get_tree_with_non_tree_sha(self):
        resp = self.client.get('/repos/restfulgit/git/trees/{}'.format(BLOB_FROM_FIRST_COMMIT))
        self.assert404(resp)

    def test_get_blob_with_non_blob_sha(self):
        resp = self.client.get('/repos/restfulgit/git/blobs/{}'.format(FIRST_COMMIT))
        self.assert404(resp)

    def test_get_tag_with_non_tag_sha(self):
        resp = self.client.get('/repos/restfulgit/git/tags/{}'.format(BLOB_FROM_FIRST_COMMIT))
        self.assert404(resp)

    def test_get_commit_works(self):
        resp = self.client.get('/repos/restfulgit/git/commits/{}'.format(FIRST_COMMIT))
        self.assert200(resp)
        # FIXME: should be more thorough

    def test_get_tree_works(self):
        resp = self.client.get('/repos/restfulgit/git/trees/{}'.format(TREE_OF_FIRST_COMMIT))
        self.assert200(resp)
        # FIXME: should be more thorough

    def test_get_blob_works(self):
        resp = self.client.get('/repos/restfulgit/git/blobs/{}'.format(BLOB_FROM_FIRST_COMMIT))
        self.assert200(resp)
        # FIXME: should be more thorough

    def test_get_tag_works(self):
        # resp = self.client.get('/repos/restfulgit/git/tags/{}'.format())
        # FIXME: implement
        pass


class RefsTestCase(_GitApiTestCase):
    def test_get_ref_list_works(self):
        resp = self.client.get('/repos/restfulgit/git/refs')
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
            obj.viewkeys() == {'type', 'sha', 'url'}
            for val in obj.itervalues():
                self.assertIsInstance(val, unicode)
            self.assertIn(obj['type'], {'commit'})

    def test_invalid_ref_path(self):
        resp = self.client.get('/repos/restfulgit/git/refs/this_ref/path_does/not_exist')
        self.assert200(resp)
        self.assertEqual([], resp.json)

    def test_valid_ref_path(self):
        resp = self.client.get('/repos/restfulgit/git/refs/heads/master')
        self.assert200(resp)
        # FIXME: should be more thorough


class RawFileTestCase(_GitApiTestCase):
    def test_nonexistent_branch(self):
        resp = self.client.get('/repos/restfulgit/raw/this-branch-does-not-exist/LICENSE.md')
        self.assert404(resp)

    def test_nonexistent_file_path(self):
        resp = self.client.get('/repos/restfulgit/raw/master/this_path/does_not/exist.txt')
        self.assert404(resp)

    def test_file_path_security(self):
        # FIXME: implement
        pass

    def test_mime_type_logic(self):
        # FIXME: implement
        pass

    def test_works(self):
        resp = self.client.get('/repos/restfulgit/raw/master/LICENSE.md')
        self.assert200(resp)
        self.assertEqual(
            '7201955547d83fb4e740adf52d95c3044591ec8b60e4a136f5486a05d1dfaac2bd44d4546830cf0f32d05b40ce5928d0b3f71e0b2628488ea0db1427a6dd2988',
            sha512(resp.data).hexdigest()
        )


class DescriptionTestCase(_GitApiTestCase):
    def test_no_description_file(self):
        try:
            os.remove(DESCRIPTION_FILEPATH)
        except OSError:
            pass
        resp = self.client.get('/repos/restfulgit/description')
        self.assert200(resp)
        self.assertEqual(resp.data, "")

    def test_dot_dot_disallowed(self):
        resp = self.client.get('/repos/../description')
        self.assert404(resp)

    def test_nonexistent_repo(self):
        gitapi.app.REPO_BASE = RESTFULGIT_REPO
        resp = self.client.get('/repos/test/description')
        self.assert404(resp)

    def test_works(self):
        description = "REST API for Git data\n"
        with io.open(DESCRIPTION_FILEPATH, mode='wt', encoding='utf-8') as description_file:
            description_file.write(description)
        resp = self.client.get('/repos/restfulgit/description')
        self.assertEqual(resp.data, description)
