from .__version__ import __version__  # Conform to PEP-0396

# The contents of the following is imported to module level, with __all__ extended with their respective __all__
# These should be `del` later to clean the namespace
from . import core
from .core import *  # pylint: disable=wildcard-import
from . import api
from .api import *  # pylint: disable=wildcard-import
# TODO - this import system works mainly with submodules; `agent` and accompanying `__utils__` should be moved to their
#        own submodule
from . import agent
from .agent import *  # pylint: disable=wildcard-import
from . import notifications
from .notifications import *  # pylint: disable=wildcard-import
from . import git
from .git import *  # pylint: disable=wildcard-import

# The following are available as is; written explicitly also in __all__
from . import exceptions
from . import sagemaker
from .__utils__ import save_token


# Only make the following available by default
__all__ = ["__version__", "exceptions", "config", "save_token", "sagemaker", "submit_git"]
__all__ += api.__all__
__all__ += agent.__all__
__all__ += core.__all__
__all__ += notifications.__all__

# Clean-up (make `meeshkan.core`, etc unavailable)
del core
del api
del agent
del notifications
del git
