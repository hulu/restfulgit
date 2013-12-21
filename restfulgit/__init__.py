# coding=utf-8
from __future__ import print_function

from flask import Flask, url_for, request, Response, current_app, Blueprint, safe_join, send_from_directory, make_response
from werkzeug.exceptions import NotFound, BadRequest, HTTPException, default_exceptions
from werkzeug.routing import BaseConverter

from pygit2 import (Repository,
                    GIT_OBJ_COMMIT, GIT_OBJ_TREE, GIT_OBJ_BLOB, GIT_OBJ_TAG,
                    GIT_REF_SYMBOLIC, GIT_SORT_TIME)
GIT_MODE_SUBMODULE = int('0160000', 8)

from datetime import datetime, tzinfo, timedelta
from base64 import b64encode
from itertools import islice, ifilter
import json
import os
import functools
import re

# Optionally use better libmagic-based MIME-type guessing
try:
    import magic as libmagic
except ImportError:
    import mimetypes

    def guess_mime_type(filename, content):  # pylint: disable=W0613
        (mime_type, encoding) = mimetypes.guess_type(filename)  # pylint: disable=W0612
        return mime_type
else:
    import atexit
    MAGIC = libmagic.Magic(flags=libmagic.MAGIC_MIME_TYPE)
    atexit.register(MAGIC.close)

    def guess_mime_type(filename, content):  # pylint: disable=W0613
        return MAGIC.id_buffer(content)


class DefaultConfig(object):
    RESTFULGIT_DEFAULT_COMMIT_LIST_LIMIT = 50
    RESTFULGIT_ENABLE_CORS = False
    RESTFULGIT_CORS_ALLOWED_HEADERS = []
    RESTFULGIT_CORS_ALLOW_CREDENTIALS = False
    RESTFULGIT_CORS_MAX_AGE = timedelta(days=30)
    RESTFULGIT_CORS_ALLOWED_ORIGIN = "*"


app = Flask(__name__)
app.config.from_object(DefaultConfig)
LOADED_CONFIG = app.config.from_envvar('RESTFULGIT_CONFIG', silent=True)
LOADED_CONFIG = LOADED_CONFIG or app.config.from_pyfile('/etc/restfulgit.conf.py', silent=True)
if not LOADED_CONFIG:
    raise SystemExit("Failed to load any RestfulGit configuration!")
restfulgit = Blueprint('restfulgit', __name__)  # pylint: disable=C0103


### PLUMBING RETRIEVE OBJECTS ###

def _get_repo(repo_key):
    path = safe_join(current_app.config['RESTFULGIT_REPO_BASE_PATH'], repo_key)
    try:
        return Repository(path)
    except KeyError:
        raise NotFound("repository not found")


def _get_commit(repo, sha):
    try:
        commit = repo[unicode(sha)]
    except KeyError:
        raise NotFound("commit not found")
    if commit.type != GIT_OBJ_COMMIT:
        raise NotFound("object not a commit")
    return commit


def _get_tree(repo, sha):
    try:
        tree = repo[unicode(sha)]
    except KeyError:
        raise NotFound("tree not found")
    if tree.type != GIT_OBJ_TREE:
        raise NotFound("object not a tree")
    return tree


def _get_tag(repo, sha):
    try:
        tag = repo[unicode(sha)]
    except KeyError:
        raise NotFound("tag not found")
    if tag.type != GIT_OBJ_TAG:
        raise NotFound("object not a tag")
    return tag


def _get_object_from_path(repo, tree, path):
    path_segments = path.split("/")

    ctree = tree
    for path_seg in path_segments:
        if ctree.type != GIT_OBJ_TREE:
            raise NotFound("invalid path")
        try:
            ctree = repo[ctree[path_seg].oid]
        except KeyError:
            raise NotFound("invalid path")
    return ctree


def _lookup_ref(repo, ref_name):
    try:
        return repo.lookup_reference(ref_name)
    except (ValueError, KeyError):
        if "/" in ref_name and not ref_name.startswith("refs/"):
            ref_name = "refs/" + ref_name
        else:
            ref_name = "refs/heads/" + ref_name

        try:
            return repo.lookup_reference(ref_name)
        except (ValueError, KeyError):
            return None


