# coding=utf-8
from datetime import timedelta

# base path for repositories that should be exposed
RESTFULGIT_REPO_BASE_PATH = '/Code/'
# default number of commits that should be returned by /repos/<repo_key>/git/commits/
RESTFULGIT_DEFAULT_COMMIT_LIST_LIMIT = 50

# Cross-Origin Resource Sharing
RESTFULGIT_ENABLE_CORS = False
RESTFULGIT_CORS_ALLOWED_ORIGIN = "*"
RESTFULGIT_CORS_ALLOW_CREDENTIALS = False
RESTFULGIT_CORS_ALLOWED_HEADERS = []
RESTFULGIT_CORS_MAX_AGE = timedelta(days=30)

# Cache-Control header for conditional GETs
RESTFULGIT_CACHE_CONTROL = "max-age=3600"
