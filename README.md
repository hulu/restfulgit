REST API for Git data
=======================

Provides a read-only restful interface for accessing data from Git repositories (local to the server).
Modeled off the GitHub Git DB API for compatibility (see http://developer.github.com/v3/git/).

Requires: flask, pygit2 (>= 0.18.1), libgit2 (>= 0.18).
Must modify: REPO_BASE (root path for repositories, note only repositories immediately under this path are currently supported).

api.py is a valid WSGI application.

--

All of these routes return JSON unless otherwise specified.

Commits
----------
Retrieves a list of commit objects:

    GET /repos/:repo_key/git/commits
    
    optional: ?start_sha=:sha
    optional: ?ref_name=:ref_name
    optional: ?limit=:limit (default=50)
    
Retrieves specific commit object:

    GET /repos/:repo_key/git/commits/:sha

Blobs
----------
Retrieves a specific blob object:

    GET /repos/:repo_key/git/blobs/:sha

Trees
----------
Retrieves a specific tree object:

    GET /repos/:repo_key/git/trees/:sha

Refs
----------
Retrieves a list of refs:

    GET /repos/:repo_key/git/refs

Retrieves a specific ref:

    GET /repos/:repo_key/git/refs/:ref_name

Raw Files
----------
Returns the raw file data for the file on the specified branch:

    /repos/:repo_key/raw/:branch_name/:file_path