#### PORCELAIN RETRIEVE OBJECTS ####


def _get_branch(repo, branch_name):
    branch = repo.lookup_branch(branch_name)
    if branch is None:
        raise NotFound("branch not found")
    return branch


def _get_commit_for_refspec(repo, branch_or_tag_or_sha):
    # Precedence order GitHub uses (& that we copy):
    # 1. Branch  2. Tag  3. Commit SHA
    commit_sha = None
    # branch?
    branch_ref = _lookup_ref(repo, branch_or_tag_or_sha)
    if branch_ref is not None:
        commit_sha = branch_ref.resolve().target.hex
    # tag?
    if commit_sha is None:
        ref_to_tag = _lookup_ref(repo, "tags/" + branch_or_tag_or_sha)
        if ref_to_tag is not None:
            commit_sha = ref_to_tag.get_object().hex
    # commit?
    if commit_sha is None:
        commit_sha = branch_or_tag_or_sha
    try:
        return _get_commit(repo, commit_sha)
    except (ValueError, NotFound):
        raise NotFound("no such branch, tag, or commit SHA")


def _get_diff(repo, commit):
    if commit.parents:
        diff = repo.diff(commit.parents[0], commit)
        diff.find_similar()
    else:  # NOTE: RestfulGit extension; GitHub gives a 404 in this case
        diff = commit.tree.diff_to_tree(swap=True)
    return diff


def _get_patches(diff):
    return [patch for patch in diff]


SPLIT_PATCH_TXT_RE = re.compile(r'^\+\+\+\ b\/(.*?)\n(@@.*?)(?=\n^diff|\n\Z)', re.M | re.S)


def _get_patches_txt(diff):
    matches = re.findall(SPLIT_PATCH_TXT_RE, diff.patch)
    return dict(m for m in matches)


DEFAULT_GIT_DESCRIPTION = "Unnamed repository; edit this file 'description' to name the repository.\n"


def _get_repo_description(repo_key):
    relative_paths = (
        os.path.join(repo_key, 'description'),
        os.path.join(repo_key, '.git', 'description'),
    )
    extant_relative_paths = (
        relative_path
        for relative_path in relative_paths
        if os.path.isfile(safe_join(current_app.config['RESTFULGIT_REPO_BASE_PATH'], relative_path))
    )
    extant_relative_path = next(extant_relative_paths, None)
    if extant_relative_path is None:
        return None
    with open(os.path.join(current_app.config['RESTFULGIT_REPO_BASE_PATH'], extant_relative_path), 'r') as content_file:
        description = content_file.read()
        if description == DEFAULT_GIT_DESCRIPTION:
            description = None
        return description


#### PLUMBING OBJECT CONVERTERS ####


def _convert_repo(repo_key):
    description = _get_repo_description(repo_key)
    return {
        "name": repo_key,
        "full_name": repo_key,
        "description": description,
        "url": url_for('.get_repo', _external=True, repo_key=repo_key),
        "branches_url": (url_for('.get_branches', _external=True, repo_key=repo_key).rstrip('/') + '{/branch}'),
        "blobs_url": (url_for('.get_blob', _external=True, repo_key=repo_key, sha='').rstrip('/') + '{/sha}'),
        "commits_url": (url_for('.get_repos_commit', _external=True, repo_key=repo_key, branch_or_tag_or_sha='').rstrip('/') + '{/sha}'),
        "git_commits_url": (url_for('.get_commit', _external=True, repo_key=repo_key, sha='').rstrip('/') + '{/sha}'),
        "git_refs_url": (url_for('.get_refs', _external=True, repo_key=repo_key).rstrip('/') + '{/sha}'),
        "git_tags_url": (url_for('.get_tag', _external=True, repo_key=repo_key, sha='').rstrip('/') + '{/sha}'),
        "tags_url": url_for('.get_tags', _external=True, repo_key=repo_key),
        "trees_url": (url_for('.get_tree', _external=True, repo_key=repo_key, sha='').rstrip('/') + '{/sha}'),
    }


