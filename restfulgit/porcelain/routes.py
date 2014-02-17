# coding=utf-8
from __future__ import absolute_import, unicode_literals, print_function, division

import os
from itertools import ifilter
from collections import defaultdict

from flask import request, Response, Blueprint, url_for
from werkzeug.exceptions import NotFound, BadRequest

from restfulgit.plumbing.retrieval import get_repo, lookup_ref, get_tree
from restfulgit.plumbing.converters import convert_tag
from restfulgit.porcelain.retrieval import get_repo_names, get_commit_for_refspec, get_branch as _get_branch, get_object_from_path, get_raw_file_content, get_contents as _get_contents, get_diff as _get_diff, get_blame as _get_blame, get_authors
from restfulgit.porcelain.converters import convert_repo, convert_branch, convert_commit, convert_blame
from restfulgit.utils.json import jsonify
from restfulgit.utils.cors import corsify
from restfulgit.utils.json_err_pages import json_error_page, register_general_error_handler
from restfulgit.utils.url_converters import SHAConverter, register_converter
from restfulgit.utils import mime_types


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


porcelain = Blueprint('porcelain', __name__)  # pylint: disable=C0103
register_converter(porcelain, 'sha', SHAConverter)
register_general_error_handler(porcelain, json_error_page)


@porcelain.route('/repos/')
@corsify
@jsonify
def get_repo_list():
    return [convert_repo(repo_key) for repo_key in sorted(get_repo_names())]


@porcelain.route('/repos/<repo_key>/')
@corsify
@jsonify
def get_repo_info(repo_key):
    get_repo(repo_key)  # check repo_key validity
    return convert_repo(repo_key)


@porcelain.route('/repos/<repo_key>/branches/')
@corsify
@jsonify
def get_branches(repo_key):
    repo = get_repo(repo_key)
    branches = (repo.lookup_branch(branch_name) for branch_name in repo.listall_branches())
    return [
        {
            "name": branch.branch_name,
            "commit": {
                "sha": branch.target.hex,
                "url": url_for('porcelain.get_commit', _external=True,
                               repo_key=repo_key, branch_or_tag_or_sha=branch.target.hex),
            },
        }
        for branch in branches
    ]


@porcelain.route('/repos/<repo_key>/branches/<branch_name>/')
@corsify
@jsonify
def get_branch(repo_key, branch_name):
    repo = get_repo(repo_key)
    branch = _get_branch(repo, branch_name)
    return convert_branch(repo_key, repo, branch)


TAG_REF_PREFIX = "refs/tags/"


@porcelain.route('/repos/<repo_key>/tags/')
@corsify
@jsonify
def get_tags(repo_key):
    repo = get_repo(repo_key)
    ref_names = ifilter(lambda ref_name: ref_name.startswith(TAG_REF_PREFIX), repo.listall_references())
    tags = (repo.lookup_reference(ref_name) for ref_name in ref_names)
    return [
        {
            "name": tag.shorthand,
            "commit": {
                "sha": tag.get_object().hex,
                "url": url_for('porcelain.get_commit', _external=True,
                               repo_key=repo_key, branch_or_tag_or_sha=tag.get_object().hex),
            },
            "url": url_for('porcelain.get_tag', _external=True,  # NOTE: This is RestfulGit extension
                           repo_key=repo_key, tag_name=tag.shorthand),
        }
        for tag in tags
    ]


@porcelain.route('/repos/<repo_key>/tags/<tag_name>/')
@corsify
@jsonify
def get_tag(repo_key, tag_name):  # NOTE: This endpoint is a RestfulGit extension
    repo = get_repo(repo_key)
    tag = lookup_ref(repo, TAG_REF_PREFIX + tag_name)
    if tag is None:
        raise NotFound("tag not found")
    result = {
        "name": tag.shorthand,
        "commit": convert_commit(repo_key, repo, tag.get_object()),
        "url": url_for('porcelain.get_tag', _external=True,
                       repo_key=repo_key, tag_name=tag.shorthand),
    }
    # simple tag
    if tag.target != tag.get_object().oid:
        tag_obj = repo[tag.target]
        result['tag'] = convert_tag(repo_key, repo, tag_obj)
    return result


@porcelain.route('/repos/<repo_key>/commits/<branch_or_tag_or_sha>/')
@corsify
@jsonify
def get_commit(repo_key, branch_or_tag_or_sha):
    repo = get_repo(repo_key)
    commit = get_commit_for_refspec(repo, branch_or_tag_or_sha)
    return convert_commit(repo_key, repo, commit, include_diff=True)


