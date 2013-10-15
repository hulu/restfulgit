#!/usr/bin/env python2.7
# coding=utf-8
from __future__ import print_function

from flask import Flask, url_for, request, Response, Blueprint, safe_join, send_from_directory
from werkzeug.exceptions import NotFound, BadRequest
from werkzeug.routing import BaseConverter

from pygit2 import (Repository,
                    GIT_OBJ_COMMIT, GIT_OBJ_TREE, GIT_OBJ_BLOB, GIT_OBJ_TAG,
                    GIT_REF_SYMBOLIC, GIT_SORT_TIME)
GIT_MODE_SUBMODULE = int('0160000', 8)

from datetime import datetime, tzinfo, timedelta
from base64 import b64encode
from itertools import islice, ifilter
import json
import os.path
import functools

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


app = Flask(__name__)
restfulgit = Blueprint('restfulgit', __name__)  # pylint: disable=C0103

CONFIG = {}
try:
    execfile("config.conf", CONFIG)
except:  # pylint: disable=W0702
    import sys
    from traceback import print_exc
    print("error loading config:\n", file=sys.stderr)
    print_exc()
    sys.exit(1)

REPO_BASE = CONFIG.get("repo_base_path", "/Code/")
DEFAULT_COMMIT_LIST_LIMIT = CONFIG.get("default_commit_list_limit", 50)


def _get_repo(repo_key):
    path = safe_join(REPO_BASE, repo_key)
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


def _convert_signature(sig):
    return {
        "name": sig.name,
        "email": sig.email,
        "date": datetime.fromtimestamp(sig.time, FixedOffset(sig.offset))
    }


def _convert_commit(repo_key, commit):
    return {
        "url": url_for('.get_commit', _external=True,
                       repo_key=repo_key, sha=commit.hex),
        "sha": commit.hex,
        "author": _convert_signature(commit.author),
        "committer": _convert_signature(commit.committer),
        "message": commit.message,
        "tree": {
            "sha": commit.tree.hex,
            "url": url_for('.get_tree', _external=True,
                           repo_key=repo_key, sha=commit.tree.hex),
        },
        "parents": [{
            "sha": c.hex,
            "url": url_for('.get_commit', _external=True,
                           repo_key=repo_key, sha=c.hex)
        } for c in commit.parents]
    }


def _convert_tree(repo_key, repo, tree):
    entry_list = []
    for entry in tree:
        entry_data = {
            "path": entry.name,
            "sha": entry.hex,
        }
        if entry.filemode == GIT_MODE_SUBMODULE:
            entry_data['type'] = "submodule"
        else:
            obj = repo[entry.oid]
            if obj.type == GIT_OBJ_BLOB:
                entry_data['type'] = "blob"
                entry_data['size'] = obj.size
                entry_data['url'] = url_for('.get_blob', _external=True,
                                            repo_key=repo_key, sha=entry.hex)
            elif obj.type == GIT_OBJ_TREE:
                entry_data['type'] = "tree"
                entry_data['url'] = url_for('.get_tree', _external=True,
                                            repo_key=repo_key, sha=entry.hex)
        entry_data['mode'] = oct(entry.filemode)
        entry_list.append(entry_data)

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
        "url": url_for('.get_ref_list', _external=True,
                       repo_key=repo_key, ref_path=ref.name[5:]),  # [5:] to cut off the redundant refs/
        "ref": ref.name,
        "object": _linkobj_for_gitobj(repo_key, obj, include_type=True),
    }


