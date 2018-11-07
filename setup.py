from setuptools import setup, find_packages
from client.version import __version__

setup(
    name="Meeshkan Client",
    version=__version__,
    packages=find_packages())
