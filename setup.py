from setuptools import find_packages, setup, Command
import stat
import os
from shutil import rmtree
import sys

# Package meta-data.
NAME = 'meeshkan'
DESCRIPTION = 'The Meeshkan Client for interactive machine learning'
URL = 'https://www.meeshkan.io/'
EMAIL = 'dev@meeshkan.com'
AUTHOR = 'Meeshkan Dev Team'
REQUIRES_PYTHON = '>=3.5.0'
SRC_DIR = 'meeshkan'  # Relative location wrt setup.py

# Required packages
REQUIRED = ['requests', 'Click', 'Pyro4', 'PyYAML', 'tabulate', 'matplotlib']

DEV = ['pylint', 'pytest', 'pytest-cov', 'mypy', 'pytest-asyncio']
# Optional packages
EXTRAS = {'dev': DEV,
          'devTF': DEV + ['tensorflow', 'tensorboard', 'keras'],
          'devTorch':  DEV + ['torch']}

# Entry point for CLI (relative to setup.py)
ENTRY_POINTS = ['meeshkan = meeshkan.__main__:cli']

here = os.path.abspath(os.path.dirname(__file__))

# Import the README and use it as the long-description.
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = '\n' + f.read()

# Load the package's __version__.py module as a dictionary.
about = dict()
with open(os.path.join(here, SRC_DIR, '__version__.py')) as f:
    exec(f.read(), about)


class SetupCommand(Command):
    """Base class for setup.py commands with no arguments"""
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print('\033[1m{0}\033[0m'.format(s))


class BuildDistCommand(SetupCommand):
    """Support setup.py upload."""
    description = "Build the package."

    def run(self):
        try:
            self.status("Removing previous builds...")
            rmtree(os.path.join(here, 'dist'))
        except OSError:
            pass

        self.status("Building Source and Wheel (universal) distribution...")
        os.system("{executable} setup.py sdist bdist_wheel --universal".format(executable=sys.executable))
        sys.exit()


class UploadCommand(SetupCommand):
    """Support setup.py upload."""
    description = "Build and publish the package."

    def run(self):
        try:
            self.status("Removing previous builds...")
            rmtree(os.path.join(here, 'dist'))
        except OSError:
            pass

        self.status("Building Source and Wheel (universal) distribution...")
        os.system("{executable} setup.py sdist bdist_wheel --universal".format(executable=sys.executable))

        self.status("Uploading the package to PyPI via Twine...")
        os.system("twine upload dist/*")

        self.status("Pushing git tags...")
        os.system("git tag v{about}".format(about=about['__version__']))
        os.system("git push --tags")

        sys.exit()


class TestCommand(SetupCommand):
    """Support setup.py test."""
    description = "Run local test if they exist"

    def run(self):
        os.system("pytest")
        sys.exit()

setup(
    name=NAME,
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
    license='Apache 2.0',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Operating System :: MacOS',
        'Operating System :: POSIX',
        'Operating System :: Unix'
    ],
    entry_points={'console_scripts': ENTRY_POINTS},
    cmdclass={'dist': BuildDistCommand, 'upload': UploadCommand, 'test': TestCommand}
)
