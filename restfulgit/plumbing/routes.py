# coding=utf-8


from itertools import islice

from flask import current_app, request, Blueprint
from werkzeug.exceptions import NotFound, BadRequest
from pygit2 import GIT_REF_SYMBOLIC, GIT_SORT_TIME

from restfulgit.plumbing.retrieval import get_repo, get_commit as _get_commit, get_blob as _get_blob, get_tree as _get_tree, lookup_ref, get_tag as _get_tag
from restfulgit.plumbing.converters import convert_commit, convert_blob, convert_tree, convert_ref, convert_tag
from restfulgit.utils.json import jsonify
from restfulgit.utils.cors import corsify
from restfulgit.utils.json_err_pages import json_error_page, register_general_error_handler
from restfulgit.utils.url_converters import SHAConverter, register_converter


plumbing = Blueprint('plumbing', __name__)  # pylint: disable=C0103
register_converter(plumbing, 'sha', SHAConverter)
register_general_error_handler(plumbing, json_error_page)


@plumbing.route('/repos/<repo_key>/git/commits/')
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

    repo = get_repo(repo_key)

    start_commit_id = None
    if start_sha is not None:
        start_commit_id = start_sha
    else:
        if ref_name is None:
            ref_name = "HEAD"
        ref = lookup_ref(repo, ref_name)
        if ref is None:
            raise NotFound("reference not found")
        start_ref = lookup_ref(repo, ref_name)
        try:
            start_commit_id = start_ref.resolve().target
        except KeyError:
            if ref_name == "HEAD":
                return []
            else:
                raise NotFound("reference not found")

    try:
        walker = repo.walk(start_commit_id, GIT_SORT_TIME)
    except ValueError:
        raise BadRequest("invalid start_sha")
    except KeyError:
        raise NotFound("commit not found")

    commits = [convert_commit(repo_key, commit) for commit in islice(walker, limit)]
    return commits


@plumbing.route('/repos/<repo_key>/git/commits/<sha:sha>/')
@corsify
@jsonify
def get_commit(repo_key, sha):
    repo = get_repo(repo_key)
    commit = _get_commit(repo, sha)
    return convert_commit(repo_key, commit)


@plumbing.route('/repos/<repo_key>/git/commits/<sha:left_sha>/merge-base/<sha:right_sha>/')
@corsify
@jsonify
def get_merge_base_for_commits(repo_key, left_sha, right_sha):  # NOTE: RestfulGit extension
    repo = get_repo(repo_key)
    left_commit = _get_commit(repo, left_sha)
    right_commit = _get_commit(repo, right_sha)
    try:
        merge_base_oid = repo.merge_base(left_commit.id, right_commit.id)
        merge_base_commit = repo[merge_base_oid]
    except TypeError:
        return None
    else:
        return convert_commit(repo_key, merge_base_commit)


@plumbing.route('/repos/<repo_key>/git/trees/<sha:sha>/')
@corsify
@jsonify
def get_tree(repo_key, sha):
    recursive = request.args.get('recursive') == '1'
    repo = get_repo(repo_key)
    tree = _get_tree(repo, sha)
    return convert_tree(repo_key, repo, tree, recursive)


@plumbing.route('/repos/<repo_key>/git/blobs/<sha:sha>/')
@corsify
@jsonify
def get_blob(repo_key, sha):
    repo = get_repo(repo_key)
    blob = _get_blob(repo, sha)
    return convert_blob(repo_key, blob)


@plumbing.route('/repos/<repo_key>/git/tags/<sha:sha>/')
@corsify
@jsonify
def get_tag(repo_key, sha):
    repo = get_repo(repo_key)
    tag = _get_tag(repo, sha)
    return convert_tag(repo_key, repo, tag)


@plumbing.route('/repos/<repo_key>/git/refs/')
@plumbing.route('/repos/<repo_key>/git/refs/<path:ref_path>')
@corsify
@jsonify
def get_refs(repo_key, ref_path=None):
    if ref_path is not None:
        ref_path = "refs/" + ref_path
    else:
        ref_path = ""
    repo = get_repo(repo_key)
    ref_names = filter(lambda x: x.startswith(ref_path), repo.listall_references())
    references = (repo.lookup_reference(ref_name) for ref_name in ref_names)
    nonsymbolic_refs = filter(lambda x: x.type != GIT_REF_SYMBOLIC, references)
    ref_data = [
        convert_ref(repo_key, reference, repo[reference.target])
        for reference in nonsymbolic_refs
    ]
    if len(ref_data) == 1 and ref_data[0]['ref'] == ref_path:
        # exact match
        ref_data = ref_data[0]
    return ref_data
