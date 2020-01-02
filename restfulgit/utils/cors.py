# coding=utf-8


from functools import wraps

from flask import current_app, request, make_response


def corsify(func):
    # based on http://flask.pocoo.org/snippets/56/
    func.provide_automatic_options = False
    required_methods = set(getattr(func, 'required_methods', ()))
    required_methods.add(b'OPTIONS')
    func.required_methods = required_methods

    @wraps(func)
    def wrapped(*args, **kwargs):
        if not current_app.config['RESTFULGIT_ENABLE_CORS']:
            return func(*args, **kwargs)
        options_resp = current_app.make_default_options_response()
        if request.method == b'OPTIONS':
            resp = options_resp
        else:
            resp = make_response(func(*args, **kwargs))
        headers = resp.headers
        options_header_allow = options_resp.headers.get(b'allow')
        if options_header_allow:
            headers[b'Access-Control-Allow-Methods'] = options_header_allow
        headers[b'Access-Control-Allow-Origin'] = current_app.config['RESTFULGIT_CORS_ALLOWED_ORIGIN']
        headers[b'Access-Control-Allow-Credentials'] = str(current_app.config['RESTFULGIT_CORS_ALLOW_CREDENTIALS']).lower()
        allowed_headers = current_app.config['RESTFULGIT_CORS_ALLOWED_HEADERS']
        if allowed_headers:
            headers[b'Access-Control-Allow-Headers'] = ", ".join(allowed_headers)
        max_age = current_app.config['RESTFULGIT_CORS_MAX_AGE']
        if max_age is not None:
            headers[b'Access-Control-Max-Age'] = str(int(max_age.total_seconds()))
        return resp

    return wrapped
