from .__version__ import __version__  # Conform to PEP-0396

from .core import *  # pylint: disable=wildcard-import
from . import core
from .api import *  # pylint: disable=wildcard-import
from . import api
from . import exceptions

# Only make the following available by default
__all__ = ["__version__", "exceptions", "config"]
__all__ += api.__all__

del core  # Clean-up (make `meeshkan.core` unavailable)
del api
