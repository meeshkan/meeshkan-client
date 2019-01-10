from .__version__ import __version__  # Conform to PEP-0396

from .core import *  # pylint: disable=wildcard-import
from . import core
from .api import *  # pylint: disable=wildcard-import
from . import api
from . import exceptions
from . import sagemaker
from .start import start_agent as start, restart_agent as restart, init, stop as stop
from .utils import save_token

# Only make the following available by default
__all__ = ["__version__", "exceptions", "config"]
__all__ += api.__all__
__all__ += ["save_token", "start", "restart_agent", "init"]

del core  # Clean-up (make `meeshkan.core` unavailable)
del api
# del utils  # This is still required by mocking tests
