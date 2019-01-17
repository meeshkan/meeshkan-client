from .__version__ import __version__  # Conform to PEP-0396

from . import core
from .core import *  # pylint: disable=wildcard-import
from . import api
from .api import *  # pylint: disable=wildcard-import
from . import agent
from .agent import *  # pylint: disable=wildcard-import
from . import notifications
from .notifications import *  # pylint: disable=wildcard-import

from . import exceptions
from . import sagemaker
from .__utils__ import save_token


# Only make the following available by default
__all__ = ["__version__", "exceptions", "config", "save_token"]
__all__ += api.__all__
__all__ += agent.__all__
__all__ += core.__all__
__all__ += notifications.__all__

# Clean-up (make `meeshkan.core`, etc unavailable)
del core, api, agent, notifications


try:
    from IPython.core.magic import line_magic, Magics, magics_class
    @magics_class
    class MeeshkanMagic(Magics):
        @line_magic
        def meeshkan(self, line):
            from .core.job import IPythonJob
            from .__utils__ import _get_api

            job = IPythonJob(self.shell, line)
            job.launch_and_wait()
            return job
            # _get_api().submit_job(job)



    def load_ipython_extension(ipython):
        ipython.register_magics(MeeshkanMagic)
    try:
        ip = get_ipython()
        ip.magic("load_ext meeshkan")
    except Exception:
        pass

    del Magics, magics_class, line_magic
except ModuleNotFoundError:
    pass