def _convert_signature(sig):
    return {
        "name": sig.name,
        "email": sig.email,
        "date": datetime.fromtimestamp(sig.time, FixedOffset(sig.offset))
    }


def _convert_commit(repo_key, commit, porcelain=False):
    if porcelain:
        def commit_url_for(sha):
            return url_for('.get_repos_commit', _external=True,
                           repo_key=repo_key, branch_or_tag_or_sha=sha)
    else:
        def commit_url_for(sha):
            return url_for('.get_commit', _external=True,
                           repo_key=repo_key, sha=sha)

    return {
        "url": url_for('.get_commit', _external=True,
                       repo_key=repo_key, sha=commit.hex),
        "sha": commit.hex,
        "author": _convert_signature(commit.author),
        "committer": _convert_signature(commit.committer),
        "message": commit.message.rstrip(),
        "tree": {
            "sha": commit.tree.hex,
            "url": url_for('.get_tree', _external=True,
                           repo_key=repo_key, sha=commit.tree.hex),
        },
        "parents": [{
            "sha": c.hex,
            "url": commit_url_for(c.hex),
        } for c in commit.parents]
    }


GIT_STATUS_TO_NAME = {
    'M': 'modified',
    'A': 'added',
    'R': 'renamed',
    'D': 'removed',
}


def _convert_patch(repo_key, commit, patch, patches_txt):
    deleted = patch.status == 'D'
    commit_sha = (commit.hex if not deleted else commit.parents[0].hex)
    result = {
        "sha": patch.new_oid if not deleted else patch.old_oid,
        "status": GIT_STATUS_TO_NAME[patch.status],
        "filename": patch.new_file_path,
        "additions": patch.additions,
        "deletions": patch.deletions,
        "changes": patch.additions + patch.deletions,
        "raw_url": url_for('.get_raw',
                           _external=True,
                           repo_key=repo_key,
                           branch_or_tag_or_sha=commit_sha,
                           file_path=patch.new_file_path),
        "contents_url": url_for('.get_contents',
                                _external=True,
                                repo_key=repo_key,
                                file_path=patch.new_file_path,
                                ref=commit_sha),
    }
    if patch.new_file_path in patches_txt:
        result['patch'] = patches_txt[patch.new_file_path]
    return result


def _repos_convert_commit(repo_key, repo, commit, include_diff=False):
    plain_commit_json = _convert_commit(repo_key, commit, porcelain=True)
    result = {
        "commit": plain_commit_json,
        "sha": plain_commit_json['sha'],
        "author": plain_commit_json['author'],
        "committer": plain_commit_json['committer'],
        "url": url_for('.get_repos_commit', _external=True,
                       repo_key=repo_key, branch_or_tag_or_sha=commit.hex),
        "parents": [{
            "sha": c.hex,
            "url": url_for('.get_repos_commit', _external=True,
                           repo_key=repo_key, branch_or_tag_or_sha=c.hex)
        } for c in commit.parents],
    }
    if include_diff:
        diff = _get_diff(repo, commit)
        patches = _get_patches(diff)
        patches_txt = _get_patches_txt(diff)
        patches_additions = sum(patch.additions for patch in patches)
        patches_deletions = sum(patch.deletions for patch in patches)
        result.update({
            "stats": {
                "additions": patches_additions,
                "deletions": patches_deletions,
                "total": patches_additions + patches_deletions,
            },
            "files": [_convert_patch(repo_key, commit, patch, patches_txt) for patch in patches],
        })
    return result


