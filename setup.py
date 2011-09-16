#!/usr/bin/env python

import distutils.core
import subprocess
import sys
# Importing setuptools adds some features like "setup.py develop", but
# it's optional so swallow the error if it's not there.
try:
    import setuptools
except ImportError:
    pass

kwargs = {}

major, minor = sys.version_info[:2]

if major >= 3:
    import setuptools # setuptools is required for use_2to3
    kwargs["use_2to3"] = True

classifiers = """\
Development Status :: 2 - Pre-Alpha
Environment :: Console
Intended Audience :: Developers
License :: OSI Approved :: MIT License
Operating System :: POSIX
Operating System :: Microsoft
Programming Language :: Python :: 2.5
Programming Language :: Python :: 3.0
Topic :: Internet :: WWW/HTTP :: Dynamic Content
Topic :: Internet :: WWW/HTTP :: HTTP Servers
Topic :: Internet :: WWW/HTTP :: WSGI :: Server
"""

distutils.core.setup(
    name="vortex",
    version="0.0.5",
    packages = ["vortex"],
    package_data = {"vortex": ["README.md"]},
    author="Alek Storm",
    author_email="alek.storm@gmail.com",
    url="http://alekstorm.github.com/vortex",
    description="An experimental resource-based web framework built on Tornado's IOLoop",
    long_description = subprocess.Popen('pandoc -r markdown -w rst README.md', stdout=subprocess.PIPE, shell=True).communicate()[0],
    classifiers=filter(None, classifiers.split("\n")),
    **kwargs
)
