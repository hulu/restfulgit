# coding=utf-8
# JSON error pages based on http://flask.pocoo.org/snippets/83/


from flask import Blueprint, jsonify
from werkzeug.exceptions import HTTPException, default_exceptions

from restfulgit.utils.cors import corsify


def register_general_error_handler(blueprint_or_app, handler):
    error_codes = list(default_exceptions.keys())
    if isinstance(blueprint_or_app, Blueprint):
        error_codes.remove(500)  # Flask doesn't currently allow per-Blueprint HTTP 500 error handlers

    for err_code in error_codes:
        blueprint_or_app.errorhandler(err_code)(handler)


@corsify
def json_error_page(error):
    err_msg = error.description if isinstance(error, HTTPException) else str(error)
    resp = jsonify({'error': err_msg})
    resp.status_code = (error.code if isinstance(error, HTTPException) else 500)
    return resp