def _tree_entries(repo_key, repo, tree, recursive=False, path=''):
    entry_list = []
    for entry in tree:
        if entry.filemode == GIT_MODE_SUBMODULE:
            entry_data = {
                "path": entry.name,
                "sha": entry.hex,
                "type": "submodule",
            }
        else:
            obj = repo[entry.oid]
            if obj.type == GIT_OBJ_BLOB:
                entry_data = {
                    "path": '%s%s' % (path, entry.name),
                    "sha": entry.hex,
                    "type": "blob",
                    "size": obj.size,
                    "url": url_for('.get_blob', _external=True,
                                   repo_key=repo_key, sha=entry.hex),
                }
            elif obj.type == GIT_OBJ_TREE:
                if recursive:
                    entry_list += _tree_entries(repo_key, repo, obj, True, '%s%s/' % (path, entry.name))
                entry_data = {
                    "path": "%s%s" % (path, entry.name),
                    "sha": entry.hex,
                    "type": "tree",
                    "url": url_for('.get_tree', _external=True,
                                   repo_key=repo_key, sha=entry.hex)
                }
        entry_data['mode'] = oct(entry.filemode)[1:].zfill(6)  # 6 octal digits without single leading base-indicating 0
        entry_list.append(entry_data)
    return entry_list


def _convert_tree(repo_key, repo, tree, recursive=False):
    entry_list = _tree_entries(repo_key, repo, tree, recursive=recursive)
    entry_list.sort(key=lambda entry: entry['path'])
    return {
        "url": url_for('.get_tree', _external=True,
                       repo_key=repo_key, sha=tree.hex),
        "sha": tree.hex,
        "tree": entry_list,
    }


def _convert_tag(repo_key, repo, tag):
    target_type_name = GIT_OBJ_TYPE_TO_NAME.get(repo[tag.target].type)
    return {
        "url": url_for('.get_tag', _external=True,
                       repo_key=repo_key, sha=tag.hex),
        "sha": tag.hex,
        "tag": tag.name,
        "tagger": _convert_signature(tag.tagger),
        "message": tag.message,
        "object": {
            "type": target_type_name,
            "sha": tag.target.hex,
            "url": url_for('.get_' + target_type_name, _external=True,
                           repo_key=repo_key, sha=tag.target.hex),
        },
    }


GIT_OBJ_TYPE_TO_NAME = {
    GIT_OBJ_COMMIT: 'commit',
    GIT_OBJ_TREE: 'tree',
    GIT_OBJ_BLOB: 'blob',
    GIT_OBJ_TAG: 'tag',
}


def _linkobj_for_gitobj(repo_key, obj, include_type=False):
    data = {}
    data['sha'] = obj.hex
    obj_type = GIT_OBJ_TYPE_TO_NAME.get(obj.type)
    if obj_type is not None:
        data['url'] = url_for('.get_' + obj_type, _external=True,
                              repo_key=repo_key, sha=obj.hex)
    if include_type:
        data['type'] = obj_type
    return data


def _encode_blob_data(data):
    try:
        return 'utf-8', data.decode('utf-8')
    except UnicodeDecodeError:
        return 'base64', b64encode(data)


def _convert_blob(repo_key, blob):
    encoding, data = _encode_blob_data(blob.data)
    return {
        "url": url_for('.get_blob', _external=True,
                       repo_key=repo_key, sha=blob.hex),
        "sha": blob.hex,
        "size": blob.size,
        "encoding": encoding,
        "data": data,
    }


def _convert_ref(repo_key, ref, obj):
    return {
        "url": url_for('.get_refs', _external=True,
                       repo_key=repo_key, ref_path=ref.name[5:]),  # [5:] to cut off the redundant refs/
        "ref": ref.name,
        "object": _linkobj_for_gitobj(repo_key, obj, include_type=True),
    }


#### PORCELAIN DATA CONVERTERS ####


def _convert_branch(repo_key, repo, branch):
    url = url_for('.get_branch', _external=True, repo_key=repo_key, branch_name=branch.branch_name)
    return {
        "name": branch.branch_name,
        "commit": _repos_convert_commit(repo_key, repo, branch.get_object()),
        "url": url,
        "_links": {
            # For some reason GitHub API for branch does the self-link like this
            # instead of with "url" as everywhere else.
            "self": url,
        }
    }


def jsonify(func):
    def dthandler(obj):
        if hasattr(obj, 'isoformat'):
            return obj.astimezone(UTC).replace(tzinfo=None).isoformat() + 'Z'

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        return Response(json.dumps(func(*args, **kwargs), default=dthandler),
                        mimetype='application/json')
    return wrapped


