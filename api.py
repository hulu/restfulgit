from flask import Flask, url_for, request, Response
from werkzeug.exceptions import NotFound, BadRequest
app = Flask(__name__)
from pygit2 import Repository, GIT_OBJ_COMMIT, GIT_OBJ_TREE, GIT_OBJ_BLOB, GIT_REF_SYMBOLIC, GIT_SORT_TIME
from datetime import datetime, tzinfo, timedelta
import json
from base64 import b64encode
import functools

def dthandler(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()

def jsonify(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        return Response(json.dumps(f(*args, **kwargs), default=dthandler), mimetype='application/json')
    return wrapped

class FixedOffset(tzinfo):
    ZERO = timedelta(0)
    def __init__(self, offset):
        self._offset = timedelta(minutes = offset)

    def utcoffset(self, dt):
        return self._offset

    def dst(self, dt):
        return self.ZERO

REPO_BASE = '/Users/rajiv/HuluCode/'

def _get_repo(repo_key):
    path = REPO_BASE + repo_key
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
        raise NotFound("sha not a commit")
    return commit

def _lookup_ref(repo, ref_name):
    try:
        return repo.lookup_reference(ref_name)
    except:
        if "/" in ref_name and not ref_name.startswith("refs/"):
            ref_name = "refs/" + ref_name
        else:
            ref_name = "refs/heads/" + ref_name

        try:
            return repo.lookup_reference(ref_name)
        except:
            return None


def _convert_signature(sig):
    return {
        "name" : sig.name,
        "email" : sig.email,
        "date" : datetime.fromtimestamp(sig.time, FixedOffset(sig.offset))
    }

def _convert_commit(repo_key, commit):
    return {
        "url": url_for('get_commit', _external=True, repo_key=repo_key, sha=commit.hex),
        "sha": commit.hex,
        "author": _convert_signature(commit.author),
        "committer": _convert_signature(commit.committer),
        "message": commit.message,
        "tree" : {
            "sha": commit.tree.hex,
            "url": url_for('get_tree', _external=True, repo_key=repo_key, sha=commit.tree.hex),
        },
        "parents" : [{
            "sha": c.hex,
            "url": url_for('get_commit', _external=True, repo_key=repo_key, sha=c.hex)
        } for c in commit.parents]
    }

GIT_MODE_SUBMODULE = int('0160000', 8)

def _convert_tree(repo_key, tree):
    entry_list = []
    for entry in tree:
        entry_data = {
            "path": entry.name,
            "sha": entry.hex,
        }
        if entry.filemode == GIT_MODE_SUBMODULE:
            entry_data['type'] = "submodule"
        else:
            obj = entry.to_object()
            if obj.type == GIT_OBJ_BLOB:
                entry_data['type'] = "blob"
                entry_data['size'] = obj.size
                entry_data['url'] = url_for('get_blob', _external=True, repo_key=repo_key, sha=entry.hex)
            elif obj.type == GIT_OBJ_TREE:
                entry_data['type'] = "tree"
                entry_data['url'] = url_for('get_tree', _external=True, repo_key=repo_key, sha=entry.hex)
        entry_data['mode'] = oct(entry.filemode)
        entry_list.append(entry_data)

    return {
        "url": url_for('get_tree', _external=True, repo_key=repo_key, sha=tree.hex),
        "sha": tree.hex,
        "tree": entry_list,
    }

def _linkobj_for_gitobj(repo_key, obj, include_type=False):
    data = {}
    data['sha'] = obj.hex
    obj_type = None
    if obj.type == GIT_OBJ_COMMIT:
        obj_type = 'commit'
    elif obj.type == GIT_OBJ_TREE:
        obj_type = 'tree'
    elif obj.type == GIT_OBJ_BLOB:
        obj_type = 'blob'
    if obj_type is not None:
        data['url'] = url_for('get_' + obj_type, _external=True, repo_key=repo_key, sha=obj.hex)
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
        "url": url_for('get_blob', _external=True, repo_key=repo_key, sha=blob.hex),
        "sha": blob.hex,
        "size": blob.size,
        "encoding": encoding,
        "data": data,
    }

def _convert_ref(repo_key, ref, obj):
    return {
        "url": url_for('get_ref_list', _external=True, repo_key=repo_key, ref_path=ref.name[5:]), #[5:] to cut off the redundant refs/
        "ref": ref.name,
        "object": _linkobj_for_gitobj(repo_key, obj, include_type=True),
    }

@app.route('/repos/<repo_key>/git/commits')
@jsonify
def get_commit_list(repo_key):
    ref_name = request.args.get('ref_name') or None
    start_sha = request.args.get('start_sha') or None
    limit = request.args.get('limit') or 50
    try:
        limit = int(limit)
    except:
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
        start_commit_id = _lookup_ref(repo, ref_name).resolve().oid

    commits = []
    walker = repo.walk(start_commit_id, GIT_SORT_TIME)
    count = 0
    for commit in walker:
        count += 1
        if count > limit:
            break
        commits.append(_convert_commit(repo_key, commit))
    return commits

@app.route('/repos/<repo_key>/git/commits/<sha>')
@jsonify
def get_commit(repo_key, sha):
    repo = _get_repo(repo_key)
    commit = _get_commit(repo, sha)
    return _convert_commit(repo_key, commit)


@app.route('/repos/<repo_key>/git/trees/<sha>')
@jsonify
def get_tree(repo_key, sha):
    repo = _get_repo(repo_key)
    try:
        tree = repo[unicode(sha)]
    except KeyError:
        raise NotFound("tree not found")
    if tree.type != GIT_OBJ_TREE:
        raise NotFound("sha not a tree")
    return _convert_tree(repo_key, tree)

@app.route('/repos/<repo_key>/git/blobs/<sha>')
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

@app.route('/repos/<repo_key>/git/refs')
@app.route('/repos/<repo_key>/git/refs/<path:ref_path>')
@jsonify
def get_ref_list(repo_key, ref_path=None):
    if ref_path is not None:
        ref_path = "refs/" + ref_path
    else:
        ref_path = ""
    repo = _get_repo(repo_key)
    ref_data = [
        _convert_ref(repo_key, reference, repo[reference.oid]) for reference in filter(lambda x: x.type != GIT_REF_SYMBOLIC, [repo.lookup_reference(r) for r in filter(lambda x: x.startswith(ref_path), repo.listall_references())])
    ]
    if len(ref_data) == 1:
        ref_data = ref_data[0]
    return ref_data
    

if __name__ == '__main__':
    app.debug = True
    app.run(host="0.0.0.0")
    
application = app