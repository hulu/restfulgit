# coding=utf-8
from __future__ import absolute_import, unicode_literals, print_function, division

from datetime import tzinfo, timedelta


class FixedOffset(tzinfo):
    ZERO = timedelta(0)

    def __init__(self, offset):
        super(FixedOffset, self).__init__()
        self._offset = timedelta(minutes=offset)

    def utcoffset(self, dt):  # pylint: disable=W0613
        return self._offset

    def dst(self, dt):  # pylint: disable=W0613
        return self.ZERO


UTC = FixedOffset(0)