#### VIEW UTILS ####


def corsify(func):
    # based on http://flask.pocoo.org/snippets/56/
    func.provide_automatic_options = False
    func.required_methods = set(getattr(func, 'required_methods', ())) | {'OPTIONS'}

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        if not current_app.config['RESTFULGIT_ENABLE_CORS']:
            return func(*args, **kwargs)
        options_resp = current_app.make_default_options_response()
        if request.method == 'OPTIONS':
            resp = options_resp
        else:
            resp = make_response(func(*args, **kwargs))
        headers = resp.headers
        headers['Access-Control-Allow-Methods'] = options_resp.headers['allow']
        headers['Access-Control-Allow-Origin'] = current_app.config['RESTFULGIT_CORS_ALLOWED_ORIGIN']
        headers['Access-Control-Allow-Credentials'] = str(current_app.config['RESTFULGIT_CORS_ALLOW_CREDENTIALS']).lower()
        allowed_headers = current_app.config['RESTFULGIT_CORS_ALLOWED_HEADERS']
        if allowed_headers:
            headers['Access-Control-Allow-Headers'] = ", ".join(allowed_headers)
        max_age = current_app.config['RESTFULGIT_CORS_MAX_AGE']
        if max_age is not None:
            headers['Access-Control-Max-Age'] = str(int(max_age.total_seconds()))
        return resp

    return wrapped


class FixedOffset(tzinfo):
    ZERO = timedelta(0)

    def __init__(self, offset):
        super(FixedOffset, self).__init__()
        self._offset = timedelta(minutes=offset)

    def utcoffset(self, dt):  # pylint: disable=W0613
        return self._offset

    def dst(self, dt):  # pylint: disable=W0613
        return self.ZERO


UTC = FixedOffset(0)

OCTET_STREAM = 'application/octet-stream'


# JSON error pages based on http://flask.pocoo.org/snippets/83/
def register_general_error_handler(blueprint_or_app, handler):
    error_codes = default_exceptions.keys()
    if isinstance(blueprint_or_app, Blueprint):
        error_codes.remove(500)  # Flask doesn't currently allow per-Blueprint HTTP 500 error handlers

    for err_code in error_codes:
        blueprint_or_app.errorhandler(err_code)(handler)


def json_error_page(error):
    err_msg = error.description if isinstance(error, HTTPException) else unicode(error)
    resp = Response(json.dumps({'error': err_msg}), mimetype='application/json')
    resp.status_code = (error.code if isinstance(error, HTTPException) else 500)
    return resp


register_general_error_handler(restfulgit, json_error_page)
register_general_error_handler(app, json_error_page)


def register_converter(blueprint, name, converter):
    @blueprint.record_once
    def registrator(state):  # pylint: disable=W0612
        state.app.url_map.converters[name] = converter


class SHAConverter(BaseConverter):  # pylint: disable=W0232
    regex = r'(?:[0-9a-fA-F]{1,40})'


register_converter(restfulgit, 'sha', SHAConverter)


##### PLUMBING API VIEWS #####


@restfulgit.route('/repos/<repo_key>/git/commits/')
@corsify
@jsonify
def get_commit_list(repo_key):
    ref_name = request.args.get('ref_name') or None
    start_sha = request.args.get('start_sha') or None
    limit = request.args.get('limit') or current_app.config['RESTFULGIT_DEFAULT_COMMIT_LIST_LIMIT']
    try:
        limit = int(limit)
    except ValueError:
        raise BadRequest("invalid limit")
    if limit < 0:
        raise BadRequest("invalid limit")

    repo = _get_repo(repo_key)

    start_commit_id = None
    if start_sha is not None:
        start_commit_id = start_sha
    else:
        if ref_name is None:
            ref_name = "HEAD"
        ref = _lookup_ref(repo, ref_name)
        if ref is None:
            raise NotFound("reference not found")
        start_commit_id = _lookup_ref(repo, ref_name).resolve().target

    try:
        walker = repo.walk(start_commit_id, GIT_SORT_TIME)
    except ValueError:
        raise BadRequest("invalid start_sha")
    except KeyError:
        raise NotFound("commit not found")

    commits = [_convert_commit(repo_key, commit) for commit in islice(walker, limit)]
    return commits


