RestfulGit: A Restful API for Git data
=======================================
[![Build Status](https://travis-ci.org/kainswor/restfulgit.png?branch=master)](https://travis-ci.org/kainswor/restfulgit)
[![Coverage Status](https://coveralls.io/repos/kainswor/restfulgit/badge.png?branch=master)](https://coveralls.io/r/kainswor/restfulgit?branch=master)
[![Requirements Status](https://requires.io/github/kainswor/restfulgit/requirements.png?branch=master)](https://requires.io/github/kainswor/restfulgit/requirements/?branch=master)

Provides a read-only restful interface for accessing data from Git repositories (local to the server).
Modeled off the GitHub Git DB API for compatibility (see http://developer.github.com/v3/git/).

Requires:
- Python 2.7
- Flask
- pygit2 (= 0.20.0), which itself requires libgit2 (= 0.20.0)

Optional:
- filemagic (= 1.6) (offers improved MIME-type guessing), which itself requires libmagic (= 5.11)

The `restfulgit` package is a valid WSGI application.

While the app can be run with `python -m restfulgit` -- this runs Flask in debug mode and should NOT be used in production.
Instead, the app can be run with any WSGI server, such as gunicorn (`pip install gunicorn; gunicorn restfulgit`)
(Note: If you haven't installed restfulgit into your Python environment, you may need to explicitly set `PYTHONPATH` when running the above commands.)

Configuration
----------------
RestfulGit uses Flask's config system. See `example_config.py` for an example config file.
If the `$RESTFULGIT_CONFIG` environment variable is set, RestfulGit will assume its value is a config filepath and will attempt to load its config from that file.
If the variable is not set or the loading attempt fails, RestfulGit will then attempt to load its config from `/etc/restfulgit.conf.py`.

| Config parameter                     | Default value     | Description                                                                                                                                         |
|--------------------------------------|-------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| RESTFULGIT_REPO_BASE_PATH            | (none)            | Root path for Git repositories. Note: only repositories immediately under this path are currently supported.                                        |
| RESTFULGIT_DEFAULT_COMMIT_LIST_LIMIT | 50                | Number of most recent commits to return by default from the "commits" API endpoint.                                                                 |
| RESTFULGIT_ENABLE_CORS               | False             | Whether to enable [cross-origin resource sharing (CORS)](http://en.wikipedia.org/wiki/Cross-origin_resource_sharing) headers for the API endpoints. |
| RESTFULGIT_CORS_ALLOWED_HEADERS      | `[]` (empty list) | List of HTTP header names (strings) that are allowed be used by the client when making a CORS request.                                              |
| RESTFULGIT_CORS_ALLOW_CREDENTIALS    | False             | Whether HTTP Cookies and HTTP Authentication information should be sent by the client when making a CORS request.                                   |
| RESTFULGIT_CORS_MAX_AGE              | 30 days           | `datetime.timedelta` specifying how long the results of a CORS preflight request can be cached by clients.                                          |
| RESTFULGIT_CORS_ALLOWED_ORIGIN       | `*` (all origins) | Which [origin](http://en.wikipedia.org/wiki/Same-origin_policy#Origin_determination_rules) is allowed to access the API endpoints using CORS.       |

--

All of these routes return JSON unless otherwise specified.

Commits
----------
Retrieves a list of commit objects:

    GET /repos/:repo_key/git/commits/
    
    optional: ?start_sha=:sha
    optional: ?ref_name=:ref_name
    optional: ?limit=:limit (default=50, or as specified by the config)

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
        "url": "http://localhost:5000/repos/restfulgit.git/git/commits/f85df530d8413b0390364b291eb97d1cc5798dee/",
        "tree": {
            "url": "http://localhost:5000/repos/restfulgit.git/git/trees/4c392547aa3d644877f3b22e198a5caac99a69a3/",
            "sha": "4c392547aa3d644877f3b22e198a5caac99a69a3"
        },
        "sha": "f85df530d8413b0390364b291eb97d1cc5798dee",
        "parents": [
            {
                "url": "http://localhost:5000/repos/restfulgit.git/git/commits/7b3f40ff9aba370a59732522420201b744297317/",
                "sha": "7b3f40ff9aba370a59732522420201b744297317"
            }
        ],
        "message": "Renamed main api file, added production recommendation to README"
    },
    ...
]
```

Retrieves specific commit object:

    GET /repos/:repo_key/git/commits/:sha/

Blobs
----------
Retrieves a specific blob object:

    GET /repos/:repo_key/git/blobs/:sha/

```json
{
    "url": "http://localhost:5000/repos/restfulgit.git/git/blobs/0d20b6487c61e7d1bde93acf4a14b7a89083a16d/",
    "sha": "0d20b6487c61e7d1bde93acf4a14b7a89083a16d",
    "encoding": "utf-8",
    "data": "*.pyc ",
    "size": 6
}
```

Trees
----------
Retrieves a specific tree object:

    GET /repos/:repo_key/git/trees/:sha/

    optional: ?recursive=:zero_or_one (default=0, non-recursive)

```json
{
    "url": "http://localhost:5000/repos/restfulgit.git/git/trees/4c392547aa3d644877f3b22e198a5caac99a69a3/",
    "sha": "4c392547aa3d644877f3b22e198a5caac99a69a3",
    "tree": [
        {
            "url": "http://localhost:5000/repos/restfulgit.git/git/blobs/0d20b6487c61e7d1bde93acf4a14b7a89083a16d/",
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

    GET /repos/:repo_key/git/tags/:sha/

```json
{
    "url": "http://localhost:5000/repos/restfulgit.git/git/tags/89571737c474fae7ea4c092b5ed94e4eccb11b2a/",
    "object": {
        "url": "http://localhost:5000/repos/restfulgit.git/git/commits/b6b05bb0f230b591d82fcc07d169b7453e04cf89/",
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

    GET /repos/:repo_key/git/refs/

```json
[
    {
        "url": "http://localhost:5000/repos/restfulgit.git/git/refs/heads/master",
        "object": {
            "url": "http://localhost:5000/repos/restfulgit.git/git/commits/f85df530d8413b0390364b291eb97d1cc5798dee/",
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
Returns the raw file data for the file on the specified branch, tag, or commit SHA:

    GET /repos/:repo_key/blob/:refspec/:file_path

List Repositories
----------
Retrieves a list of the names of all the repos:

    GET /repos/

```json
{"repos": ["restfulgit.git"]}
```

Repository Descriptions
-----------------
Retrieve the description (if any) of the repo, as plain text:

    GET /repos/:repo_key/description/

```
REST API for Git data
```

(If there is no description, the result will be blank.)
