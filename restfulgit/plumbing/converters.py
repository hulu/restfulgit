# coding=utf-8
from __future__ import absolute_import, unicode_literals, print_function, division

from base64 import b64encode
from datetime import datetime

from flask import url_for
from pygit2 import GIT_OBJ_COMMIT, GIT_OBJ_BLOB, GIT_OBJ_TREE, GIT_OBJ_TAG

from restfulgit.utils.timezones import FixedOffset


GIT_MODE_SUBMODULE = 0o0160000
GIT_OBJ_TYPE_TO_NAME = {
    GIT_OBJ_COMMIT: 'commit',
    GIT_OBJ_TREE: 'tree',
    GIT_OBJ_BLOB: 'blob',
    GIT_OBJ_TAG: 'tag',
}


def _convert_signature(sig):
    return {
        "name": sig.name,
        "email": sig.email,
        "date": datetime.fromtimestamp(sig.time, FixedOffset(sig.offset))
    }


def convert_commit(repo_key, commit, porcelain=False):
    if porcelain:
        def commit_url_for(sha):
            return url_for('porcelain.get_commit', _external=True,
                           repo_key=repo_key, branch_or_tag_or_sha=sha)
    else:
        def commit_url_for(sha):
            return url_for('plumbing.get_commit', _external=True,
                           repo_key=repo_key, sha=sha)

    return {
        "url": url_for('plumbing.get_commit', _external=True,
                       repo_key=repo_key, sha=unicode(commit.id)),
        "sha": unicode(commit.id),
        "author": _convert_signature(commit.author),
        "committer": _convert_signature(commit.committer),
        "message": commit.message.rstrip(),
        "tree": {
            "sha": unicode(commit.tree_id),
            "url": url_for('plumbing.get_tree', _external=True,
                           repo_key=repo_key, sha=unicode(commit.tree_id)),
        },
        "parents": [{
            "sha": unicode(c.id),
            "url": commit_url_for(unicode(c.id)),
        } for c in commit.parents]
    }


def encode_blob_data(data):
    try:
        return 'utf-8', data.decode('utf-8')
    except UnicodeDecodeError:
        return 'base64', b64encode(data)


def convert_blob(repo_key, blob):
    encoding, data = encode_blob_data(blob.data)
    return {
        "url": url_for('plumbing.get_blob', _external=True,
                       repo_key=repo_key, sha=unicode(blob.id)),
        "sha": unicode(blob.id),
        "size": blob.size,
        "encoding": encoding,
        "content": data,
    }


def _tree_entries(repo_key, repo, tree, recursive=False, path=''):
    entry_list = []
    for entry in tree:
        entry_name = unicode(entry.name, 'utf-8')
        if entry.filemode == GIT_MODE_SUBMODULE:
            entry_data = {
                "path": entry_name,
                "sha": unicode(entry.id),
                "type": "submodule",
            }
        else:
            obj = repo[entry.id]
            if obj.type == GIT_OBJ_BLOB:
                entry_data = {
                    "path": '%s%s' % (path, entry_name),
                    "sha": unicode(entry.id),
                    "type": "blob",
                    "size": obj.size,
                    "url": url_for('plumbing.get_blob', _external=True,
                                   repo_key=repo_key, sha=unicode(entry.id)),
                }
            elif obj.type == GIT_OBJ_TREE:
                if recursive:
                    entry_list += _tree_entries(repo_key, repo, obj, True, '%s%s/' % (path, entry_name))
                entry_data = {
                    "path": "%s%s" % (path, entry_name),
                    "sha": unicode(entry.id),
                    "type": "tree",
                    "url": url_for('plumbing.get_tree', _external=True,
                                   repo_key=repo_key, sha=unicode(entry.id))
                }
        entry_data['mode'] = oct(entry.filemode)[1:].zfill(6)  # 6 octal digits without single leading base-indicating 0
        entry_list.append(entry_data)
    return entry_list


def convert_tree(repo_key, repo, tree, recursive=False):
    entry_list = _tree_entries(repo_key, repo, tree, recursive=recursive)
    entry_list.sort(key=lambda entry: entry['path'])
    return {
        "url": url_for('plumbing.get_tree', _external=True,
                       repo_key=repo_key, sha=unicode(tree.id)),
        "sha": unicode(tree.id),
        "tree": entry_list,
    }


def _linkobj_for_gitobj(repo_key, obj, include_type=False):
    data = {}
    data['sha'] = unicode(obj.id)
    obj_type = GIT_OBJ_TYPE_TO_NAME.get(obj.type)
    if obj_type is not None:
        data['url'] = url_for('plumbing.get_' + obj_type, _external=True,
                              repo_key=repo_key, sha=unicode(obj.id))
    if include_type:
        data['type'] = obj_type
    return data


def convert_ref(repo_key, ref, obj):
    return {
        "url": url_for('plumbing.get_refs', _external=True,
                       repo_key=repo_key, ref_path=ref.name[5:]),  # [5:] to cut off the redundant refs/
        "ref": ref.name,
        "object": _linkobj_for_gitobj(repo_key, obj, include_type=True),
    }


def convert_tag(repo_key, repo, tag):
    target_type_name = GIT_OBJ_TYPE_TO_NAME.get(repo[tag.target].type)
    return {
        "url": url_for('plumbing.get_tag', _external=True,
                       repo_key=repo_key, sha=unicode(tag.id)),
        "sha": unicode(tag.id),
        "tag": tag.name,
        "tagger": _convert_signature(tag.tagger),
        "message": tag.message,
        "object": {
            "type": target_type_name,
            "sha": unicode(tag.target),
            "url": url_for('plumbing.get_' + target_type_name, _external=True,
                           repo_key=repo_key, sha=unicode(tag.target)),
        },
    }
