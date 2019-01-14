from .__version__ import __version__  # Conform to PEP-0396

from .core import *  # pylint: disable=wildcard-import
from . import core
from .api import *  # pylint: disable=wildcard-import
from . import api
from . import exceptions
from . import sagemaker
from .__utils__ import save_token
from . import agent
from .agent import *


# Only make the following available by default
__all__ = ["__version__", "exceptions", "config"]
__all__ += api.__all__
__all__ += agent.__all__

del core  # Clean-up (make `meeshkan.core` unavailable)
del api
del agent

__doc__ = """
Meeshkan - Monitoring and remote-control tool for machine learning jobs
=======================================================================
**meeshkan** is a Python package providing control to your machine learning jobs. 

Main Features
-------------
Here are just a few of the things meeshkan can do:
  - Notify you of your job's progress at fixed intervals.
  - Notify you when certain events happen
  - Allow you to control training jobs remotely
  - Allow monitoring Amazon SageMaker jobs
"""