@restfulgit.route('/repos/<repo_key>/git/commits/<sha:sha>/')
@corsify
@jsonify
def get_commit(repo_key, sha):
    repo = _get_repo(repo_key)
    commit = _get_commit(repo, sha)
    return _convert_commit(repo_key, commit)


@restfulgit.route('/repos/<repo_key>/commits/<branch_or_tag_or_sha>/')
@corsify
@jsonify
def get_repos_commit(repo_key, branch_or_tag_or_sha):
    repo = _get_repo(repo_key)
    commit = _get_commit_for_refspec(repo, branch_or_tag_or_sha)
    return _repos_convert_commit(repo_key, repo, commit, include_diff=True)


@restfulgit.route('/repos/<repo_key>/git/trees/<sha:sha>/')
@corsify
@jsonify
def get_tree(repo_key, sha):
    recursive = request.args.get('recursive') == '1'
    repo = _get_repo(repo_key)
    tree = _get_tree(repo, sha)
    return _convert_tree(repo_key, repo, tree, recursive)


@restfulgit.route('/repos/<repo_key>/git/blobs/<sha:sha>/')
@corsify
@jsonify
def get_blob(repo_key, sha):
    repo = _get_repo(repo_key)
    try:
        blob = repo[unicode(sha)]
    except KeyError:
        raise NotFound("blob not found")
    if blob.type != GIT_OBJ_BLOB:
        raise NotFound("sha not a blob")
    return _convert_blob(repo_key, blob)


@restfulgit.route('/repos/<repo_key>/git/tags/<sha:sha>/')
@corsify
@jsonify
def get_tag(repo_key, sha):
    repo = _get_repo(repo_key)
    tag = _get_tag(repo, sha)
    return _convert_tag(repo_key, repo, tag)


##### PORCELAIN API VIEWS #####


@restfulgit.route('/repos/<repo_key>/')
@corsify
@jsonify
def get_repo(repo_key):
    _get_repo(repo_key)  # check repo_key validity
    return _convert_repo(repo_key)


@restfulgit.route('/repos/')
@corsify
@jsonify
def get_repo_list():
    children = (
        (name, safe_join(current_app.config['RESTFULGIT_REPO_BASE_PATH'], name))
        for name in os.listdir(current_app.config['RESTFULGIT_REPO_BASE_PATH'])
    )
    subdirs = [(dir_name, full_path) for dir_name, full_path in children if os.path.isdir(full_path)]
    mirrors = set(name for name, _ in subdirs if name.endswith('.git'))
    working_copies = set(name for name, full_path in subdirs if os.path.isdir(safe_join(full_path, '.git')))
    repositories = list(mirrors | working_copies)
    repositories.sort()
    return [_convert_repo(repo_key) for repo_key in repositories]


TAG_REF_PREFIX = "refs/tags/"


@restfulgit.route('/repos/<repo_key>/tags/')
@corsify
@jsonify
def get_tags(repo_key):
    repo = _get_repo(repo_key)
    ref_names = ifilter(lambda ref_name: ref_name.startswith(TAG_REF_PREFIX), repo.listall_references())
    tags = (repo.lookup_reference(ref_name) for ref_name in ref_names)
    return [
        {
            "name": tag.shorthand,
            "commit": {
                "sha": tag.get_object().hex,
                "url": url_for('.get_repos_commit', _external=True,
                               repo_key=repo_key, branch_or_tag_or_sha=tag.get_object().hex),
            },
        }
        for tag in tags
    ]


