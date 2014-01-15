# coding=utf-8
from __future__ import absolute_import, unicode_literals, print_function, division

import tarfile
import zipfile
import os
from datetime import datetime
from tempfile import mkstemp as _make_temp_file_handle
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from flask import current_app, Blueprint, send_file
from pygit2 import GIT_OBJ_BLOB, GIT_OBJ_TREE

from restfulgit.plumbing.retrieval import get_repo, get_tree
from restfulgit.plumbing.converters import GIT_MODE_SUBMODULE
from restfulgit.porcelain.retrieval import get_commit_for_refspec
from restfulgit.utils.json_err_pages import json_error_page, register_general_error_handler
from restfulgit.utils.url_converters import SHAConverter, register_converter
from restfulgit.utils.cors import corsify
from restfulgit.utils import mime_types


# Detect whether we can actually use compression for archive files
try:
    import zlib
except ImportError:
    ZLIB_SUPPORT = False
    TARFILE_WRITE_MODE = 'w'
    ZIP_COMPRESSION_METHOD = zipfile.ZIP_STORED
else:
    del zlib
    ZLIB_SUPPORT = True
    TARFILE_WRITE_MODE = 'w:gz'
    ZIP_COMPRESSION_METHOD = zipfile.ZIP_DEFLATED


ZIP_EXTENSION = '.zip'
TAR_EXTENSION = '.tar'
TGZ_EXTENSION = '.tar.gz'

EPOCH_START = datetime(1970, 1, 1)


archives = Blueprint('archives', __name__)  # pylint: disable=C0103
register_converter(archives, 'sha', SHAConverter)
register_general_error_handler(archives, json_error_page)


def _walk_tree_recursively(repo, tree, blobs_only=False, base_path=''):
    for entry in tree:
        if entry.filemode == GIT_MODE_SUBMODULE:
            continue  # FIX ME: handle submodules & symlinks
        path = base_path + entry.name
        obj = repo[entry.oid]
        if not blobs_only or obj.type == GIT_OBJ_BLOB:
            yield path, entry.filemode, obj

        if obj.type == GIT_OBJ_TREE:
            for subpath, subfilemode, subobj in _walk_tree_recursively(repo, obj, blobs_only, (path + '/')):
                yield subpath, subfilemode, subobj


def _wrapper_dir_name_for(repo_key, commit):
    return "{}-{}".format(repo_key, commit.hex)


def _archive_filename_for(repo_key, refspec, ext):
    return "{}-{}{}".format(repo_key, refspec, ext)


def _make_temp_file(prefix='tmp_restfulgit_', suffix='', text=False):
    handle, filepath = _make_temp_file_handle(prefix=prefix, suffix=suffix, text=text)
    try:
        os.remove(filepath)
    except (OSError, IOError):
        current_app.logger.exception("Encountered error when attempting to delete temporary file.")
    # Our handle is now the only way to access the temp file.
    # The OS will delete the file completely once our handle is closed (at the end of the HTTP request).
    mode = 'w+'
    if not text:
        mode += 'b'
    file_obj = os.fdopen(handle, mode)
    return file_obj


def _send_transient_file_as_attachment(source_filename_or_fp, attachment_filename, mimetype):
    return send_file(
        source_filename_or_fp,
        mimetype=mimetype,
        as_attachment=True,
        attachment_filename=attachment_filename,
        add_etags=False,
        cache_timeout=0,
    )


@archives.route('/repos/<repo_key>/zipball/<branch_or_tag_or_sha>/')
@corsify
def get_zip_file(repo_key, branch_or_tag_or_sha):
    """
    Serves a ZIP file of a working copy of the repo at the given commit.
    Note: This endpoint is relatively slow, and the ZIP file is generated from-scratch on each request (no caching is done).
    """
    repo = get_repo(repo_key)
    commit = get_commit_for_refspec(repo, branch_or_tag_or_sha)
    tree = get_tree(repo, commit.tree.hex)

    wrapper_dir = _wrapper_dir_name_for(repo_key, commit)
    temp_file = _make_temp_file(suffix=ZIP_EXTENSION)
    with zipfile.ZipFile(temp_file, mode='w', compression=ZIP_COMPRESSION_METHOD, allowZip64=True) as zip_file:
        for filepath, _, blob in _walk_tree_recursively(repo, tree, blobs_only=True):
            filepath = os.path.join(wrapper_dir, filepath)
            zip_file.writestr(filepath, blob.data)
    temp_file.seek(0)
    return _send_transient_file_as_attachment(temp_file,
                                              _archive_filename_for(repo_key, refspec=branch_or_tag_or_sha, ext=ZIP_EXTENSION),
                                              mime_types.ZIP)


@archives.route('/repos/<repo_key>/tarball/<branch_or_tag_or_sha>/')
@corsify
def get_tarball(repo_key, branch_or_tag_or_sha):
    """
    Serves a TAR file of a working copy of the repo at the given commit.
    If Python's zlib bindings are available, the TAR file will be gzip-ed.
    The limited permissions information that git stores is honored in the TAR file.
    The commit SHA is included as a PAX header field named "comment".
    Note: This endpoint is relatively slow, and the TAR file is generated from-scratch on each request (no caching is done).
    """
    repo = get_repo(repo_key)
    commit = get_commit_for_refspec(repo, branch_or_tag_or_sha)
    tree = get_tree(repo, commit.tree.hex)

    wrapper_dir = _wrapper_dir_name_for(repo_key, commit)
    extension = (TGZ_EXTENSION if ZLIB_SUPPORT else TAR_EXTENSION)
    timestamp = int((datetime.utcnow() - EPOCH_START).total_seconds())  # FIX ME: use committer/author timestamp?
    temp_file = _make_temp_file(suffix=extension)
    with tarfile.open(fileobj=temp_file, mode=TARFILE_WRITE_MODE, encoding='utf-8') as tar_file:
        tar_file.pax_headers = {u'comment': commit.hex.decode('ascii')}

        for path, filemode, obj in _walk_tree_recursively(repo, tree):
            tar_info = tarfile.TarInfo(os.path.join(wrapper_dir, path))
            tar_info.mtime = timestamp

            if obj.type == GIT_OBJ_BLOB:
                tar_info.size = obj.size

            if obj.type == GIT_OBJ_TREE:
                filemode = 0o755  # git doesn't store meaningful directory perms
            tar_info.mode = filemode

            if obj.type == GIT_OBJ_BLOB:
                tar_info.type = tarfile.REGTYPE
                content = StringIO(obj.data)
            elif obj.type == GIT_OBJ_TREE:
                tar_info.type = tarfile.DIRTYPE
                content = None
            # FIX ME: handle submodules & symlinks

            tar_file.addfile(tar_info, content)
    temp_file.seek(0)
    return _send_transient_file_as_attachment(temp_file,
                                              _archive_filename_for(repo_key, refspec=branch_or_tag_or_sha, ext=extension),
                                              (mime_types.GZIP if ZLIB_SUPPORT else mime_types.TAR))
