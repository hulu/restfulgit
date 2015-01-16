#!/usr/bin/env python

from distutils.core import setup
import os
import sys


NAME = 'restfulgit'

VERSION = '0.1.0'

MIN_PYTHON_VERSION = (2, 7)
MIN_UNSUPPORTED_VERSION = 3

CLASSIFIERS = [
    'Development Status :: 2 - Beta',
    'Environment :: Web Environment',
    'Framework :: Flask',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Operating System :: POSIX :: Linux',
    'Programming Language :: Python :: 2.7',
    'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
    'Topic :: Software Development :: Libraries',
    'Topic :: Software Development :: Version Control'
]


if sys.version_info < MIN_PYTHON_VERSION or sys.version_info[0] >= MIN_UNSUPPORTED_VERSION:
    raise Exception(
        '%s==%s requires Python >= %s and Python < %d' % (
            NAME,
            VERSION,
            '.'.join([str(x) for x in MIN_PYTHON_VERSION]),
            MIN_UNSUPPORTED_VERSION
        )
    )

with open(os.path.join(os.path.dirname(__file__), 'requirements.txt')) as f:
    requirements = f.readlines()


def get_packages(root_pkg_name):
    pkgs = []
    for dirs, _, files in os.walk(os.path.join(root_pkg_name)):
        if '__init__.py' in files:
            package = dirs.replace(os.sep, '.')
            pkgs.append(package)
    return pkgs


setup(
    name=NAME,
    version=VERSION,
    description='A restful interface for accessing data from Git repositories',
    long_description=open('README.md').read(),
    classifiers=CLASSIFIERS,
    maintainer='Chris Rebert',
    maintainer_email='chris.rebert@hulu.com',
    author='Rajiv Makhijani',
    url='https://github.com/hulu/restfulgit',
    provides=[NAME],
    packages=get_packages('restfulgit'),
    zip_safe=True,
    install_requires=requirements
)