@restfulgit.route('/repos/<repo_key>/tags/<tag_name>/')
@corsify
@jsonify
def get_repos_tag(repo_key, tag_name):  # NOTE: This endpoint is a RestfulGit extension
    repo = _get_repo(repo_key)
    tag = _lookup_ref(repo, TAG_REF_PREFIX + tag_name)
    if tag is None:
        raise NotFound("tag not found")
    result = {
        "name": tag.shorthand,
        "commit": _repos_convert_commit(repo_key, repo, tag.get_object()),
        "url": url_for('.get_repos_tag', _external=True,
                       repo_key=repo_key, tag_name=tag.shorthand),
    }
    # simple tag
    if tag.target != tag.get_object().oid:
        tag_obj = repo[tag.target]
        result['tag'] = _convert_tag(repo_key, repo, tag_obj)
    return result


@restfulgit.route('/repos/<repo_key>/commit/<branch_or_tag_or_sha>.diff')
@corsify
def get_repos_diff(repo_key, branch_or_tag_or_sha=None):
    repo = _get_repo(repo_key)
    commit = _get_commit_for_refspec(repo, branch_or_tag_or_sha)
    diff = _get_diff(repo, commit)
    return Response(diff.patch, mimetype="text/x-diff")


@restfulgit.route('/repos/<repo_key>/branches/')
@corsify
@jsonify
def get_branches(repo_key):
    repo = _get_repo(repo_key)
    branches = (repo.lookup_branch(branch_name) for branch_name in repo.listall_branches())
    return [
        {
            "name": branch.branch_name,
            "commit": {
                "sha": branch.target.hex,
                "url": url_for('.get_repos_commit', _external=True,
                               repo_key=repo_key, branch_or_tag_or_sha=branch.target.hex),
            },
        }
        for branch in branches
    ]


@restfulgit.route('/repos/<repo_key>/branches/<branch_name>/')
@corsify
@jsonify
def get_branch(repo_key, branch_name):
    repo = _get_repo(repo_key)
    branch = _get_branch(repo, branch_name)
    return _convert_branch(repo_key, repo, branch)


@restfulgit.route('/repos/<repo_key>/git/refs/')
@restfulgit.route('/repos/<repo_key>/git/refs/<path:ref_path>')
@corsify
@jsonify
def get_refs(repo_key, ref_path=None):
    if ref_path is not None:
        ref_path = "refs/" + ref_path
    else:
        ref_path = ""
    repo = _get_repo(repo_key)
    ref_names = ifilter(lambda x: x.startswith(ref_path), repo.listall_references())
    references = (repo.lookup_reference(ref_name) for ref_name in ref_names)
    nonsymbolic_refs = ifilter(lambda x: x.type != GIT_REF_SYMBOLIC, references)
    ref_data = [
        _convert_ref(repo_key, reference, repo[reference.target])
        for reference in nonsymbolic_refs
    ]
    if len(ref_data) == 1 and ref_data[0]['ref'] == ref_path:
        # exact match
        ref_data = ref_data[0]
    return ref_data


@restfulgit.route('/repos/<repo_key>/raw/<branch_or_tag_or_sha>/<path:file_path>')
@corsify
def get_raw(repo_key, branch_or_tag_or_sha, file_path):
    repo = _get_repo(repo_key)
    commit = _get_commit_for_refspec(repo, branch_or_tag_or_sha)
    tree = _get_tree(repo, commit.tree.hex)
    git_obj = _get_object_from_path(repo, tree, file_path)

    if git_obj.type != GIT_OBJ_BLOB:
        return "not a file", 406

    data = git_obj.data
    mime_type = guess_mime_type(os.path.basename(file_path), data)
    if mime_type is None:
        mime_type = OCTET_STREAM
    return Response(data, mimetype=mime_type)


@restfulgit.route('/repos/<repo_key>/contents/<path:file_path>')
@corsify
def get_contents(repo_key, path):  # pylint: disable=W0613
    ref = request.args.get('ref')  # pylint: disable=W0612
    raise NotImplementedError()


@restfulgit.route('/')
@corsify
@jsonify
def index():  # pragma: no cover
    links = []
    for rule in app.url_map.iter_rules():
        if str(rule).startswith("/repos"):
            links.append(str(rule))
    return links


app.register_blueprint(restfulgit)

application = app
