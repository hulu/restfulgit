RestfulGit: A Restful API for Git data
=======================================
[![Build Status](https://travis-ci.org/hulu/restfulgit.png?branch=master)](https://travis-ci.org/hulu/restfulgit)

Provides a read-only restful interface for accessing data from Git repositories (local to the server).
Modeled off the GitHub Git DB API for compatibility (see http://developer.github.com/v3/git/).

Requires: Python 2.7, Flask, pygit2 (= 0.19.0), libgit2 (= 0.19.0)

Must modify: `config.conf` : `repo_base_path` (root path for repositories; note: only repositories immediately under this path are currently supported).

`gitapi.py` is a valid WSGI application.

While the app can be run with `python gitapi.py` -- this runs Flask in debug mode and should NOT be used in production.
Instead the app can be run with any WSGI server, such as gunicorn (`pip install gunicorn; gunicorn gitapi`)

--

All of these routes return JSON unless otherwise specified.

Commits
----------
Retrieves a list of commit objects:

    GET /repos/:repo_key/git/commits
    
    optional: ?start_sha=:sha
    optional: ?ref_name=:ref_name
    optional: ?limit=:limit (default=50)

```json
[
    {
        "committer": {
            "date": "2013-05-20T16:11:30-07:00",
            "name": "Rajiv Makhijani",
            "email": "rajiv@hulu.com"
        },
        "author": {
            "date": "2013-05-20T16:11:30-07:00",
            "name": "Rajiv Makhijani",
            "email": "rajiv@hulu.com"
        },
        "url": "http://localhost:5000/repos/restfulgit.git/git/commits/f85df530d8413b0390364b291eb97d1cc5798dee",
        "tree": {
            "url": "http://localhost:5000/repos/restfulgit.git/git/trees/4c392547aa3d644877f3b22e198a5caac99a69a3",
            "sha": "4c392547aa3d644877f3b22e198a5caac99a69a3"
        },
        "sha": "f85df530d8413b0390364b291eb97d1cc5798dee",
        "parents": [
            {
                "url": "http://localhost:5000/repos/restfulgit.git/git/commits/7b3f40ff9aba370a59732522420201b744297317",
                "sha": "7b3f40ff9aba370a59732522420201b744297317"
            }
        ],
        "message": "Renamed main api file, added production recommendation to README"
    },
    ...
]
```

Retrieves specific commit object:

    GET /repos/:repo_key/git/commits/:sha

Blobs
----------
Retrieves a specific blob object:

    GET /repos/:repo_key/git/blobs/:sha

```json
{
    "url": "http://localhost:5000/repos/restfulgit.git/git/blobs/0d20b6487c61e7d1bde93acf4a14b7a89083a16d",
    "sha": "0d20b6487c61e7d1bde93acf4a14b7a89083a16d",
    "encoding": "utf-8",
    "data": "*.pyc ",
    "size": 6
}
```

Trees
----------
Retrieves a specific tree object:

    GET /repos/:repo_key/git/trees/:sha

```json
{
    "url": "http://localhost:5000/repos/restfulgit.git/git/trees/4c392547aa3d644877f3b22e198a5caac99a69a3",
    "sha": "4c392547aa3d644877f3b22e198a5caac99a69a3",
    "tree": [
        {
            "url": "http://localhost:5000/repos/restfulgit.git/git/blobs/0d20b6487c61e7d1bde93acf4a14b7a89083a16d",
            "sha": "0d20b6487c61e7d1bde93acf4a14b7a89083a16d",
            "mode": "0100644",
            "path": ".gitignore",
            "type": "blob",
            "size": 6
        },
        ...
    ]
}
```

Tags
----------
Retrieves a specific tag object:

    GET /repos/:repo_key/git/tags/:sha

```json
{
    "url": "http://localhost:5000/repos/restfulgit.git/git/tags/89571737c474fae7ea4c092b5ed94e4eccb11b2a",
    "object": {
        "url": "http://localhost:5000/repos/restfulgit.git/git/commits/b6b05bb0f230b591d82fcc07d169b7453e04cf89",
        "sha": "b6b05bb0f230b591d82fcc07d169b7453e04cf89",
        "type": "commit"
    },
    "sha": "89571737c474fae7ea4c092b5ed94e4eccb11b2a",
    "tag": "v0.1",
    "tagger": {
        "date": "2013-09-12T21:00:28-07:00",
        "name": "Rajiv Makhijani",
        "email": "rajiv@hulu.com"
    },
    "message": "this is our first release"
}
```

Refs
----------
Retrieves a list of refs:

    GET /repos/:repo_key/git/refs

```json
[
    {
        "url": "http://localhost:5000/repos/restfulgit.git/git/refs/heads/master",
        "object": {
            "url": "http://localhost:5000/repos/restfulgit.git/git/commits/f85df530d8413b0390364b291eb97d1cc5798dee",
            "sha": "f85df530d8413b0390364b291eb97d1cc5798dee",
            "type": "commit"
        },
        "ref": "refs/heads/master"
    }
    ...
]
```

Retrieves a specific ref:

    GET /repos/:repo_key/git/refs/:ref_name

Raw Files
----------
Returns the raw file data for the file on the specified branch:

    /repos/:repo_key/raw/:branch_name/:file_path

Repository Descriptions
-----------------
Retrieve the description (if any) of the repo, as plain text:

    GET /repos/:repo_key/description

```
REST API for Git data
```

(If there is no description, the result will be blank.)