def jsonify(func):
    def dthandler(obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        return Response(json.dumps(func(*args, **kwargs), default=dthandler),
                        mimetype='application/json')
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

##### VIEWS #####


PLAIN_TEXT = 'text/plain'
OCTET_STREAM = 'application/octet-stream'


def register_converter(blueprint, name, converter):
    @blueprint.record_once
    def registrator(state):  # pylint: disable=W0612
        state.app.url_map.converters[name] = converter


class SHAConverter(BaseConverter):  # pylint: disable=W0232
    regex = r'(?:[0-9a-fA-F]{1,40})'


register_converter(restfulgit, 'sha', SHAConverter)


@restfulgit.route('/repos/<repo_key>/git/commits/')
@jsonify
def get_commit_list(repo_key):
    ref_name = request.args.get('ref_name') or None
    start_sha = request.args.get('start_sha') or None
    limit = request.args.get('limit') or DEFAULT_COMMIT_LIST_LIMIT
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
@jsonify
def get_commit(repo_key, sha):
    repo = _get_repo(repo_key)
    commit = _get_commit(repo, sha)
    return _convert_commit(repo_key, commit)


@restfulgit.route('/repos/<repo_key>/git/trees/<sha:sha>/')
@jsonify
def get_tree(repo_key, sha):
    repo = _get_repo(repo_key)
    tree = _get_tree(repo, sha)
    return _convert_tree(repo_key, repo, tree)


@restfulgit.route('/repos/<repo_key>/git/blobs/<sha:sha>/')
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
@jsonify
def get_tag(repo_key, sha):
    repo = _get_repo(repo_key)
    tag = _get_tag(repo, sha)
    return _convert_tag(repo_key, repo, tag)


@restfulgit.route('/repos/<repo_key>/description/')
def get_description(repo_key):
    _get_repo(repo_key)  # check repo_key validity
    relative_paths = (
        os.path.join(repo_key, 'description'),
        os.path.join(repo_key, '.git', 'description'),
    )
    extant_relative_paths = (relative_path for relative_path in relative_paths if os.path.isfile(safe_join(REPO_BASE, relative_path)))
    extant_relative_path = next(extant_relative_paths, None)
    if extant_relative_path is None:
        return Response("", mimetype=PLAIN_TEXT)
    return send_from_directory(REPO_BASE, extant_relative_path, mimetype=PLAIN_TEXT)


@restfulgit.route('/repos/<repo_key>/git/refs/')
@restfulgit.route('/repos/<repo_key>/git/refs/<path:ref_path>')
@jsonify
def get_ref_list(repo_key, ref_path=None):
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
    if len(ref_data) == 1:
        ref_data = ref_data[0]
    return ref_data


UNSAFE_TEXT_FILENAMES = frozenset({'crossdomain.xml', 'clientaccesspolicy.xml'})
HTML_FILE_EXTENSIONS = frozenset({'html', 'htm', 'xhtml', 'xht'})  # From Wikipedia's HTML and XHTML articles
# From Wikipedia's JavaScript, ECMAScript, JScript, and VBScript articles
WEB_SCRIPT_FILE_EXTENSIONS = frozenset({'js', 'es', 'jse', 'wsf', 'wsc', 'vbs', 'vbe'})
UNSAFE_TEXT_FILE_EXTENSIONS = HTML_FILE_EXTENSIONS | WEB_SCRIPT_FILE_EXTENSIONS
UNSAFE_BINARY_FILE_EXTENSIONS = frozenset({'swf', 'xap', 'jar', 'class'})  # Flash, Silverlight, and Java
# From http://www.whatwg.org/specs/web-apps/current-work/multipage/iana.html
UNSAFE_TEXT_MIME_TYPES = frozenset({'text/html', 'application/xhtml+xml', 'text/cache-manifest'})
MISC_WEB_SCRIPT_MIME_SUBTYPES = frozenset({'ecmascript', 'jscript', 'livescript', 'vbscript', 'vbs'})


def _somewhat_sanitize_mime_type(mime_type, filename):
    # WARNING: Not vetted to provide meaningful security against a malicious repo owner
    # or for an installation exposed to the public Internet.
    orig_mime_type = mime_type

    mime_type = mime_type.lower()
    general_type, _, subtype = mime_type.partition('/')
    if subtype.startswith('x-'):
        subtype = subtype[2:]
        mime_type = '/'.join((general_type, subtype))

    filename = filename.lower()
    extension = os.path.splitext(filename)[1][1:]  # [1:] to remove leading dot

    if extension in UNSAFE_BINARY_FILE_EXTENSIONS or mime_type == 'application/shockwave-flash':
        return OCTET_STREAM
    if general_type == 'application' and ('java' in subtype or 'class' in subtype):
        return OCTET_STREAM

    if (mime_type in UNSAFE_TEXT_MIME_TYPES
            or extension in UNSAFE_TEXT_FILE_EXTENSIONS
            or filename in UNSAFE_TEXT_FILENAMES):
        return PLAIN_TEXT
    # Based on http://www.whatwg.org/specs/web-apps/current-work/multipage/scripting-1.html#scriptingLanguages
    if general_type in {'application', 'text'} and (subtype in MISC_WEB_SCRIPT_MIME_SUBTYPES or subtype.startswith('javascript')):
        return PLAIN_TEXT

    return orig_mime_type


@restfulgit.route('/repos/<repo_key>/raw/<branch_name>/<path:file_path>')
def get_raw(repo_key, branch_name, file_path):
    repo = _get_repo(repo_key)

    ref = _lookup_ref(repo, branch_name)
    if ref is None:
        raise NotFound("branch not found")
    commit_sha = ref.resolve().target.hex

    tree = _get_tree(repo, _get_commit(repo, commit_sha).tree.hex)
    git_obj = _get_object_from_path(repo, tree, file_path)

    if git_obj.type != GIT_OBJ_BLOB:
        return "not a file", 406

    data = git_obj.data
    filename = os.path.basename(file_path)
    mime_type = guess_mime_type(filename, data)
    if mime_type is None:
        mime_type = OCTET_STREAM
    else:
        mime_type = _somewhat_sanitize_mime_type(mime_type, filename)

    resp = Response(data, mimetype=mime_type)
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp


@restfulgit.route('/')
@jsonify
def index():  # pragma: no cover
    links = []
    for rule in app.url_map.iter_rules():
        if str(rule).startswith("/repos"):
            links.append(str(rule))
    return links


app.register_blueprint(restfulgit)

if __name__ == '__main__':  # pragma: no cover
    app.debug = True
    app.run(host="0.0.0.0")


application = app
