# coding=utf-8
from __future__ import absolute_import, unicode_literals, print_function, division

from flask import current_app, safe_join
from werkzeug.exceptions import NotFound
from pygit2 import Repository, GIT_OBJ_COMMIT, GIT_OBJ_BLOB, GIT_OBJ_TREE, GIT_OBJ_TAG


def get_repo(repo_key):
    path = safe_join(current_app.config['RESTFULGIT_REPO_BASE_PATH'], repo_key)
    try:
        return Repository(path)
    except KeyError:
        raise NotFound("repository not found")


def get_commit(repo, sha):
    try:
        commit = repo[unicode(sha)]
    except KeyError:
        raise NotFound("commit not found")
    if commit.type != GIT_OBJ_COMMIT:
        raise NotFound("object not a commit")
    return commit


def get_tree(repo, sha):
    try:
        obj = repo[unicode(sha)]
    except KeyError:
        raise NotFound("tree not found")
    if obj.type == GIT_OBJ_TREE:
        return obj
    elif obj.type == GIT_OBJ_COMMIT:
        return obj.tree
    else:
        raise NotFound("object not a tree or a commit")


def get_blob(repo, sha):
    try:
        blob = repo[unicode(sha)]
    except KeyError:
        raise NotFound("blob not found")
    if blob.type != GIT_OBJ_BLOB:
        raise NotFound("sha not a blob")
    return blob


def get_tag(repo, sha):
    try:
        tag = repo[unicode(sha)]
    except KeyError:
        raise NotFound("tag not found")
    if tag.type != GIT_OBJ_TAG:
        raise NotFound("object not a tag")
    return tag


def lookup_ref(repo, ref_name):
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
