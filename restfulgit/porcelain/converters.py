# coding=utf-8
from __future__ import absolute_import, unicode_literals, print_function, division

import re

from flask import url_for

from restfulgit.plumbing.retrieval import get_commit
from restfulgit.plumbing.converters import convert_commit as _plumbing_convert_commit
from restfulgit.porcelain.retrieval import get_repo_description, get_diff


GIT_STATUS_TO_NAME = {
    'M': 'modified',
    'A': 'added',
    'R': 'renamed',
    'D': 'removed',
}
SPLIT_PATCH_TXT_RE = re.compile(r'^\+\+\+\ b\/(.*?)\n(@@.*?)(?=\n^diff|\n\Z)', re.M | re.S)


def convert_repo(repo_key):
    description = get_repo_description(repo_key)
    return {
        "name": repo_key,
        "full_name": repo_key,
        "description": description,
        "url": url_for('porcelain.get_repo_info', _external=True, repo_key=repo_key),
        "branches_url": (url_for('porcelain.get_branches', _external=True, repo_key=repo_key).rstrip('/') + '{/branch}'),
        "blobs_url": (url_for('plumbing.get_blob', _external=True, repo_key=repo_key, sha='').rstrip('/') + '{/sha}'),
        "commits_url": (url_for('porcelain.get_commit', _external=True, repo_key=repo_key, branch_or_tag_or_sha='').rstrip('/') + '{/sha}'),
        "git_commits_url": (url_for('plumbing.get_commit', _external=True, repo_key=repo_key, sha='').rstrip('/') + '{/sha}'),
        "git_refs_url": (url_for('plumbing.get_refs', _external=True, repo_key=repo_key).rstrip('/') + '{/sha}'),
        "git_tags_url": (url_for('plumbing.get_tag', _external=True, repo_key=repo_key, sha='').rstrip('/') + '{/sha}'),
        "tags_url": url_for('porcelain.get_tags', _external=True, repo_key=repo_key),
        "trees_url": (url_for('plumbing.get_tree', _external=True, repo_key=repo_key, sha='').rstrip('/') + '{/sha}'),
    }


def convert_branch(repo_key, repo, branch):
    url = url_for('porcelain.get_branch', _external=True, repo_key=repo_key, branch_name=branch.branch_name)
    return {
        "name": branch.branch_name,
        "commit": convert_commit(repo_key, repo, branch.get_object()),
        "url": url,
        "_links": {
            # For some reason GitHub API for branch does the self-link like this
            # instead of with "url" as everywhere else.
            "self": url,
        }
    }


def _filename_to_patch_from(diff):
    matches = re.findall(SPLIT_PATCH_TXT_RE, diff.patch)
    return dict(m for m in matches)


def _convert_patch(repo_key, commit, patch, filename_to_patch):
    deleted = patch.status == 'D'
    commit_sha = unicode(commit.id if not deleted else commit.parent_ids[0])
    result = {
        "sha": patch.new_oid if not deleted else patch.old_oid,
        "status": GIT_STATUS_TO_NAME[patch.status],
        "filename": patch.new_file_path,
        "additions": patch.additions,
        "deletions": patch.deletions,
        "changes": patch.additions + patch.deletions,
        "raw_url": url_for('porcelain.get_raw',
                           _external=True,
                           repo_key=repo_key,
                           branch_or_tag_or_sha=commit_sha,
                           file_path=patch.new_file_path),
        "contents_url": url_for('porcelain.get_contents',
                                _external=True,
                                repo_key=repo_key,
                                file_path=patch.new_file_path,
                                ref=commit_sha),
    }
    if patch.new_file_path in filename_to_patch:
        result['patch'] = filename_to_patch[patch.new_file_path]
    return result


def convert_commit(repo_key, repo, commit, include_diff=False):
    plain_commit_json = _plumbing_convert_commit(repo_key, commit, porcelain=True)
    result = {
        "commit": plain_commit_json,
        "sha": plain_commit_json['sha'],
        "author": plain_commit_json['author'],
        "committer": plain_commit_json['committer'],
        "url": url_for('porcelain.get_commit', _external=True,
                       repo_key=repo_key, branch_or_tag_or_sha=unicode(commit.id)),
        "parents": [{
            "sha": unicode(c.id),
            "url": url_for('porcelain.get_commit', _external=True,
                           repo_key=repo_key, branch_or_tag_or_sha=unicode(c.id))
        } for c in commit.parents],
    }
    if include_diff:
        diff = get_diff(repo, commit)
        patches = list(diff)
        filename_to_patch = _filename_to_patch_from(diff)
        patches_additions = sum(patch.additions for patch in patches)
        patches_deletions = sum(patch.deletions for patch in patches)
        result.update({
            "stats": {
                "additions": patches_additions,
                "deletions": patches_deletions,
                "total": patches_additions + patches_deletions,
            },
            "files": [_convert_patch(repo_key, commit, patch, filename_to_patch) for patch in patches],
        })
    return result


def convert_blame(repo_key, repo, blame, raw_lines, start_line):
    annotated_lines = []
    commit_shas = set()
    for line_num, line in enumerate(raw_lines, start=start_line):
        hunk = blame.for_line(line_num)
        commit_sha = hunk.final_commit_id
        commit_shas.add(commit_sha)
        annotated_lines.append({
            'commit': commit_sha,
            'origPath': hunk.orig_path,
            'lineNum': line_num,
            'line': line,
        })

    return {
        'lines': annotated_lines,
        'commits': {
            commit_sha: _plumbing_convert_commit(repo_key, get_commit(repo, commit_sha))
            for commit_sha in commit_shas
        }
    }
