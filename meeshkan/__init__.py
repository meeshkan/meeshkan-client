from .__version__ import __version__  # Conform to PEP-0396

from .core import *  # pylint: disable=wildcard-import
from . import core
from .api import *  # pylint: disable=wildcard-import
from . import api
from . import exceptions
from . import sagemaker
from . import notifications  # Exposed for tests for now
from .start import start_agent as start, restart_agent as restart, init, stop_agent as stop
from .__utils__ import save_token

# Only make the following available by default
__all__ = ["__version__", "exceptions", "config"]
__all__ += api.__all__
__all__ += ["save_token", "start", "restart_agent", "init"]

del core  # Clean-up (make `meeshkan.core` unavailable)
del api
# del utils  # This is still required by tests that use patching.

__doc__ = """
Meeshkan - Monitoring and remote-control tool for machine learning jobs
=====================================================================
**meeshkan** is a Python package providing control to your machine learning jobs. 

Main Features
-------------
Here are just a few of the things meeshkan can do:
  - Notify you of your job's progress at fixed intervals.
  - Notify you when certain events happen
  - Allow you to control training jobs remotely
  - Allow monitoring Amazon SageMaker jobs
"""
