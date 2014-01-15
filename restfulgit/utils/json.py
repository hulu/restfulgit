# coding=utf-8
from __future__ import absolute_import, unicode_literals, print_function, division

from json import dumps
from functools import wraps

from flask import Response

from restfulgit.utils import mime_types
from restfulgit.utils.timezones import UTC


def jsonify(func):
    def dthandler(obj):
        if hasattr(obj, 'isoformat'):
            return obj.astimezone(UTC).replace(tzinfo=None).isoformat() + 'Z'

    @wraps(func)
    def wrapped(*args, **kwargs):
        return Response(dumps(func(*args, **kwargs), default=dthandler),
                        mimetype=mime_types.JSON)
    return wrapped
