# from setuptools import setup, find_packages
# from client.__version__ import __version__
#
# setup(
#     name="Meeshkan Client",
#     version=__version__,
#     author="",
#     author_email="",
#     description="",
#     url="",
#     long_description="",
#     license="",
#     install_requires=[],
#     packages=find_packages())


import io
import os
import sys
from shutil import rmtree

from setuptools import find_packages, setup, Command

# Package meta-data.
NAME = 'Meeshkan Client'
DESCRIPTION = 'The Meeshkan Client for interactive machine learning'
URL = 'https://www.meeshkan.io/'
EMAIL = 'dev@meeshkan.com'
AUTHOR = 'Meeshkan Dev Team'
REQUIRES_PYTHON = '>=3.5.0'

# Required packages
REQUIRED = ['requests', 'Click', 'Pyro4', 'PyYAML']

# Optional packages
EXTRAS = {}

SRC_DIR = 'client'

here = os.path.abspath(os.path.dirname(__file__))

# Import the README and use it as the long-description.
with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = '\n' + f.read()

# Load the package's __version__.py module as a dictionary.
about = {}
with open(os.path.join(here, SRC_DIR, '__version__.py')) as f:
    exec(f.read(), about)


setup(name=NAME,
      version=about['__version__'],
      description=DESCRIPTION,
      long_description=long_description,
      long_description_content_type='text/markdown',
      author=AUTHOR,
      author_email=EMAIL,
      python_requires=REQUIRES_PYTHON,
      url=URL,
      packages=find_packages(exclude=('tests',)),
      install_requires=REQUIRED,
      extras_require=EXTRAS,
      include_package_data=True,
      license='MIT',
      classifiers=[
          'Development Status :: 2 - Pre-Alpha',
          'License :: Other/Proprietary License',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Programming Language :: Python :: Implementation :: CPython',
          'Programming Language :: Python :: Implementation :: PyPy',
          'Topic:: Scientific / Engineering:: Artificial Intelligence']
      )