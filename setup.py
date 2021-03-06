#!/usr/bin/env python3

'''
'''

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='picks',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version='0.6.5',

    description='A picture viewer, tagger and picker',
    long_description=long_description,

    # The project's main homepage.
    url='https://github.com/frans-fuerst/picks',

    # Author details
    author='Frans Fuerst',
    author_email='frans.fuerst+github@gmail.com',

    # Choose your license
    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
#        'Intended Audience :: Developers',
#        'Topic :: Software Development :: Build Tools',

        # Pick your license as you wish (should match "license" above)
#        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
    ],

    keywords='picks image picture viewer choose pick tagging slideshow gallery',

    packages=find_packages(exclude=['contrib', 'docs', 'tests']),

    scripts = ['picks'],

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=['ExifRead', 'PyQt5'],

    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
#    extras_require={
#        'dev': ['check-manifest'],
#        'test': ['coverage'],
#    },

    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    package_data={
        'picks_viewer': ['QTDark.stylesheet', 'picks.ui'],
    },
)

