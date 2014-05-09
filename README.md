RestfulGit: A Restful API for Git data
=======================================
[![PyPI version](https://badge.fury.io/py/restfulgit.png)](http://badge.fury.io/py/restfulgit)
[![Build Status](https://travis-ci.org/hulu/restfulgit.png?branch=master)](https://travis-ci.org/hulu/restfulgit)
[![Coverage Status](https://coveralls.io/repos/hulu/restfulgit/badge.png?branch=master)](https://coveralls.io/r/hulu/restfulgit?branch=master)
[![Requirements Status](https://requires.io/github/hulu/restfulgit/requirements.png?branch=master)](https://requires.io/github/hulu/restfulgit/requirements/?branch=master)

Provides a read-only restful interface for accessing data from Git repositories (local to the server).
Modeled off the GitHub API for compatibility (see http://developer.github.com/v3/).

Requires:
- Python 2.7
- Flask
- pygit2 (= 0.20.3), which itself requires libgit2 (= 0.20.0)

Optional:
- filemagic (= 1.6) (offers improved MIME-type guessing), which itself requires libmagic (= 5.11)

The `restfulgit` package is a valid WSGI application.

While the app can be run with `python -m restfulgit.app` -- this runs Flask in debug mode and should NOT be used in production.
Instead, the app can be run with any WSGI server, such as gunicorn (`pip install gunicorn; gunicorn restfulgit.app`)
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
Retrieves a list of commit objects (in plumbing format):

    GET /repos/:repo_key/git/commits/
    
    optional: ?start_sha=:sha
    optional: ?ref_name=:ref_name
    optional: ?limit=:limit (default=50, or as specified by the config)

```json
[
    {
        "sha": "f85df530d8413b0390364b291eb97d1cc5798dee",
        "url": "http://localhost:5000/repos/restfulgit/git/commits/f85df530d8413b0390364b291eb97d1cc5798dee/",
        "author": {
            "date": "2013-05-20T23:11:30Z",
            "name": "Rajiv Makhijani",
            "email": "rajiv@hulu.com"
        },
        "committer": {
            "date": "2013-05-20T23:11:30Z",
            "name": "Rajiv Makhijani",
            "email": "rajiv@hulu.com"
        },
        "tree": {
            "url": "http://localhost:5000/repos/restfulgit/git/trees/4c392547aa3d644877f3b22e198a5caac99a69a3/",
            "sha": "4c392547aa3d644877f3b22e198a5caac99a69a3"
        },
        "parents": [
            {
                "url": "http://localhost:5000/repos/restfulgit/git/commits/7b3f40ff9aba370a59732522420201b744297317/",
                "sha": "7b3f40ff9aba370a59732522420201b744297317"
            }
        ],
        "message": "Renamed main api file, added production recommendation to README"
    },
    ...
]
```

Retrieves a specific commit object (plumbing format) given its SHA:

    GET /repos/:repo_key/git/commits/:sha/

Retrieves a specific commit object (porcelain format) given a branch name, tag name, or commit SHA:

    GET /repos/:repo_key/commits/:refspec/

```json
{
    "sha": "07b9bf1540305153ceeb4519a50b588c35a35464",
    "url": "http://localhost:5000/repos/restfulgit/commits/07b9bf1540305153ceeb4519a50b588c35a35464/",
    "files": [
        {
            "filename": "api.py",
            "status": "added",
            "sha": "ae9d90706c632c26023ce599ac96cb152673da7c",
            "raw_url": "http://localhost:5000/repos/restfulgit/raw/07b9bf1540305153ceeb4519a50b588c35a35464/api.py",
            "contents_url": "http://localhost:5000/repos/restfulgit/contents/api.py?ref=07b9bf1540305153ceeb4519a50b588c35a35464",
            "changes": 179,
            "additions": 179,
            "deletions": 0,
            "patch": ...,
        }
    ],
    "stats": {
        "additions": 179,
        "deletions": 0,
        "total": 179
    },
    "author": {
        "date": "2013-02-24T13:25:46Z",
        "name": "Rajiv Makhijani",
        "email": "rajiv@hulu.com"
    },
    "committer": {
        "date": "2013-02-24T13:25:46Z",
        "name": "Rajiv Makhijani",
        "email": "rajiv@hulu.com"
    },
    "parents": [],
    "commit": {
        "committer": {
            "date": "2013-02-24T13:25:46Z",
            "name": "Rajiv Makhijani",
            "email": "rajiv@hulu.com"
        },
        "author": {
            "date": "2013-02-24T13:25:46Z",
            "name": "Rajiv Makhijani",
            "email": "rajiv@hulu.com"
        },
        "url": "http://localhost:5000/repos/restfulgit/git/commits/07b9bf1540305153ceeb4519a50b588c35a35464/",
        "tree": {
            "url": "http://localhost:5000/repos/restfulgit/git/trees/6ca22167185c31554aa6157306e68dfd612d6345/",
            "sha": "6ca22167185c31554aa6157306e68dfd612d6345"
        },
        "sha": "07b9bf1540305153ceeb4519a50b588c35a35464",
        "parents": [],
        "message": "Initial support for read-only REST api for Git plumbing"
    }
}
```

Retrieves a diff of the changes in a given commit (specified by branch name, tag name, or commit SHA):

    GET /repos/:repo_key/commit/:refspec.diff

```
Content-Type: text/x-diff; charset=utf-8

diff --git a/api.py b/api.py
new file mode 100644
index 0000000..ae9d907
--- /dev/null
+++ b/api.py
@@ -0,0 +1,179 @@
+from flask import Flask, url_for
...
```

Branches
----------
Retrieves a list of branches:

    GET /repos/:repo_key/branches/

```json
[
    {
        "name": "master",
        "commit": {
            "url": "http://localhost:5000/repos/restfulgit/commits/7ad9ae851a4491ab55042bccbab24fc8d740aaea/",
            "sha": "7ad9ae851a4491ab55042bccbab24fc8d740aaea"
        }
    },
    ...
]
```

Retrieves a specific branch object:

    GET /repos/:repo_key/branches/:branch_name/

```json

{
    "name": "master",
    "url": "http://localhost:5000/repos/restfulgit/branches/master/",
    "commit": {
        "sha": "dc745192fba83adc48361c36f73d0c7b6e060ed3",
        "url": "http://localhost:5000/repos/restfulgit/commits/dc745192fba83adc48361c36f73d0c7b6e060ed3/",
        "committer": {
            "date": "2014-05-09T18:38:19Z",
            "name": "Chris Rebert",
            "email": "chris.rebert@hulu.com"
        },
        "author": {
            "date": "2014-05-09T18:38:19Z",
            "name": "Chris Rebert",
            "email": "chris.rebert@hulu.com"
        },
        "parents": [
            {
                "sha": "6c1626a0d07e4bcfdbee4a11c898199a6f7d07b6",
                "url": "http://localhost:5000/repos/restfulgit/commits/6c1626a0d07e4bcfdbee4a11c898199a6f7d07b6/"
            }
        ],
        "commit": {
            "sha": "dc745192fba83adc48361c36f73d0c7b6e060ed3",
            "url": "http://localhost:5000/repos/restfulgit/git/commits/dc745192fba83adc48361c36f73d0c7b6e060ed3/",
            "committer": {
                "date": "2014-05-09T18:38:19Z",
                "name": "Chris Rebert",
                "email": "chris.rebert@hulu.com"
            },
            "author": {
                "date": "2014-05-09T18:38:19Z",
                "name": "Chris Rebert",
                "email": "chris.rebert@hulu.com"
            },
            "tree": {
                "url": "http://localhost:5000/repos/restfulgit/git/trees/3c02cb0f836416718a76d853583c3aae37c1dff7/",
                "sha": "3c02cb0f836416718a76d853583c3aae37c1dff7"
            },
            "parents": [
                {
                    "url": "http://localhost:5000/repos/restfulgit/commits/6c1626a0d07e4bcfdbee4a11c898199a6f7d07b6/",
                    "sha": "6c1626a0d07e4bcfdbee4a11c898199a6f7d07b6"
                }
            ],
            "message": "document commit-in-porcelain-format endpoint in README"
        }
    },
    "_links": {
        "self": "http://localhost:5000/repos/restfulgit/branches/master/"
    }
}
```

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
Retrieves a list of tags:

    GET /repos/:repo_key/tags/

```json
[
    {
        "name": "initial",
        "url": "http://localhost:5000/repos/restfulgit/tags/initial/",
        "commit": {
            "url": "http://localhost:5000/repos/restfulgit/commits/07b9bf1540305153ceeb4519a50b588c35a35464/",
            "sha": "07b9bf1540305153ceeb4519a50b588c35a35464"
        }
    },
    ...
]
```

Retrieves a specific tag object by name:

    GET /repos/:repo_key/tags/:tag_name/

```json
{
    "name": "initial",
    "url": "http://localhost:5000/repos/restfulgit/tags/initial/",
    "tag": {
        "message": "initial commit\n",
        "object": {
            "sha": "07b9bf1540305153ceeb4519a50b588c35a35464",
            "type": "commit",
            "url": "http://localhost:5000/repos/restfulgit/git/commits/07b9bf1540305153ceeb4519a50b588c35a35464/"
        },
        "sha": "1dffc031c9beda43ff94c526cbc00a30d231c079",
        "tag": "initial",
        "tagger": {
            "date": "2013-09-28T01:14:09Z",
            "email": "chris.rebert@hulu.com",
            "name": "Chris Rebert"
        },
        "url": "http://localhost:5000/repos/restfulgit/git/tags/1dffc031c9beda43ff94c526cbc00a30d231c079/"
    },
    "commit": {
        "author": {
            "date": "2013-02-24T13:25:46Z",
            "email": "rajiv@hulu.com",
            "name": "Rajiv Makhijani"
        },
        "commit": {
            "author": {
                "date": "2013-02-24T13:25:46Z",
                "email": "rajiv@hulu.com",
                "name": "Rajiv Makhijani"
            },
            "committer": {
                "date": "2013-02-24T13:25:46Z",
                "email": "rajiv@hulu.com",
                "name": "Rajiv Makhijani"
            },
            "message": "Initial support for read-only REST api for Git plumbing",
            "parents": [],
            "sha": "07b9bf1540305153ceeb4519a50b588c35a35464",
            "tree": {
                "sha": "6ca22167185c31554aa6157306e68dfd612d6345",
                "url": "http://localhost:5000/repos/restfulgit/git/trees/6ca22167185c31554aa6157306e68dfd612d6345/"
            },
            "url": "http://localhost:5000/repos/restfulgit/git/commits/07b9bf1540305153ceeb4519a50b588c35a35464/"
        },
        "committer": {
            "date": "2013-02-24T13:25:46Z",
            "email": "rajiv@hulu.com",
            "name": "Rajiv Makhijani"
        },
        "parents": [],
        "sha": "07b9bf1540305153ceeb4519a50b588c35a35464",
        "url": "http://localhost:5000/repos/restfulgit/commits/07b9bf1540305153ceeb4519a50b588c35a35464/"
    }
}
```

Retrieves a specific tag object by SHA:

    GET /repos/:repo_key/git/tags/:tag_sha/

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
        "date": "2013-09-13T04:00:28Z",
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

    GET /repos/:repo_key/raw/:refspec/:file_path

List Repositories
----------
Retrieves a list of general information about all of the repos:

    GET /repos/

```json
[
    {
        "name": "restfulgit",
        "description": "REST API for Git data",
        "url": "http://localhost:5000/repos/restfulgit/",
        ...
    },
    ...
]
```

Repository Info
----------
Retrieve general information about a specific repo:

    GET /repos/:repo_key/

```json
{
    "name": "restfulgit",
    "full_name": "restfulgit",
    "description": "REST API for Git data",
    "url": "http://localhost:5000/repos/restfulgit/",
    "commits_url": "http://localhost:5000/repos/restfulgit/commits{/sha}",
    "blobs_url": "http://localhost:5000/repos/restfulgit/git/blobs{/sha}",
    "branches_url": "http://localhost:5000/repos/restfulgit/branches{/branch}",
    "tags_url": "http://localhost:5000/repos/restfulgit/tags/",
    "trees_url": "http://localhost:5000/repos/restfulgit/git/trees{/sha}",
    "git_commits_url": "http://localhost:5000/repos/restfulgit/git/commits{/sha}",
    "git_refs_url": "http://localhost:5000/repos/restfulgit/git/refs{/sha}",
    "git_tags_url": "http://localhost:5000/repos/restfulgit/git/tags{/sha}"
}
```

Compare Commits
----------
Retrieve the diff between two commits each specified by branch name, tag name, or commit SHA:

    GET /repos/:repo_key/compare/:refspec_1...:refspec_2.diff

    optional: ?context=:num_context_lines (default=3; the number of lines to display before and after each hunk of the diff)

```
Content-Type: text/x-diff; charset=utf-8

diff --git a/README.md b/README.md
index 83e7371..c42b50e 100644
--- a/README.md
+++ b/README.md
@@ -183,6 +183,66 @@ Retrieves a list of branches:
 ]
...
```

Archives
----------
Download a ZIP file or (gzipped) tarball of the contents of the repo at the specified branch, tag, or commit SHA:

    GET /repos/:repo_key/zipball/:refspec/
    GET /repos/:repo_key/tarball/:refspec/

```
Content-Type: application/zip
Content-Disposition: attachment; filename=restfulgit-master.zip
...
```

The zipball and gzipped-tarball features require that the Python standard library module `zlib` be available.
If `zlib` is unavailable, only the `/tarball/` endpoint will be available, and it will send an uncompressed TAR file instead of a gzipped one.
Note that this endpoint may be slow as it does no caching.

Contributors
----------
Retrieves a list of contributors for the given repo, in descending order by number of commits in the main branch:

    GET /repos/:repo_key/contributors/

```json
[
    ...
    {
        "contributions": 23,
        "email": "rajiv@hulu.com",
        "name": "Rajiv Makhijani"
    },
    ...
]
```

Contributors are presumed to be uniquely identifiable by their email address.
Note that this endpoint may be slow as it involves walking through every single commit in the main branch and does no caching.

Blame
----------
Retrieves blame information for lines in the given range of the given file at the specified branch, tag, or commit SHA:

    GET /repos/:repo_key/blame/:refspec/:file_path

    optional: ?firstLine=:line_num (default=1)
    optional: ?lastLine=:line_num (default=number of lines in the file)
    optional: ?oldest=:refspec (default=first commit in the repository; the oldest commit to consider; can be a branch, a tag, or a commit SHA)

```json

{
    "lines": [
        {
            "commit": "bcb720a10cd8452626e037673b3958facac9a789",
            "line": "# coding=utf-8",
            "origPath": "restfulgit/app.py",
            "lineNum": 1
        },
        {
            "commit": "bcb720a10cd8452626e037673b3958facac9a789",
            "line": "from __future__ import absolute_import, unicode_literals, print_function, division",
            "origPath": "restfulgit/app.py",
            "lineNum": 2
        },
        ...
    ],
    "commits": {
        "bcb720a10cd8452626e037673b3958facac9a789": {
            "committer": {
                "date": "2014-01-15T20:36:39Z",
                "name": "Chris Rebert",
                "email": "chris.rebert@hulu.com"
            },
            "author": {
                "date": "2014-01-04T01:10:41Z",
                "name": "Chris Rebert",
                "email": "chris.rebert@hulu.com"
            },
            "url": "http://localhost:5000/repos/restfulgit/git/commits/bcb720a10cd8452626e037673b3958facac9a789/",
            "tree": {
                "url": "http://localhost:5000/repos/restfulgit/git/trees/8d50e406c9581433d2ec19d069fa32f3f03c43d8/",
                "sha": "8d50e406c9581433d2ec19d069fa32f3f03c43d8"
            },
            "sha": "bcb720a10cd8452626e037673b3958facac9a789",
            "parents": [
                {
                    "url": "http://localhost:5000/repos/restfulgit/git/commits/29c9c6ef4a1f4f78aee60418e31a2a535d2bc923/",
                    "sha": "29c9c6ef4a1f4f78aee60418e31a2a535d2bc923"
                }
            ],
            "message": "refactoring: split things out into a bunch more packages+modules"
        },
        ...
    }
}
```

Contents
----------
Retrieves a listing of the contents of a given directory at the given branch, tag, or commit.

    GET /repos/:repo_key/contents/:directory_path
    
    optional ?ref=:refspec (default=the default branch; can be a branch, a tag, or a commit SHA)

```json
[
    {
        "name": ".gitignore",
        "path": ".gitignore",
        "type": "file",
        "size": 55,
        "sha": "3eac043ba3a315bce813d557102bb69ff9511d19",
        "url": "http://localhost:5000/repos/restfulgit/contents/.gitignore?ref=master",
        "git_url": "http://localhost:5000/repos/restfulgit/git/blobs/3eac043ba3a315bce813d557102bb69ff9511d19/",
        "_links": {
            "self": "http://localhost:5000/repos/restfulgit/contents/.gitignore?ref=master",
            "git": "http://localhost:5000/repos/restfulgit/git/blobs/3eac043ba3a315bce813d557102bb69ff9511d19/"
        }
    },
    ...
    {
        "name": "restfulgit",
        "path": "restfulgit",
        "type": "dir",
        "size": 0,
        "sha": "48dd8b941913f02cd22a1fa8f18355a4f81c5d78",
        "url": "http://localhost:5000/repos/restfulgit/contents/restfulgit?ref=master",
        "git_url": "http://localhost:5000/repos/restfulgit/git/trees/48dd8b941913f02cd22a1fa8f18355a4f81c5d78/",
        "_links": {
            "self": "http://localhost:5000/repos/restfulgit/contents/restfulgit?ref=master",
            "git":"http://localhost:5000/repos/restfulgit/git/trees/48dd8b941913f02cd22a1fa8f18355a4f81c5d78/"
        }
    },
    ...
]
```

Retrieves the contents of and the metadata about the given file at the given branch, tag, or commit.

    GET /repos/:repo_key/contents/:file_path
    
    optional ?ref=:refspec (default=the default branch; can be a branch, a tag, or a commit SHA)

```json
{
    "name": "LICENSE.md",
    "path": "LICENSE.md",
    "type": "file",
    "encoding": "utf-8",
    "size": 1056,
    "sha": "bb27aa0a502f73c19837b96d1bd514ba95e0d404",
    "url": "http://localhost:5000/repos/restfulgit/contents/LICENSE.md?ref=master",
    "git_url": "http://localhost:5000/repos/restfulgit/git/blobs/bb27aa0a502f73c19837b96d1bd514ba95e0d404/",
    "content": "...",
    "_links": {
        "self": "http://localhost:5000/repos/restfulgit/contents/LICENSE.md?ref=master",
        "git": "http://localhost:5000/repos/restfulgit/git/blobs/bb27aa0a502f73c19837b96d1bd514ba95e0d404/"
    }
}
```
