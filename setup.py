from setuptools import find_packages, setup, Command
import os
from shutil import rmtree
import sys

# Package meta-data.
NAME = 'meeshkan_client'
DESCRIPTION = 'The Meeshkan Client for interactive machine learning'
URL = 'https://www.meeshkan.io/'
EMAIL = 'dev@meeshkan.com'
AUTHOR = 'Meeshkan Dev Team'
REQUIRES_PYTHON = '>=3.5.0'
SRC_DIR = 'client'  # Relative location wrt setup.py

# Required packages
REQUIRED = ['requests', 'Click', 'Pyro4', 'PyYAML']

# Optional packages
EXTRAS = {'dev': ['pylint', 'pytest', 'pytest-cov']}

here = os.path.abspath(os.path.dirname(__file__))

# Import the README and use it as the long-description.
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = '\n' + f.read()

# Load the package's __version__.py module as a dictionary.
about = dict()
with open(os.path.join(here, SRC_DIR, '__version__.py')) as f:
    exec(f.read(), about)

class UploadCommand(Command):
    """Support setup.py upload."""

    description = "Build and publish the package."
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print('\033[1m{0}\033[0m'.format(s))

    def run(self):
        # bc = BuildCommand()
        # bc.run()
        try:
            self.status("Removing previous builds...")
            rmtree(os.path.join(here, 'dist'))
        except OSError:
            pass

        self.status("Building Source and Wheel (universal) distribution...")
        os.system(f"{sys.executable} setup.py sdist bdist_wheel --universal")

        self.status("Uploading the package to PyPI via Twine...")
        os.system("twine upload dist/*")

        self.status("Pushing git tags...")
        os.system(f"git tag v{about['__version__']}")
        os.system("git push --tags")

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
        'Operating System :: OS Independent',
        'Topic:: Scientific / Engineering:: Artificial Intelligence'
    ],
    cmdclass={'upload': UploadCommand}
)