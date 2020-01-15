# coding=utf-8


import os

from flask import current_app, url_for, safe_join
from werkzeug.exceptions import NotFound, BadRequest
from pygit2 import GIT_OBJ_COMMIT, GIT_OBJ_BLOB, GIT_OBJ_TREE, GIT_OBJ_TAG, GIT_REF_SYMBOLIC, GIT_BLAME_TRACK_COPIES_SAME_COMMIT_MOVES, GIT_BLAME_TRACK_COPIES_SAME_COMMIT_COPIES, GIT_SORT_NONE, GitError
from restfulgit.plumbing.converters import GIT_OBJ_TYPE_TO_NAME, encode_blob_data


DEFAULT_GIT_DESCRIPTION = "Unnamed repository; edit this file 'description' to name the repository.\n"
GIT_OBJ_TO_PORCELAIN_NAME = {
    GIT_OBJ_TREE: 'dir',
    GIT_OBJ_BLOB: 'file',
}


def get_repo_names():
    children = (
        (name, safe_join(current_app.config['RESTFULGIT_REPO_BASE_PATH'], name))
        for name in os.listdir(current_app.config['RESTFULGIT_REPO_BASE_PATH'])
    )
    subdirs = [(dir_name, full_path) for dir_name, full_path in children if os.path.isdir(full_path)]
    mirrors = set(name for name, _ in subdirs if name.endswith('.git'))
    working_copies = set(name for name, full_path in subdirs if os.path.isdir(safe_join(full_path, '.git')))
    repositories = mirrors | working_copies
    return repositories


def get_commit_for_refspec(repo, branch_or_tag_or_sha):
    try:
        commit = repo.revparse_single(branch_or_tag_or_sha)
        if commit.type == GIT_OBJ_TAG:
            commit = commit.peel(GIT_OBJ_COMMIT)
        return commit
    except KeyError:
        raise NotFound("no such branch, tag, or commit SHA")


def get_branch(repo, branch_name):
    branch = repo.lookup_branch(branch_name)
    if branch is None:
        raise NotFound("branch not found")
    return branch


def get_object_from_path(repo, tree, path):
    path_segments = path.split("/")

    ctree = tree
    for i, path_seg in enumerate(path_segments):
        if ctree.type != GIT_OBJ_TREE:
            raise NotFound("invalid path; traversal unexpectedly encountered a non-tree")
        if not path_seg and i == len(path_segments) - 1:  # allow trailing slash in paths to directories
            continue
        try:
            ctree = repo[ctree[path_seg].id]
        except KeyError:
            raise NotFound("invalid path; no such object")
    return ctree


def get_repo_description(repo_key):
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


def get_raw_file_content(repo, tree, path):
    git_obj = get_object_from_path(repo, tree, path)
    if git_obj.type != GIT_OBJ_BLOB:
        raise BadRequest("path resolved to non-blob object")
    return git_obj.data


def get_diff(repo, commit, against=None, context_lines=3):
    if against is None:
        if commit.parents:
            against = commit.parents[0]
        else:  # NOTE: RestfulGit extension; GitHub gives a 404 in this case
            diff = commit.tree.diff_to_tree(swap=True, context_lines=context_lines)

    if against is not None:
        diff = repo.diff(against, commit, context_lines=context_lines)
        diff.find_similar()

    return diff


def get_blame(repo, file_path, newest_commit, oldest_refspec=None, min_line=1, max_line=None):  # pylint: disable=R0913
    kwargs = {
        'flags': (GIT_BLAME_TRACK_COPIES_SAME_COMMIT_MOVES | GIT_BLAME_TRACK_COPIES_SAME_COMMIT_COPIES),
        'newest_commit': newest_commit.id,
    }
    if oldest_refspec is not None:
        oldest_commit = get_commit_for_refspec(repo, oldest_refspec)
        kwargs['oldest_commit'] = oldest_commit.id
    if min_line > 1:
        kwargs['min_line'] = min_line
    if max_line is not None:
        kwargs['max_line'] = max_line

    try:
        return repo.blame(file_path, **kwargs)
    except KeyError as no_such_file_err:  # pragma: no cover
        raise NotFound(str(no_such_file_err))
    except ValueError:  # pragma: no cover
        raise BadRequest("path resolved to non-blob object")


def get_authors(repo):
    try:
        target = repo.head.target
    except GitError:
        return ()
    else:
        return (commit.author for commit in repo.walk(target, GIT_SORT_NONE))  # pylint: disable=E1103


# FIX ME: should be in different module?
def get_contents(repo_key, repo, refspec, file_path, obj, _recursing=False):
    # FIX ME: implement symlink and submodule cases
    if not _recursing and obj.type == GIT_OBJ_TREE:
        entries = [
            get_contents(repo_key, repo, refspec, os.path.join(file_path, entry.name), repo[entry.id], _recursing=True)
            for entry in obj
        ]
        entries.sort(key=lambda entry: entry["name"])
        return entries

    contents_url = url_for('porcelain.get_contents', _external=True, repo_key=repo_key, file_path=file_path, ref=refspec)
    git_url = url_for('plumbing.get_' + GIT_OBJ_TYPE_TO_NAME[obj.type], _external=True, repo_key=repo_key, sha=str(obj.id))

    result = {
        "type": GIT_OBJ_TO_PORCELAIN_NAME[obj.type],
        "sha": str(obj.id),
        "name": os.path.basename(file_path),
        "path": file_path,
        "size": (obj.size if obj.type == GIT_OBJ_BLOB else 0),
        "url": contents_url,
        "git_url": git_url,
        "_links": {
            "self": contents_url,
            "git": git_url,
        }
    }
    if not _recursing and obj.type == GIT_OBJ_BLOB:
        encoding, data = encode_blob_data(obj.data)
        result["encoding"] = encoding
        result["content"] = data
    return result


def _get_common_ancestor_or_none(repo, left_oid, right_oid):
    try:
        return repo.merge_base(left_oid, right_oid)
    except KeyError:
        # Couldn't find merge base
        return None


def _get_other_nonsymbolic_refs(repo, main_ref_name):
    for ref_name in repo.listall_references():
        if ref_name == main_ref_name:
            continue
        ref = repo.lookup_reference(ref_name)
        if ref.type == GIT_REF_SYMBOLIC:
            continue
        yield ref


def get_commits_unique_to_branch(repo, branch, sort=GIT_SORT_NONE):
    common_ancestor_oids = set(_get_common_ancestor_or_none(repo, branch.target, ref.target) for ref in _get_other_nonsymbolic_refs(repo, branch.name))
    common_ancestor_oids.discard(None)
    walker = repo.walk(branch.target, sort)
    for ancestor in common_ancestor_oids:
        walker.hide(ancestor)
    return walker