@porcelain.route('/repos/<repo_key>/contents/')
@porcelain.route('/repos/<repo_key>/contents/<path:file_path>')
@corsify
@jsonify
def get_contents(repo_key, file_path=''):
    repo = get_repo(repo_key)
    refspec = request.args.get('ref', 'master')
    commit = get_commit_for_refspec(repo, refspec)
    tree = get_tree(repo, commit.tree.hex)
    obj = get_object_from_path(repo, tree, file_path)
    return _get_contents(repo_key, repo, refspec, file_path, obj)


@porcelain.route('/repos/<repo_key>/raw/<branch_or_tag_or_sha>/<path:file_path>')
@corsify
def get_raw(repo_key, branch_or_tag_or_sha, file_path):
    repo = get_repo(repo_key)
    commit = get_commit_for_refspec(repo, branch_or_tag_or_sha)
    tree = get_tree(repo, commit.tree.hex)
    data = get_raw_file_content(repo, tree, file_path)
    mime_type = guess_mime_type(os.path.basename(file_path), data)
    if mime_type is None:
        mime_type = mime_types.OCTET_STREAM
    return Response(data, mimetype=mime_type)


@porcelain.route('/repos/<repo_key>/commit/<branch_or_tag_or_sha>.diff')
@corsify
def get_diff(repo_key, branch_or_tag_or_sha=None):
    repo = get_repo(repo_key)
    commit = get_commit_for_refspec(repo, branch_or_tag_or_sha)
    diff = _get_diff(repo, commit)
    return Response(diff.patch, mimetype=mime_types.DIFF)


@porcelain.route('/repos/<repo_key>/diff/<branch_or_tag_or_sha1>/<branch_or_tag_or_sha2>')
@corsify
def get_diffs(repo_key, branch_or_tag_or_sha1=None, branch_or_tag_or_sha2=None):
    context_lines = request.args.get('context_lines') or 3
    try:
        context_lines = int(context_lines)
    except ValueError:
        raise BadRequest("invalid context_lines")
    if context_lines < 0:
        raise BadRequest("invalid context_lines")

    repo = get_repo(repo_key)
    commit1 = get_commit_for_refspec(repo, branch_or_tag_or_sha1)
    commit2 = get_commit_for_refspec(repo, branch_or_tag_or_sha2)
    diff = _get_diff(repo, commit1, commit2, context_lines)
    return Response(diff.patch, mimetype=mime_types.DIFF)


@porcelain.route('/repos/<repo_key>/blame/<branch_or_tag_or_sha>/<path:file_path>')  # NOTE: This endpoint is a RestfulGit extension
@corsify
@jsonify
def get_blame(repo_key, branch_or_tag_or_sha, file_path):
    min_line = request.args.get('firstLine')
    if min_line is None:
        min_line = 1
    try:
        min_line = int(min_line)
    except ValueError:
        raise BadRequest("firstLine was not a valid integer")
    if min_line < 1:
        raise BadRequest("firstLine must be positive")

    max_line = request.args.get('lastLine')
    if max_line is not None:
        try:
            max_line = int(max_line)
        except ValueError:
            raise BadRequest("lastLine was not a valid integer")
        if max_line < 1:
            raise BadRequest("lastLine must be positive")

        if min_line > max_line:
            raise BadRequest("firstLine cannot be greater than lastLine")

    repo = get_repo(repo_key)
    newest_commit = get_commit_for_refspec(repo, branch_or_tag_or_sha)
    tree = get_tree(repo, newest_commit.tree.hex)

    raw_lines = get_raw_file_content(repo, tree, file_path).splitlines()
    if min_line > len(raw_lines):
        raise BadRequest("firstLine out of bounds")
    if max_line is not None and max_line > len(raw_lines):
        raise BadRequest("lastLine out of bounds")
    raw_lines = raw_lines[(min_line - 1):max_line]

    blame = _get_blame(
        repo,
        file_path,
        newest_commit,
        oldest_refspec=request.args.get('oldest'),
        min_line=min_line,
        max_line=max_line,
    )

    return convert_blame(repo_key, repo, blame, raw_lines, min_line)


@porcelain.route('/repos/<repo_key>/contributors/')
@corsify
@jsonify
def get_contributors(repo_key):
    repo = get_repo(repo_key)
    authors = get_authors(repo)
    email_to_name = {}
    commit_counts = defaultdict(int)
    for author in authors:
        email = author.email
        email_to_name.setdefault(email, author.name)
        commit_counts[email] += 1
    leaderboard = commit_counts.items()
    leaderboard.sort(key=(lambda pair: pair[1]), reverse=True)
    return [
        {
            "email": email,  # NOTE: This is RestfulGit extension
            "name": email_to_name[email],
            "contributions": commit_count,
        }
        for email, commit_count in leaderboard
    ]
