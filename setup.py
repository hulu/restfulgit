#!/usr/bin/env python

from setuptools import setup, find_packages
import os
import sys


NAME = 'restfulgit'

VERSION = '0.1.1'

CLASSIFIERS = [
    'Development Status :: 2 - Beta',
    'Environment :: Web Environment',
    'Framework :: Flask',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Operating System :: POSIX :: Linux',
    'Programming Language :: Python :: 3.7',
    'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
    'Topic :: Software Development :: Libraries',
    'Topic :: Software Development :: Version Control'
]


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
    maintainer='Kaiwen Xu',
    maintainer_email='kaiwen.xu@hulu.com',
    author='Rajiv Makhijani',
    url='https://github.com/hulu/restfulgit',
    provides=[NAME],
    packages=find_packages(exclude=['tests']),
    zip_safe=True,
    install_requires=requirements
)
