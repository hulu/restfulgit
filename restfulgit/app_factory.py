# coding=utf-8
from __future__ import absolute_import, unicode_literals, print_function, division

from datetime import timedelta

from flask import Flask

from restfulgit.plumbing.routes import plumbing
from restfulgit.porcelain.routes import porcelain
from restfulgit.archives import archives
from restfulgit.utils.json_err_pages import json_error_page, register_general_error_handler
from restfulgit.utils.json import jsonify
from restfulgit.utils.cors import corsify


BLUEPRINTS = (plumbing, porcelain, archives)


class DefaultConfig(object):
    RESTFULGIT_DEFAULT_COMMIT_LIST_LIMIT = 50
    RESTFULGIT_ENABLE_CORS = False
    RESTFULGIT_CORS_ALLOWED_HEADERS = []
    RESTFULGIT_CORS_ALLOW_CREDENTIALS = False
    RESTFULGIT_CORS_MAX_AGE = timedelta(days=30)
    RESTFULGIT_CORS_ALLOWED_ORIGIN = "*"


def create_app(config_obj_dotted_path=None):
    # pylint: disable=W0612
    app = Flask(__name__)

    app.config.from_object(DefaultConfig)
    if config_obj_dotted_path is not None:  # pragma: no cover
        app.config.from_object(config_obj_dotted_path)

    register_general_error_handler(app, json_error_page)

    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)

    @app.route('/')
    @corsify
    @jsonify
    def index():  # pragma: no cover
        links = []
        for rule in app.url_map.iter_rules():
            if str(rule).startswith("/repos"):
                links.append(str(rule))
        return links

    return app
